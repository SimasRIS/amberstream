#!/usr/bin/env bash
#
# Service entry point. Works out which address to listen on, then execs gunicorn.
#
# With BIND_ADDR=auto (the default) this binds the VM's own primary address:
# the one on its default-route interface. That way a golden image can be cloned
# any number of times and each clone serves on its own delegated IP with no
# edit to any file, and no address is ever written into the repository.
#
# Not meant to be run by hand - systemd invokes it with deploy/amberstream.env
# already loaded. To run the site manually, use `python3 app.py`.

set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

: "${BIND_ADDR:=auto}"
: "${PORT:=80}"
: "${BIND_WAIT:=30}"

# The VM's primary IPv4: the address on whichever interface holds the default
# route. Falls back to the first global address on a real interface, so a VM on
# an isolated network with no default route still resolves. Virtual bridges are
# skipped - docker0 and friends are never the address we want to serve on.
primary_address() {
    local dev addr=""

    dev="$(ip -4 route show default 2>/dev/null | awk '{print $5; exit}')"
    if [[ -n "$dev" ]]; then
        addr="$(ip -4 -o addr show dev "$dev" scope global 2>/dev/null \
                | awk '{print $4}' | cut -d/ -f1 | head -n1)"
    fi

    if [[ -z "$addr" ]]; then
        addr="$(ip -4 -o addr show scope global 2>/dev/null \
                | awk '$2 !~ /^(docker|virbr|br-|veth|lo)/ {print $4}' \
                | cut -d/ -f1 | head -n1)"
    fi

    printf '%s' "$addr"
}

if [[ "$BIND_ADDR" == "auto" ]]; then
    # The network may not be configured yet at boot, so wait rather than
    # failing the unit and burning a restart.
    found=""
    for (( i = 0; i < BIND_WAIT; i++ )); do
        found="$(primary_address || true)"
        [[ -n "$found" ]] && break
        sleep 1
    done

    if [[ -n "$found" ]]; then
        BIND_ADDR="$found"
        echo "amberstream: listening on ${BIND_ADDR}:${PORT}"
    else
        # Fall back to loopback, never to 0.0.0.0: if we cannot work out which
        # network this VM is on, the safe answer for a deliberately vulnerable
        # app is to be reachable from nowhere but the VM itself.
        BIND_ADDR=127.0.0.1
        echo "amberstream: WARNING - no usable address found after ${BIND_WAIT}s." >&2
        echo "amberstream: listening on 127.0.0.1:${PORT} (this VM only)." >&2
        echo "amberstream: check 'ip -4 addr show', or set BIND_ADDR to a literal" >&2
        echo "amberstream: address in deploy/amberstream.env." >&2
    fi
else
    echo "amberstream: listening on ${BIND_ADDR}:${PORT}"
fi

exec "${APPDIR}/.venv/bin/gunicorn" \
    --workers 1 --threads 4 \
    --bind "${BIND_ADDR}:${PORT}" \
    --access-logfile - --error-logfile - \
    wsgi:app
