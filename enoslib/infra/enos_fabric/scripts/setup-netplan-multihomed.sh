#!/usr/bin/env bash
# Configure:
#  1) UPLINK static + conditional routing (PBR for IPv4, standard for IPv6)
#  2) LAN static + internal route
#  3) rp_filter relaxed for asymmetric routing
#
# Requires: Netplan, iproute2, python3
# Safe to re-run (idempotent) and uses /etc/netplan/ for persistence.

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  setup-netplan-multihomed.sh [options]

Options (CLI args override env vars):
  -I <if>     UPLINK_IF          (e.g., "enp8s0")
  -A <cidr>   UPLINK_ADDR        (e.g., "203.0.113.10/28" or "2001:db8::10/64")
  -G <ip>     UPLINK_GW          (e.g., "203.0.113.1" or "2001:db8::1")
  -T <num>    PBR_TABLE          (default: $PBR_TABLE or 100)
  -P <num>    PBR_PRIORITY       (default: $PBR_PRIORITY or 1000)
  -t <type>   NETWORK_TYPE       (L2Bridge, L2STS, FABNetv4, FABNetv6, FABNetv4Ext, FABNetv6Ext)

  -i <if>     LAN_IF             (e.g., "enp9s0")
  -a <cidr>   LAN_ADDR           (e.g., "10.134.135.2/24" or "fd00::2/64")
  -n <cidr>   LAN_NET            (default: $LAN_NET or "10.128.0.0/10")
  -g <ip>     LAN_GW             (e.g., "10.134.135.1" or "fd00::1")

  -v          VERBOSE=1 (default)
  -q          VERBOSE=0
  -h          Show this help and exit

Environment Variables:
  FORCE_IP_VERSION=4|6    Force IPv4 or IPv6 mode (bypasses auto-detection)

Behavior:
- If you pass -I (uplink) and/or -i (lan), the script configures ONLY those sides.
- If neither -I nor -i is provided, it configures BOTH sides (backward compatible).
- IP version is auto-detected via connectivity test, or set via FORCE_IP_VERSION.
- IPv4 uses Policy-Based Routing (PBR). IPv6 uses standard routing.
USAGE
}

# =========================
# Defaults (override via env or CLI)
# =========================
UPLINK_IF="${UPLINK_IF:-}"
UPLINK_ADDR="${UPLINK_ADDR:-}"
UPLINK_GW="${UPLINK_GW:-}"
PBR_TABLE="${PBR_TABLE:-100}"
PBR_PRIORITY="${PBR_PRIORITY:-1000}"
NETWORK_TYPE="${NETWORK_TYPE:-}"
#NETPLAN_UPLINK_FILE="/etc/netplan/90-uplink-pbr-${UPLINK_IF}.yaml"

LAN_IF="${LAN_IF:-}"
LAN_ADDR="${LAN_ADDR:-}"
LAN_NET="${LAN_NET:-10.128.0.0/10}"
LAN_GW="${LAN_GW:-}"
#NETPLAN_LAN_FILE="/etc/netplan/91-lan-route-${LAN_IF}.yaml"

VERBOSE="${VERBOSE:-1}"
NETPLAN_YAML="" # Accumulates the full Netplan config

# Track which sides were explicitly specified via CLI
CLI_SET_UPLINK=0
CLI_SET_LAN=0

# =========================
# CLI parsing
# =========================
while getopts ":I:A:G:T:P:t:i:a:n:g:vqh" opt; do
  case "$opt" in
    I) UPLINK_IF="$OPTARG"; CLI_SET_UPLINK=1 ;;
    A) UPLINK_ADDR="$OPTARG" ;;
    G) UPLINK_GW="$OPTARG" ;;
    T) PBR_TABLE="$OPTARG" ;;
    P) PBR_PRIORITY="$OPTARG" ;;
    t) NETWORK_TYPE="$OPTARG" ;;
    i) LAN_IF="$OPTARG"; CLI_SET_LAN=1 ;;
    a) LAN_ADDR="$OPTARG" ;;
    n) LAN_NET="$OPTARG" ;;
    g) LAN_GW="$OPTARG" ;;
    v) VERBOSE=1 ;;
    q) VERBOSE=0 ;;
    h) usage; exit 0 ;;
    \?) echo "[!] Invalid option: -$OPTARG" >&2; usage; exit 2 ;;
    :)  echo "[!] Option -$OPTARG requires an argument." >&2; usage; exit 2 ;;
  esac
done
shift $((OPTIND-1))

NETPLAN_UPLINK_FILE="/etc/netplan/90-uplink-pbr-${UPLINK_IF}.yaml"
NETPLAN_LAN_FILE="/etc/netplan/91-lan-route-${LAN_IF}.yaml"

# Implicit side selection:
DO_UPLINK=$(( CLI_SET_UPLINK == 1 || (CLI_SET_UPLINK == 0 && CLI_SET_LAN == 0) ? 1 : 0 ))
DO_LAN=$(( CLI_SET_LAN == 1 || (CLI_SET_UPLINK == 0 && CLI_SET_LAN == 0) ? 1 : 0 ))

log(){ [ "$VERBOSE" = "1" ] && echo "[*] $*" >&2 || true; }
die(){ echo "[!] $*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }
is_ipv6(){ [[ "$1" =~ : ]]; }

need netplan
need ip

# Check for python3 (optional but helpful)
HAS_PYTHON3=0
command -v python3 >/dev/null 2>&1 && HAS_PYTHON3=1

# Helpers
get_ip_cidr(){ ip -${IP_VERSION} -o addr show dev "$1" | awk '{print $4}' | head -n1; }
cidr_ip(){ echo "${1%/*}"; }
cidr_prefix(){ echo "${1#*/}"; }

# Network base calculation - with fallback for IPv4
net_base_from_cidr(){
  if [ "$HAS_PYTHON3" = "1" ]; then
    python3 - "$1" <<'PY'
import sys, ipaddress
print(ipaddress.ip_network(sys.argv[1], strict=False).network_address)
PY
  else
    # Bash fallback for IPv4 only
    local cidr="$1"
    if [[ "$cidr" =~ : ]]; then
      die "Python3 required for IPv6 network calculations. Please install python3."
    fi

    local ip="${cidr%/*}"
    local prefix="${cidr#*/}"

    # Convert IP to integer
    IFS=. read -r i1 i2 i3 i4 <<< "$ip"
    local ip_int=$(( (i1 << 24) + (i2 << 16) + (i3 << 8) + i4 ))

    # Calculate netmask
    local mask=$(( 0xFFFFFFFF << (32 - prefix) ))

    # Calculate network address
    local net_int=$(( ip_int & mask ))

    # Convert back to dotted notation
    echo "$(( (net_int >> 24) & 0xFF )).$(( (net_int >> 16) & 0xFF )).$(( (net_int >> 8) & 0xFF )).$(( net_int & 0xFF ))"
  fi
}

# Gateway guessing - with fallback for IPv4
guess_gw_from_cidr(){
  if [ "$HAS_PYTHON3" = "1" ]; then
    python3 - "$1" <<'PY'
import sys, ipaddress
net = ipaddress.ip_network(sys.argv[1], strict=False)
hosts = list(net.hosts())
print(hosts[0] if hosts else str(net.network_address)+"/"+str(net.prefixlen))
PY
  else
    # Bash fallback for IPv4 only
    local cidr="$1"
    if [[ "$cidr" =~ : ]]; then
      die "Python3 required for IPv6 calculations. Please install python3 or provide gateway with -G"
    fi

    local ip="${cidr%/*}"
    local prefix="${cidr#*/}"

    # For /31 and /32, return the IP itself
    if [ "$prefix" -ge 31 ]; then
      echo "$ip"
      return
    fi

    # Convert IP to integer
    IFS=. read -r i1 i2 i3 i4 <<< "$ip"
    local ip_int=$(( (i1 << 24) + (i2 << 16) + (i3 << 8) + i4 ))

    # Calculate netmask and network address
    local mask=$(( 0xFFFFFFFF << (32 - prefix) ))
    local net_int=$(( ip_int & mask ))

    # First usable IP is network + 1
    local gw_int=$(( net_int + 1 ))

    # Convert back to dotted notation
    echo "$(( (gw_int >> 24) & 0xFF )).$(( (gw_int >> 16) & 0xFF )).$(( (gw_int >> 8) & 0xFF )).$(( gw_int & 0xFF ))"
  fi
}

# ==========================================
# Network Type Validation and IP Version Detection
# ==========================================
# Validate network type if specified
if [ -n "$NETWORK_TYPE" ]; then
  case "$NETWORK_TYPE" in
    L2Bridge|L2STS|FABNetv4|FABNetv6|FABNetv4Ext|FABNetv6Ext)
      log "Network type: $NETWORK_TYPE"
      ;;
    *)
      die "Invalid NETWORK_TYPE=$NETWORK_TYPE. Use L2Bridge, L2STS, FABNetv4, FABNetv6, FABNetv4Ext, or FABNetv6Ext."
      ;;
  esac
fi

# ==========================================
# IP Type Detection for Conditional Routing
# ==========================================
# Determine IP version based on network type or detection
if [ -n "$NETWORK_TYPE" ]; then
  case "$NETWORK_TYPE" in
    FABNetv4|FABNetv4Ext)
      man_ip_type=ipv4
      log "Network type $NETWORK_TYPE: Using IPv4 mode."
      ;;
    FABNetv6|FABNetv6Ext)
      man_ip_type=ipv6
      log "Network type $NETWORK_TYPE: Using IPv6 mode."
      ;;
    L2Bridge|L2STS)
      # Detect based on IP address
      if [ -n "$UPLINK_ADDR" ]; then
        if is_ipv6 "$UPLINK_ADDR"; then
          man_ip_type=ipv6
          log "Network type $NETWORK_TYPE: Detected IPv6 from address."
        else
          man_ip_type=ipv4
          log "Network type $NETWORK_TYPE: Detected IPv4 from address."
        fi
      elif [ -n "$LAN_ADDR" ]; then
        if is_ipv6 "$LAN_ADDR"; then
          man_ip_type=ipv6
          log "Network type $NETWORK_TYPE: Detected IPv6 from address."
        else
          man_ip_type=ipv4
          log "Network type $NETWORK_TYPE: Detected IPv4 from address."
        fi
      else
        man_ip_type=ipv4
        log "Network type $NETWORK_TYPE: Defaulting to IPv4."
      fi
      ;;
  esac
elif [ -n "${FORCE_IP_VERSION:-}" ]; then
  if [ "$FORCE_IP_VERSION" = "6" ]; then
    man_ip_type=ipv6
    log "Forced IPv6 mode via FORCE_IP_VERSION."
  elif [ "$FORCE_IP_VERSION" = "4" ]; then
    man_ip_type=ipv4
    log "Forced IPv4 mode via FORCE_IP_VERSION."
  else
    die "Invalid FORCE_IP_VERSION=$FORCE_IP_VERSION. Use 4 or 6."
  fi
else
  man_ip_type=ipv4
  log "Detecting primary WAN IP connectivity..."

  if command -v ping6 >/dev/null 2>&1; then
      # Use ping6 directly if it exists
      ping6 -c 1 -W 1 google.com &>/dev/null && man_ip_type=ipv6
  elif command -v ping >/dev/null 2>&1; then
      # Try 'ping -6' if ping6 command doesn't exist but ping does
      ping -6 -c 1 -W 1 google.com &>/dev/null && man_ip_type=ipv6
  fi
  log "Detected main IP type: $man_ip_type"
fi

if [ "$man_ip_type" = "ipv6" ]; then
  log "IPv6 mode: Configuring UPLINK with a standard default route (no PBR)."
  IP_VERSION=6
  UPLINK_PREFIX=128
  UPLINK_TO="::/0"
else
  log "IPv4 mode: Configuring UPLINK with Policy-Based Routing (Table $PBR_TABLE)."
  IP_VERSION=4
  UPLINK_PREFIX=32
  UPLINK_TO="0.0.0.0/0"
fi


# ======================
# 1) UPLINK (WAN) - Conditional Configuration
# ======================
if [ "$DO_UPLINK" -eq 1 ]; then
  [ -n "${UPLINK_IF:-}" ] || die "Provide -I <uplink-if> to configure UPLINK"

  if [ -z "$UPLINK_ADDR" ]; then
    UPLINK_ADDR="$(get_ip_cidr "$UPLINK_IF" || true)"
    [ -n "$UPLINK_ADDR" ] || die "UPLINK_ADDR not set and could not detect IP$man_ip_type address on $UPLINK_IF"
  fi
  UPLINK_IP="$(cidr_ip "$UPLINK_ADDR")"
  UPLINK_PREFIX="$(cidr_prefix "$UPLINK_ADDR")"

  HAS_PBR=0
  # Configure based on network type
  case "$NETWORK_TYPE" in
    L2Bridge|L2STS)
      # L2Bridge/L2STS: Configure IP only, no gateway or routes
      log "UPLINK (L2Bridge/L2STS): if=$UPLINK_IF addr=$UPLINK_ADDR (no gateway/routes)"

      NETPLAN_YAML_UPLINK=$(cat <<YAML
network:
  version: 2
  renderer: networkd
  ethernets:
    $UPLINK_IF:
      dhcp$IP_VERSION: no
      addresses:
        - $UPLINK_ADDR
YAML
)
      ;;

    FABNetv4|FABNetv6)
      # FABNetv4/FABNetv6: Configure IP + gateway + specific routes
      if [ -z "$UPLINK_GW" ]; then
        UPLINK_GW="$(ip route show | awk -v IF="$UPLINK_IF" '$0 ~ (" dev "IF" ") && $0 ~ / via / {print $3; exit}')"
        [ -n "$UPLINK_GW" ] || { UPLINK_GW="$(guess_gw_from_cidr "$UPLINK_ADDR")"; log "Guessed UPLINK_GW=$UPLINK_GW from $UPLINK_ADDR"; }
      fi

      if [ "$NETWORK_TYPE" = "FABNetv4" ]; then
        FABRIC_ROUTE="10.128.0.0/10"
        log "UPLINK (FABNetv4): if=$UPLINK_IF addr=$UPLINK_ADDR gw=$UPLINK_GW + route to $FABRIC_ROUTE"
      else
        FABRIC_ROUTE="2602:FCFB:00::/40"
        log "UPLINK (FABNetv6): if=$UPLINK_IF addr=$UPLINK_ADDR gw=$UPLINK_GW + route to $FABRIC_ROUTE"
      fi

      NETPLAN_YAML_UPLINK=$(cat <<YAML
network:
  version: 2
  renderer: networkd
  ethernets:
    $UPLINK_IF:
      dhcp$IP_VERSION: no
      addresses:
        - $UPLINK_ADDR
      routes:
        - to: $FABRIC_ROUTE
          via: $UPLINK_GW
YAML
)
      ;;

    FABNetv4Ext|FABNetv6Ext)
      # FABNetv4Ext/FABNetv6Ext: Configure IP + gateway + default route with PBR
      if [ -z "$UPLINK_GW" ]; then
        UPLINK_GW="$(ip route show | awk -v IF="$UPLINK_IF" '$0 ~ (" dev "IF" ") && $0 ~ / via / {print $3; exit}')"
        [ -n "$UPLINK_GW" ] || { UPLINK_GW="$(guess_gw_from_cidr "$UPLINK_ADDR")"; log "Guessed UPLINK_GW=$UPLINK_GW from $UPLINK_ADDR"; }
      fi

      log "UPLINK ($NETWORK_TYPE): if=$UPLINK_IF addr=$UPLINK_ADDR gw=$UPLINK_GW + default route with PBR"

      # Check if management network is same IP version
      MGMT_IP_TYPE=""
      MGMT_DEFAULT_GW=$(ip -$IP_VERSION route show default | awk '{print $3; exit}')
      if [ -n "$MGMT_DEFAULT_GW" ]; then
        MGMT_IP_TYPE=$man_ip_type
        log "Detected management network default gateway: $MGMT_DEFAULT_GW (IP version: $MGMT_IP_TYPE)"
      fi

      # Use PBR if management network is same IP version
      if [ "$MGMT_IP_TYPE" = "$man_ip_type" ]; then
        log "Management network uses same IP version, configuring PBR (table $PBR_TABLE)"
        NETPLAN_YAML_UPLINK=$(cat <<YAML
network:
  version: 2
  renderer: networkd
  ethernets:
    $UPLINK_IF:
      dhcp$IP_VERSION: no
      addresses:
        - $UPLINK_ADDR
      routes:
        - to: ${UPLINK_TO}
          via: $UPLINK_GW
          table: $PBR_TABLE
      routing-policy:
        - from: $UPLINK_IP/$UPLINK_PREFIX
          table: $PBR_TABLE
          priority: $PBR_PRIORITY
YAML
)
        HAS_PBR=1
      else
        log "Management network uses different IP version, configuring standard default route"
        NETPLAN_YAML_UPLINK=$(cat <<YAML
network:
  version: 2
  renderer: networkd
  ethernets:
    $UPLINK_IF:
      dhcp$IP_VERSION: no
      addresses:
        - $UPLINK_ADDR
      routes:
        - to: ${UPLINK_TO}
          via: $UPLINK_GW
YAML
)
      fi
      ;;

    *)
      # Default/legacy behavior: PBR for IPv4, standard for IPv6
      if [ -z "$UPLINK_GW" ]; then
        UPLINK_GW="$(ip route show | awk -v IF="$UPLINK_IF" '$0 ~ (" dev "IF" ") && $0 ~ / via / {print $3; exit}')"
        [ -n "$UPLINK_GW" ] || { UPLINK_GW="$(guess_gw_from_cidr "$UPLINK_ADDR")"; log "Guessed UPLINK_GW=$UPLINK_GW from $UPLINK_ADDR"; }
      fi

      log "UPLINK configuration: if=$UPLINK_IF addr=$UPLINK_ADDR gw=$UPLINK_GW"

      NETPLAN_YAML_UPLINK=$(cat <<YAML
network:
  version: 2
  renderer: networkd
  ethernets:
    $UPLINK_IF:
      dhcp$IP_VERSION: no
      addresses:
        - $UPLINK_ADDR
      routes:
        - to: ${UPLINK_TO}
          via: $UPLINK_GW
          table: $PBR_TABLE
YAML
)

      # Remove the PBR rule if it exists from a previous run
      log "Removing old PBR rule for $UPLINK_IP (if exists)."
      sudo ip -${IP_VERSION} rule del from "$UPLINK_IP"/${UPLINK_PREFIX} table "$PBR_TABLE" 2>/dev/null || true
      log "Adding PBR rule for $UPLINK_IP."
      sudo ip -${IP_VERSION} rule add from "$UPLINK_IP"/${UPLINK_PREFIX} table "$PBR_TABLE" priority "$PBR_PRIORITY"
      HAS_PBR=1
      ;;
  esac

  log "Writing Netplan config to $NETPLAN_UPLINK_FILE"
  echo "$NETPLAN_YAML_UPLINK" | sudo tee "$NETPLAN_UPLINK_FILE" > /dev/null

  # Apply chmod 600
  sudo chmod 600 "$NETPLAN_UPLINK_FILE"
  log "Set permissions on $NETPLAN_UPLINK_FILE to 600."
fi

# =======================
# 2) LAN (internal) - Static IP and Internal Route
# =======================
if [ "$DO_LAN" -eq 1 ]; then
  [ -n "${LAN_IF:-}" ] || die "Provide -i <lan-if> to configure LAN"

  if [ -z "$LAN_ADDR" ]; then
    LAN_ADDR="$(get_ip_cidr "$LAN_IF" || true)"
    [ -n "$LAN_ADDR" ] || die "LAN_ADDR not set and could not detect IP$man_ip_type address on $LAN_IF"
    log "Detected LAN_ADDR=$LAN_ADDR on $LAN_IF."
  fi

  if [ -z "$LAN_GW" ]; then
    LAN_GW="$(ip route show | awk -v IF="$LAN_IF" '$0 ~ (" dev "IF" ") && $0 ~ / via / {print $3; exit}')"
    [ -n "$LAN_GW" ] || { LAN_GW="$(guess_gw_from_cidr "$LAN_ADDR")"; log "Guessed LAN_GW=$LAN_GW from $LAN_ADDR"; }
  fi

  log "LAN (Netplan): if=$LAN_IF addr=$LAN_ADDR net=$LAN_NET gw=$LAN_GW"

  # Generate Netplan YAML for the LAN interface
  NETPLAN_YAML_LAN=$(cat <<YAML
network:
  version: 2
  renderer: networkd
  ethernets:
    $LAN_IF:
      dhcp${IP_VERSION}: no
      addresses:
        - $LAN_ADDR
      routes:
        # Add the route for the internal LAN network to the LAN gateway
        - to: $LAN_NET
          via: $LAN_GW
YAML
)

  log "Writing Netplan config to $NETPLAN_LAN_FILE"
  echo "$NETPLAN_YAML_LAN" | sudo tee "$NETPLAN_LAN_FILE" > /dev/null

  # Apply chmod 600
  sudo chmod 600 "$NETPLAN_LAN_FILE"
  log "Set permissions on $NETPLAN_LAN_FILE to 600."
fi


# ==========================================
# 3) rp_filter (asymmetric routing tolerant)
# ==========================================
# Apply rp_filter to any interface that was touched (or both if defaulted).
SYSCTL_FILE="/etc/sysctl.d/99-multihomed.conf"
sudo mkdir -p /etc/sysctl.d
{
  echo "net.$man_ip_type.conf.all.rp_filter=2"
  [ "$DO_UPLINK" -eq 1 ] && echo "net.$man_ip_type.conf.$UPLINK_IF.rp_filter=2"
  # [ "$DO_LAN" -eq 1 ] && echo "net.$man_ip_type.conf.$LAN_IF.rp_filter=2"
} | sudo tee "$SYSCTL_FILE" >/dev/null
sudo sysctl --system >/dev/null

# ==========================================
# 4) Apply and Verify
# ==========================================
log "Applying Netplan configuration..."
# Use netplan generate/apply in separate steps to catch errors early
sudo netplan generate || die "Netplan syntax check failed. Check YAML files."
sudo netplan apply || die "Netplan failed to apply configuration."

echo
log "Effective rules:"
ip rule show | sed 's/^/  /'

echo
if [[ "$DO_UPLINK" -eq 1 && "$HAS_PBR" -eq 1 ]]; then
  log "Routes in policy table $PBR_TABLE (PBR Mode):"
  ip route show table "$PBR_TABLE" | sed 's/^/  /'
fi

echo
log "Main routing table highlights:"
ip route show | sed 's/^/  /' | head -n 50

echo
if [ "$DO_UPLINK" -eq 1 ] && [ -n "${UPLINK_ADDR:-}" ]; then
  log "Done. Services bound to $UPLINK_IP will reply via $UPLINK_IF."
  if [ "$man_ip_type" != "ipv6" ]; then
    log "  (Using Policy-Based Routing via table $PBR_TABLE for source $UPLINK_IP)."
  else
    log "  (Using Standard Routing for source $UPLINK_IP)."
  fi
else
  log "Done."
fi
