#!/usr/bin/env bash
# Configure:
#  1) UPLINK static + policy routing (table 100, src-based rule)
#  2) LAN static + internal route
#  3) rp_filter relaxed for asymmetric routing
#
# Requires: NetworkManager (nmcli)
# Safe to re-run (idempotent).

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  setup-multihomed.sh [options]

Options (CLI args override env vars):
  -I <if>     UPLINK_IF              (e.g., "enp8s0")
  -A <cidr>   UPLINK_ADDR            (e.g., "203.0.113.10/28" or "2001:db8::10/64")
  -G <ip>     UPLINK_GW              (e.g., "203.0.113.1" or "2001:db8::1")
  -N <name>   UPLINK_CONN            (default: $UPLINK_CONN or "uplink-static")
  -T <num>    PBR_TABLE              (default: $PBR_TABLE or 100)
  -P <num>    PBR_PRIORITY           (default: $PBR_PRIORITY or 1000)
  -t <type>   NETWORK_TYPE           (L2Bridge, L2STS, FABNetv4, FABNetv6, FABNetv4Ext, FABNetv6Ext)

  -i <if>     LAN_IF                 (e.g., "enp9s0")
  -a <cidr>   LAN_ADDR               (e.g., "10.134.135.2/24" or "fd00::2/64")
  -n <cidr>   LAN_NET                (default: $LAN_NET or "10.128.0.0/10")
  -g <ip>     LAN_GW                 (e.g., "10.134.135.1" or "fd00::1")
  -c <name>   LAN_CONN               (default: $LAN_CONN or "lan-static")

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
UPLINK_CONN="${UPLINK_CONN:-uplink-static}"
PBR_TABLE="${PBR_TABLE:-100}"
PBR_PRIORITY="${PBR_PRIORITY:-1000}"
NETWORK_TYPE="${NETWORK_TYPE:-}"

LAN_IF="${LAN_IF:-}"
LAN_ADDR="${LAN_ADDR:-}"
LAN_NET="${LAN_NET:-10.128.0.0/10}"
LAN_GW="${LAN_GW:-}"
LAN_CONN="${LAN_CONN:-lan-static}"

VERBOSE="${VERBOSE:-1}"

# Track which sides were explicitly specified via CLI
CLI_SET_UPLINK=0
CLI_SET_LAN=0

# =========================
# CLI parsing
# =========================
while getopts ":I:A:G:N:T:P:t:i:a:n:g:c:vqh" opt; do
  case "$opt" in
    I) UPLINK_IF="$OPTARG"; CLI_SET_UPLINK=1 ;;
    A) UPLINK_ADDR="$OPTARG" ;;
    G) UPLINK_GW="$OPTARG" ;;
    N) UPLINK_CONN="$OPTARG" ;;
    T) PBR_TABLE="$OPTARG" ;;
    P) PBR_PRIORITY="$OPTARG" ;;
    t) NETWORK_TYPE="$OPTARG" ;;
    i) LAN_IF="$OPTARG"; CLI_SET_LAN=1 ;;
    a) LAN_ADDR="$OPTARG" ;;
    n) LAN_NET="$OPTARG" ;;
    g) LAN_GW="$OPTARG" ;;
    c) LAN_CONN="$OPTARG" ;;
    v) VERBOSE=1 ;;
    q) VERBOSE=0 ;;
    h) usage; exit 0 ;;
    \?) echo "[!] Invalid option: -$OPTARG" >&2; usage; exit 2 ;;
    :)  echo "[!] Option -$OPTARG requires an argument." >&2; usage; exit 2 ;;
  esac
done
shift $((OPTIND-1))

# Implicit side selection:
# - If any side was specified via CLI (-I and/or -i), do ONLY those.
# - If neither was specified, do both (back-compat).
DO_UPLINK=$(( CLI_SET_UPLINK == 1 || (CLI_SET_UPLINK == 0 && CLI_SET_LAN == 0) ? 1 : 0 ))
DO_LAN=$(( CLI_SET_LAN == 1 || (CLI_SET_UPLINK == 0 && CLI_SET_LAN == 0) ? 1 : 0 ))

log(){ [ "$VERBOSE" = "1" ] && echo "[*] $*" >&2 || true; }
die(){ echo "[!] $*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"; }
is_ipv6(){ [[ "$1" =~ : ]]; }

need nmcli
need ip

# Check for python3 (optional but helpful)
HAS_PYTHON3=0
command -v python3 >/dev/null 2>&1 && HAS_PYTHON3=1

nm() { [ "$VERBOSE" = "1" ] && echo "+ nmcli $*" >&2; nmcli "$@"; }

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
print(hosts[0] if hosts else net.network_address+1)
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

conn_exists(){ nm -t -f NAME c show | awk '{print $1}' | grep -Fxq "$1"; }

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
# 1) UPLINK (WAN)
# ======================
if [ "$DO_UPLINK" -eq 1 ]; then
  [ -n "${UPLINK_IF:-}" ] || die "Provide -I <uplink-if> to configure UPLINK"

  # Set default connection name based on interface if not provided
  if [ "$UPLINK_CONN" = "uplink-static" ]; then
    UPLINK_CONN="uplink-static-${UPLINK_IF}"
  fi

  if [ -z "$UPLINK_ADDR" ]; then
    UPLINK_ADDR="$(get_ip_cidr "$UPLINK_IF" || true)"
    [ -n "$UPLINK_ADDR" ] || die "UPLINK_ADDR not set and could not detect IP$man_ip_type address on $UPLINK_IF"
  fi
  UPLINK_IP="$(cidr_ip "$UPLINK_ADDR")"
  UPLINK_PREFIX="$(cidr_prefix "$UPLINK_ADDR")"

  # Create or modify connection
  if ! conn_exists "$UPLINK_CONN"; then
    nm c add type ethernet ifname "$UPLINK_IF" con-name "$UPLINK_CONN" \
      $man_ip_type.method manual $man_ip_type.addresses "$UPLINK_ADDR" connection.autoconnect yes
  else
    nm c mod "$UPLINK_CONN" $man_ip_type.method manual $man_ip_type.addresses "$UPLINK_ADDR" connection.autoconnect yes
  fi

  HAS_PBR=0
  # Configure based on network type
  case "$NETWORK_TYPE" in
    L2Bridge|L2STS)
      # L2Bridge/L2STS: Configure IP only, no gateway or routes
      log "UPLINK (L2Bridge/L2STS): if=$UPLINK_IF addr=$UPLINK_ADDR (no gateway/routes)"
      nm c mod "$UPLINK_CONN" $man_ip_type.never-default yes
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

      nm c mod "$UPLINK_CONN" $man_ip_type.never-default yes
      nm c mod "$UPLINK_CONN" +$man_ip_type.routes "$FABRIC_ROUTE $UPLINK_GW"
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
        nm c mod "$UPLINK_CONN" $man_ip_type.never-default yes
        nm c mod "$UPLINK_CONN" $man_ip_type.route-table "$PBR_TABLE"
        nm c mod "$UPLINK_CONN" +$man_ip_type.routes "${UPLINK_TO} $UPLINK_GW"
        nm c mod "$UPLINK_CONN" +$man_ip_type.routing-rules "priority $PBR_PRIORITY from $UPLINK_IP/${UPLINK_PREFIX} table $PBR_TABLE"
        nm c mod "$UPLINK_CONN" $man_ip_type.route-metric 200
        HAS_PBR=1
      else
        log "Management network uses different IP version, configuring standard default route"
        nm c mod "$UPLINK_CONN" $man_ip_type.never-default no
        nm c mod "$UPLINK_CONN" +$man_ip_type.routes "${UPLINK_TO} $UPLINK_GW"
      fi
      ;;

    *)
      # Default/legacy behavior: PBR for IPv4, standard for IPv6
      if [ -z "$UPLINK_GW" ]; then
        UPLINK_GW="$(ip route show | awk -v IF="$UPLINK_IF" '$0 ~ (" dev "IF" ") && $0 ~ / via / {print $3; exit}')"
        [ -n "$UPLINK_GW" ] || { UPLINK_GW="$(guess_gw_from_cidr "$UPLINK_ADDR")"; log "Guessed UPLINK_GW=$UPLINK_GW from $UPLINK_ADDR"; }
      fi

      log "UPLINK: if=$UPLINK_IF addr=$UPLINK_ADDR gw=$UPLINK_GW"

      nm c mod "$UPLINK_CONN" $man_ip_type.never-default yes
      nm c mod "$UPLINK_CONN" $man_ip_type.route-table "$PBR_TABLE"
      nm c mod "$UPLINK_CONN" +$man_ip_type.routes "${UPLINK_TO} $UPLINK_GW"
      nm c mod "$UPLINK_CONN" +$man_ip_type.routing-rules "priority $PBR_PRIORITY from $UPLINK_IP/${UPLINK_PREFIX} table $PBR_TABLE"
      nm c mod "$UPLINK_CONN" $man_ip_type.route-metric 200
      HAS_PBR=1
      ;;
  esac

  nm c up "$UPLINK_CONN" || nm c up "$UPLINK_CONN"
fi

# =======================
# 2) LAN (internal)
# =======================
if [ "$DO_LAN" -eq 1 ]; then
  [ -n "${LAN_IF:-}" ] || die "Provide -i <lan-if> to configure LAN"

  # Set default connection name based on interface if not provided
  if [ "$LAN_CONN" = "lan-static" ]; then
    LAN_CONN="lan-static-${LAN_IF}"
  fi

  if [ -z "$LAN_ADDR" ]; then
    LAN_ADDR="$(get_ip_cidr "$LAN_IF" || true)"
    [ -n "$LAN_ADDR" ] || die "LAN_ADDR not set and could not detect IP$man_ip_type address on $LAN_IF"
  fi
  LAN_IP="$(cidr_ip "$LAN_ADDR")"

  if [ -z "$LAN_GW" ]; then
    LAN_GW="$(ip route show | awk -v IF="$LAN_IF" '$0 ~ (" dev "IF" ") && $0 ~ / via / {print $3; exit}')"
    [ -n "$LAN_GW" ] || { LAN_GW="$(guess_gw_from_cidr "$LAN_ADDR")"; log "Guessed LAN_GW=$LAN_GW from $LAN_ADDR"; }
  fi

  log "LAN: if=$LAN_IF addr=$LAN_ADDR net=$LAN_NET gw=$LAN_GW"

  if ! conn_exists "$LAN_CONN"; then
    nm c add type ethernet ifname "$LAN_IF" con-name "$LAN_CONN" \
      $man_ip_type.method manual $man_ip_type.addresses "$LAN_ADDR" connection.autoconnect yes
  else
    nm c mod "$LAN_CONN" $man_ip_type.method manual $man_ip_type.addresses "$LAN_ADDR" connection.autoconnect yes
  fi

  nm c mod "$LAN_CONN" $man_ip_type.never-default yes
  nm c mod "$LAN_CONN" +$man_ip_type.routes "$LAN_NET $LAN_GW"
  nm c up "$LAN_CONN" || nm c up "$LAN_CONN"
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

# =========
# Show info
# =========
echo
log "Effective rules:"
ip rule show | sed 's/^/  /'

echo
if [[ "$DO_UPLINK" -eq 1 && "$HAS_PBR" -eq 1 ]]; then
  log "Routes in policy table $PBR_TABLE:"
  ip route show table "$PBR_TABLE" | sed 's/^/  /'
fi

echo
log "Main routing table highlights:"
ip route show | sed 's/^/  /' | head -n 50

echo
if [ "$DO_UPLINK" -eq 1 ] && [ -n "${UPLINK_ADDR:-}" ]; then
  log "Done. Services bound to $(cidr_ip "$UPLINK_ADDR") will reply via $UPLINK_IF (table $PBR_TABLE)."
else
  log "Done."
fi
