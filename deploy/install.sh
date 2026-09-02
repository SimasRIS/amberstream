#!/usr/bin/env bash
#
# Install the AmberStream training lab as a systemd service on Ubuntu 24.04.
#
#   bash deploy/install.sh
#
# Installs system packages, creates a virtualenv, writes a config file with a
# generated SECRET_KEY, initialises the database, then installs and starts a
# systemd unit that serves the site under gunicorn. Safe to re-run.
#
# Needs network access the first time: apt and pip both download. See the
# offline note in step 1 if the lab VM has no route out.
#
# WARNING: this app is a deliberately vulnerable training target. Install it
# only on an isolated VM. See SECURITY_LAB.md.

set -euo pipefail

APPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE=amberstream
UNIT="/etc/systemd/system/${SERVICE}.service"
ENV_FILE="${APPDIR}/deploy/amberstream.env"
RUN_USER="${SUDO_USER:-$USER}"
RUN_GROUP="$(id -gn "$RUN_USER")"

if [[ "$RUN_USER" == "root" ]]; then
    echo "Run this as your normal desktop user, not root. It calls sudo where needed." >&2
    exit 1
fi

echo "==> AmberStream lab install"
echo "    app dir:  $APPDIR"
echo "    run as:   $RUN_USER:$RUN_GROUP"
echo

# --- 0. Repair what a Windows round-trip breaks --------------------------
# These files are authored on Windows and usually reach the VM through a shared
# folder, a zip, or a git checkout with core.autocrlf=true. Two things get lost
# on the way: the executable bit (systemd then fails with status=203/EXEC) and
# the line endings (a CRLF shebang makes the kernel look for an interpreter
# literally named "bash\r"). Both are silent until the service refuses to
# start, so repair them here rather than leaving you to diagnose it.
echo "==> Checking file integrity"
for f in "${APPDIR}/requirements.txt" "${APPDIR}/wsgi.py" "${APPDIR}/app.py" \
         "${APPDIR}/deploy/start.sh" "${APPDIR}/deploy/amberstream.service" \
         "${APPDIR}/deploy/amberstream.env.example"; do
    if [[ ! -f "$f" ]]; then
        echo "    missing required file: $f" >&2
        exit 1
    fi
done

# Stripping CR unconditionally rather than testing for it first: `tr -d` is a
# no-op on a file that is already LF, and detecting CR portably is fiddlier
# than just doing the work.
for f in "${APPDIR}/deploy/start.sh" "${APPDIR}/deploy/uninstall.sh" \
         "${APPDIR}/deploy/amberstream.service"; do
    [[ -f "$f" ]] || continue
    before="$(wc -c < "$f")"
    tmp="$(mktemp)"
    tr -d '\r' < "$f" > "$tmp" && mv "$tmp" "$f"
    after="$(wc -c < "$f")"
    if [[ "$before" != "$after" ]]; then
        echo "    converted CRLF to LF: $(basename "$f")"
    fi
done

chmod +x "${APPDIR}/deploy/start.sh"
[[ -f "${APPDIR}/deploy/uninstall.sh" ]] && chmod +x "${APPDIR}/deploy/uninstall.sh"
echo "    start.sh present and executable"

# --- 1. System packages -------------------------------------------------
# Ubuntu 24.04 enforces PEP 668, so a virtualenv is required rather than
# optional, and python3-venv is not on the desktop image by default.
echo "==> Installing system packages (sudo)"
if ! sudo apt-get update -qq; then
    cat >&2 <<'OFFLINE'
    apt-get update failed - this VM appears to have no route to the archives.

    A host-only lab network has no internet. Either:
      * attach a NAT adapter temporarily, run this script, then detach it; or
      * run this script once on a VM that does have internet and clone that
        image - .venv/ and the installed packages travel with it.
OFFLINE
    exit 1
fi
# python3          the interpreter itself (present on the desktop image, but
#                  not on every minimal or server variant)
# python3-venv     needed to create the virtualenv; NOT installed by default
# python3-pip      needed to install the dependencies into it
# iproute2         provides `ip`, which start.sh uses to find this VM's address
sudo apt-get install -y -qq python3 python3-venv python3-pip iproute2

# app.py imports datetime.UTC, which does not exist before Python 3.11, so an
# older base image fails at import with a confusing ImportError. Ubuntu 24.04
# ships 3.12 and is fine; check anyway so a wrong base image says so plainly.
PY_VER="$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
    echo "    Python ${PY_VER} is too old - this app needs 3.11 or newer." >&2
    echo "    Ubuntu 24.04 ships 3.12. Check the base image for this VM." >&2
    exit 1
fi
echo "    python3 ${PY_VER}, venv and pip installed"

# --- 2. Virtualenv ------------------------------------------------------
echo "==> Creating virtualenv at ${APPDIR}/.venv"
if [[ ! -x "${APPDIR}/.venv/bin/python" ]]; then
    python3 -m venv "${APPDIR}/.venv"
fi
if ! "${APPDIR}/.venv/bin/pip" install --quiet --upgrade pip; then
    echo "    pip could not reach PyPI. See the offline note above." >&2
    exit 1
fi
"${APPDIR}/.venv/bin/pip" install --quiet -r "${APPDIR}/requirements.txt"
echo "    $("${APPDIR}/.venv/bin/python" --version), $("${APPDIR}/.venv/bin/gunicorn" --version)"

# --- 3. Config ----------------------------------------------------------
if [[ -f "$ENV_FILE" ]]; then
    echo "==> Keeping existing config: $ENV_FILE"
else
    echo "==> Writing config with a generated SECRET_KEY: $ENV_FILE"
    SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    sed "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|" \
        "${APPDIR}/deploy/amberstream.env.example" > "$ENV_FILE"
    chmod 600 "$ENV_FILE"
fi

# --- 4. Database --------------------------------------------------------
# Created here rather than on first request, so a failure surfaces now and the
# directory ends up owned by the service user.
echo "==> Initialising database"
mkdir -p "${APPDIR}/instance"
(cd "$APPDIR" && "${APPDIR}/.venv/bin/python" -c 'import app' >/dev/null)
echo "    instance/plans.db ready"

# --- 5. systemd unit ----------------------------------------------------
echo "==> Installing systemd unit: $UNIT (sudo)"
sed -e "s|__USER__|${RUN_USER}|g" \
    -e "s|__GROUP__|${RUN_GROUP}|g" \
    -e "s|__APPDIR__|${APPDIR}|g" \
    "${APPDIR}/deploy/amberstream.service" | sudo tee "$UNIT" >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE"

# --- 6. Verify it is actually serving ------------------------------------
# Reporting success because `systemctl start` returned 0 is how you end up with
# a green install and a dead site, so make a real HTTP request before claiming
# anything. BIND_ADDR is usually "auto", so read the chosen address from the
# service log rather than from the config file.
echo "==> Verifying"
BOUND=""
for _ in $(seq 1 15); do
    BOUND="$(journalctl -u "$SERVICE" -n 50 --no-pager 2>/dev/null \
             | grep -oE 'listening on [0-9.]+:[0-9]+' | tail -n1 | cut -d' ' -f3 || true)"
    [[ -n "$BOUND" ]] && break
    sleep 1
done
if [[ -z "$BOUND" ]]; then
    CFG_ADDR="$(grep -E '^BIND_ADDR=' "$ENV_FILE" | cut -d= -f2 | tr -d "'\"")"
    CFG_PORT="$(grep -E '^PORT=' "$ENV_FILE" | cut -d= -f2 | tr -d "'\"")"
    [[ "$CFG_ADDR" == "auto" ]] && CFG_ADDR="127.0.0.1"
    BOUND="${CFG_ADDR}:${CFG_PORT}"
fi

HEALTHY=0
for _ in $(seq 1 15); do
    if "${APPDIR}/.venv/bin/python" -c \
        'import sys, urllib.request; urllib.request.urlopen(sys.argv[1], timeout=2)' \
        "http://${BOUND}/" >/dev/null 2>&1; then
        HEALTHY=1
        break
    fi
    sleep 1
done

if [[ "$HEALTHY" != "1" ]]; then
    echo >&2
    echo "!!  Installed, but nothing is answering on http://${BOUND}/" >&2
    echo "!!  Service status follows:" >&2
    sudo systemctl --no-pager --lines=20 status "$SERVICE" >&2 || true
    exit 1
fi

# --- 7. Report ----------------------------------------------------------
echo "    got a response from http://${BOUND}/"
echo
echo "==> Done. The site is served at:"
echo "      http://${BOUND}/       (admin console: /admin - login admin / admin)"
echo

case "$BOUND" in
    0.0.0.0:*)
        cat >&2 <<'WARN'
!!  Listening on 0.0.0.0 - this deliberately vulnerable app is now reachable on
!!  EVERY interface, including the NAT and bridged adapters. Set BIND_ADDR back
!!  to auto in deploy/amberstream.env and: sudo systemctl restart amberstream
WARN
        ;;
    127.0.0.1:*|localhost:*)
        echo "    Loopback only - reachable from inside this VM."
        echo "    If another machine should reach it, check the network is up:"
        echo "      ip -4 addr show"
        ;;
    *)
        echo "    Reachable from other machines on this network. Confirm that is the"
        echo "    isolated lab network and not a route to anywhere wider - this build"
        echo "    ships a live stored-XSS hole and a default admin / admin login."
        if command -v ufw >/dev/null 2>&1 && sudo ufw status 2>/dev/null | grep -q "^Status: active"; then
            echo
            echo "!!  ufw is active, so the port is probably blocked. Allow it from the"
            echo "!!  lab network only - substitute your own subnet:"
            echo "      sudo ufw allow from <lab-subnet>/24 to any port ${BOUND##*:} proto tcp"
        fi
        ;;
esac
echo
echo "    Logs:     journalctl -u ${SERVICE} -f"
echo "    Restart:  sudo systemctl restart ${SERVICE}"
echo "    Remove:   bash deploy/uninstall.sh"
