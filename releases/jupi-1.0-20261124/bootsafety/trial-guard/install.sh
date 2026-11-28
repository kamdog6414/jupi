#!/bin/bash
# install.sh <jupi1|jupi2>  — additive install of the trial guard, idle. Run with sudo on the node.
set -euo pipefail
N=$1; D=$(cd "$(dirname "$0")" && pwd)
for f in /usr/local/sbin/jupi-trial-guard.sh /etc/systemd/system/jupi-trial-guard.service /etc/jupi-trial; do
  [ -e "$f" ] && { echo "REFUSE: $f exists"; exit 1; }; done
install -m 0755 -o root -g root "$D/jupi-trial-guard.sh" /usr/local/sbin/jupi-trial-guard.sh
install -m 0644 -o root -g root "$D/jupi-trial-guard.service" /etc/systemd/system/jupi-trial-guard.service
install -d -m 0755 /etc/jupi-trial
install -m 0644 "$D/conf.$N" /etc/jupi-trial/conf
touch /var/log/jupi-trial.log; chmod 0644 /var/log/jupi-trial.log
systemctl daemon-reload
systemctl enable jupi-trial-guard.service
sha256sum /usr/local/sbin/jupi-trial-guard.sh /etc/systemd/system/jupi-trial-guard.service /etc/jupi-trial/conf
echo INSTALLED_IDLE
