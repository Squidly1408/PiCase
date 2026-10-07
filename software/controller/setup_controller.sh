#!/usr/bin/env bash
# setup_controller.sh - turn a fresh Raspberry Pi OS (Bookworm or later) install
# into the PiCase CONTROLLER (slot 0).
#
#   sudo ./setup_controller.sh [--wifi "SSID" "PASSWORD"] [--kiosk] [--slots N]
#
# What it does
#   1. Enables the hardware UART on GPIO14/15 for the RS-485 management bus
#   2. Sets up the networks:
#        eth0  -> internal LAN (10.42.0.1/24) with DHCP + NAT for the workers
#        eth1  -> optional USB-Ethernet adapter behind the briefcase RJ45 port
#                 (preferred uplink when a cable is plugged in)
#        wlan0 -> Wi-Fi uplink (used when no cable is plugged in)
#   3. Installs the bus master service, casectl and the dashboard
#   4. (--kiosk) auto-logs in on the monitor and opens the dashboard
set -euo pipefail

WIFI_SSID=""; WIFI_PASS=""; KIOSK=0; SLOTS=15
LAN_CIDR="10.42.0.1/24"
INSTALL_DIR=/opt/picase
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_USER="${SUDO_USER:-pi}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --wifi)  WIFI_SSID="$2"; WIFI_PASS="$3"; shift 3 ;;
    --kiosk) KIOSK=1; shift ;;
    --slots) SLOTS="$2"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown option $1"; exit 1 ;;
  esac
done

[[ $EUID -eq 0 ]] || { echo "run with sudo"; exit 1; }
say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

BOOT=/boot/firmware; [[ -d $BOOT ]] || BOOT=/boot
MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || echo unknown)"
say "Configuring controller on: $MODEL"

# ---------------------------------------------------------------- packages
say "Installing packages"
apt-get update -qq
apt-get install -y -qq python3-serial python3-gpiozero network-manager \
    dnsmasq-base nftables openssh-client >/dev/null

# ---------------------------------------------------------------- UART
say "Enabling hardware UART on GPIO14/15"
if command -v raspi-config >/dev/null; then
  raspi-config nonint do_serial_cons 1 || true   # no login console on the bus
  raspi-config nonint do_serial_hw 0  || true    # but keep the UART enabled
fi
sed -i 's/console=serial0,[0-9]* //' "$BOOT/cmdline.txt"
grep -q '^enable_uart=1' "$BOOT/config.txt" || echo 'enable_uart=1' >>"$BOOT/config.txt"
if [[ "$MODEL" != *"Pi 5"* ]]; then
  # Pi 3/4: give the good PL011 UART to GPIO14/15, keep Bluetooth on the mini UART
  grep -q '^dtoverlay=miniuart-bt' "$BOOT/config.txt" || echo 'dtoverlay=miniuart-bt' >>"$BOOT/config.txt"
else
  # Pi 5 powered through the backplane 5 V pins can't negotiate with a USB-C PSU
  grep -q '^usb_max_current_enable=1' "$BOOT/config.txt" || echo 'usb_max_current_enable=1' >>"$BOOT/config.txt"
fi

# ---------------------------------------------------------------- networking
say "Configuring networks"
systemctl enable --now NetworkManager >/dev/null

# Internal cluster LAN: NetworkManager 'shared' mode = static IP + DHCP + NAT
nmcli -t con show | grep -q '^picase-lan:' && nmcli con delete picase-lan >/dev/null
nmcli con add type ethernet ifname eth0 con-name picase-lan \
  ipv4.method shared ipv4.addresses "$LAN_CIDR" ipv4.never-default yes \
  ipv6.method disabled connection.autoconnect-priority 100 >/dev/null

# Wired uplink through the briefcase RJ45 port (USB-Ethernet adapter = eth1)
nmcli -t con show | grep -q '^picase-uplink-wired:' && nmcli con delete picase-uplink-wired >/dev/null
nmcli con add type ethernet ifname eth1 con-name picase-uplink-wired \
  ipv4.method auto ipv4.route-metric 100 ipv6.route-metric 100 >/dev/null

# Wi-Fi uplink (lower priority than the cable)
if [[ -n "$WIFI_SSID" ]]; then
  nmcli radio wifi on
  nmcli dev wifi rescan >/dev/null 2>&1 || true; sleep 3
  nmcli dev wifi connect "$WIFI_SSID" password "$WIFI_PASS" name picase-uplink-wifi || \
    echo "!! Wi-Fi connect failed - set it later from the dashboard (press w)"
  nmcli con modify picase-uplink-wifi ipv4.route-metric 600 ipv6.route-metric 600 2>/dev/null || true
fi

# ---------------------------------------------------------------- software
say "Installing PiCase software to $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$SRC_DIR/common" "$SRC_DIR/controller" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR"/controller/*.py "$INSTALL_DIR/controller/casectl"
ln -sf "$INSTALL_DIR/controller/casectl" /usr/local/bin/casectl
cat >/usr/local/bin/picase-console <<'EOF'
#!/bin/sh
exec python3 /opt/picase/controller/console.py "$@"
EOF
chmod +x /usr/local/bin/picase-console

getent group picase >/dev/null || groupadd picase
usermod -aG picase "$TARGET_USER"

sed "s/__SLOTS__/$SLOTS/" "$SRC_DIR/controller/picase-master.service" \
  >/etc/systemd/system/picase-master.service
systemctl daemon-reload
systemctl enable picase-master >/dev/null

# SSH key used by `casectl run` / `casectl adopt`
sudo -u "$TARGET_USER" bash -c '[[ -f ~/.ssh/id_ed25519 ]] || ssh-keygen -q -t ed25519 -N "" -f ~/.ssh/id_ed25519'

# ---------------------------------------------------------------- kiosk
if [[ $KIOSK -eq 1 ]]; then
  say "Enabling console auto-login + dashboard on the briefcase monitor"
  raspi-config nonint do_boot_behaviour B2 || true
  PROFILE="$(getent passwd "$TARGET_USER" | cut -d: -f6)/.bash_profile"
  grep -q picase-console "$PROFILE" 2>/dev/null || cat >>"$PROFILE" <<'EOF'
# PiCase: open the dashboard on the briefcase monitor (tty1 only)
if [ "$(tty)" = "/dev/tty1" ]; then picase-console; fi
EOF
  chown "$TARGET_USER": "$PROFILE"
fi

say "Done. Reboot now:  sudo reboot"
echo "After reboot:  casectl status   |   picase-console"
