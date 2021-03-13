#! /usr/bin/env bash

fail() {
    echo "ERROR: $1"
    exit 1    
}

SUDO="sudo"
sudo 2>/dev/null || SUDO=""

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"

$SUDO apt-get install libunwind-dev libini-config-dev || { fail "Cannot run 'apt-get install'."; }
"$(dirname $DIR)"/install-ndctl.sh  || { fail "Cannot run install-ndctl script."; }