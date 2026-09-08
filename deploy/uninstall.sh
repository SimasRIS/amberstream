#!/usr/bin/env bash
#
# Stop and remove the AmberStream systemd service.
#
#   bash deploy/uninstall.sh
#
# Leaves the virtualenv, the database and deploy/amberstream.env in place —
# delete those by hand if you want a clean slate.

set -euo pipefail

SERVICE=amberstream

echo "==> Stopping and disabling ${SERVICE} (sudo)"
sudo systemctl disable --now "$SERVICE" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/${SERVICE}.service"
sudo systemctl daemon-reload
echo "==> Removed. Virtualenv, database and config were left in place."
