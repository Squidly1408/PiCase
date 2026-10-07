#!/usr/bin/env bash
# install_k3s.sh - OPTIONAL: turn the briefcase into a lightweight Kubernetes
# cluster (k3s). Run on the controller after `casectl status` shows your nodes
# and `casectl adopt N` has been done for each of them.
#
#   ./install_k3s.sh
#
# The controller becomes the k3s server; every online worker joins as an agent.
# New Pis added later: just run this script again - it skips existing nodes.
set -euo pipefail
CTRL_IP=10.42.0.1

if ! command -v k3s >/dev/null; then
  echo "==> Installing k3s server on the controller"
  # cgroup memory is required by k3s on Raspberry Pi OS
  BOOT=/boot/firmware; [[ -d $BOOT ]] || BOOT=/boot
  grep -q cgroup_memory "$BOOT/cmdline.txt" || \
    sudo sed -i '1 s/$/ cgroup_memory=1 cgroup_enable=memory/' "$BOOT/cmdline.txt"
  curl -sfL https://get.k3s.io | sudo sh -s - server \
    --node-ip "$CTRL_IP" --flannel-iface eth0 --write-kubeconfig-mode 644
fi

TOKEN="$(sudo cat /var/lib/rancher/k3s/server/node-token)"
echo "==> Preparing workers (cgroups) and joining them as agents"
casectl run "grep -q cgroup_memory /boot/firmware/cmdline.txt || \
  (sudo sed -i '1 s/\$/ cgroup_memory=1 cgroup_enable=memory/' /boot/firmware/cmdline.txt && echo REBOOT_NEEDED)"
casectl run "command -v k3s >/dev/null || curl -sfL https://get.k3s.io | \
  sudo K3S_URL=https://$CTRL_IP:6443 K3S_TOKEN=$TOKEN sh -s - agent --flannel-iface eth0"
echo "==> Nodes that printed REBOOT_NEEDED: run  casectl reboot <slot>  then re-run this script."
sudo k3s kubectl get nodes -o wide
