#!/usr/bin/env bash
# Install + start the API service and the demo simulator timers.
set -euo pipefail
cd "$(dirname "$0")/systemd"
sudo cp smartsharing-*.service smartsharing-*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now smartsharing-api.service
sudo systemctl enable --now smartsharing-demo-accept.timer smartsharing-demo-transfers.timer smartsharing-demo-purchases.timer
systemctl list-timers 'smartsharing-*' --no-pager
