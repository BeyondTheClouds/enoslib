#!/usr/bin/env bash

set -euo pipefail

if [ `command -v "nmcli"` ]; then
    ./setup-multihomed.sh "$@"
else
    ./setup-netplan-multihomed.sh "$@"
fi
