#!/usr/bin/env bash
# setup_worker.sh - turn a fresh Raspberry Pi OS (Bookworm or later) install
# into a PiCase WORKER node. Run it once per SD card / SSD.
#
#   sudo ./setup_worker.sh [--controller-key "ssh-ed25519 AAAA... pi@picase-ctl"]
#
# The same card works in ANY worker slot: on boot the agent reads the slot
# number from the backplane straps and renames the Pi to picase-nodeNN.
set -euo pipefail

CTRL_KEY=""
INSTALL_DIR=/opt/picase
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_USER="${SUDO_USER:-pi}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --controller-key) CTRL_KEY="$2"; shift 2 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option $1"; exit 1 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }
say() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

BOOT=/boot/firmware; [[ -d $BOOT ]] || BOOT=/boot
MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || echo unknown)"
say "Configuring worker on: $MODEL"

say "Installing packages"
apt-get update -qq
apt-get install -y -qq python3-serial python3-gpiozero openssh-server >/dev/null
systemctl enable --now ssh >/dev/null

say "Enabling hardware UART on GPIO14/15"
if command -v raspi-config >/dev/null; then
  raspi-config nonint do_serial_cons 1 || true
  raspi-config nonint do_serial_hw 0  || true
fi
sed -i 's/console=serial0,[0-9]* //' "$BOOT/cmdline.txt"
grep -q '^enable_uart=1' "$BOOT/config.txt" || echo 'enable_uart=1' >>"$BOOT/config.txt"
if [[ "$MODEL" == *"Pi 5"* ]]; then
  grep -q '^usb_max_current_enable=1' "$BOOT/config.txt" || echo 'usb_max_current_enable=1' >>"$BOOT/config.txt"
else
  # Workers don't need Bluetooth: give GPIO14/15 the full PL011 UART
  grep -q '^dtoverlay=disable-bt' "$BOOT/config.txt" || echo 'dtoverlay=disable-bt' >>"$BOOT/config.txt"
  systemctl disable --now hciuart >/dev/null 2>&1 || true
fi
# Workers don't use Wi-Fi - all traffic goes through the controller
grep -q '^dtoverlay=disable-wifi' "$BOOT/config.txt" || echo 'dtoverlay=disable-wifi' >>"$BOOT/config.txt"

say "Installing bus agent"
mkdir -p "$INSTALL_DIR"
cp -r "$SRC_DIR/common" "$SRC_DIR/worker" "$INSTALL_DIR/"
cp "$SRC_DIR/worker/picase-agent.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable picase-agent >/dev/null

if [[ -n "$CTRL_KEY" ]]; then
  say "Authorising the controller's SSH key"
  HOME_DIR="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
  install -d -m 700 -o "$TARGET_USER" -g "$TARGET_USER" "$HOME_DIR/.ssh"
  grep -qxF "$CTRL_KEY" "$HOME_DIR/.ssh/authorized_keys" 2>/dev/null || \
    echo "$CTRL_KEY" >>"$HOME_DIR/.ssh/authorized_keys"
  chown "$TARGET_USER": "$HOME_DIR/.ssh/authorized_keys"; chmod 600 "$HOME_DIR/.ssh/authorized_keys"
fi

say "Done. Power off, then slide this Pi into any free worker slot:"
echo "    sudo poweroff"
