#!/usr/bin/env bash
# Demo simulator control: ./ctl.sh status | pause [minutes] | resume | logs [n] | uninstall
set -euo pipefail
T="smartsharing-demo-accept.timer smartsharing-demo-transfers.timer smartsharing-demo-purchases.timer"
S="smartsharing-demo-accept.service smartsharing-demo-transfers.service smartsharing-demo-purchases.service"
case "${1:-status}" in
  status) systemctl list-timers 'smartsharing-*' --no-pager; systemctl is-active smartsharing-api.service || true ;;
  pause)  sudo systemctl stop $T $S
          if [[ -n "${2:-}" ]]; then sudo systemd-run --on-active="${2}min" systemctl start $T; echo "resumes in $2 min"; fi ;;
  resume) sudo systemctl start $T ;;
  logs)   for s in $S; do echo "== $s"; journalctl -u "$s" -n "${2:-15}" --no-pager -o cat; done ;;
  uninstall) sudo systemctl disable --now $T $S; sudo rm -f /etc/systemd/system/smartsharing-demo-*; sudo systemctl daemon-reload ;;
  *) echo "usage: $0 status|pause [min]|resume|logs [n]|uninstall"; exit 1 ;;
esac
