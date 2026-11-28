#!/bin/bash
# rollback.sh — remove the trial guard completely (only if no trial is armed). Run with sudo on the node.
set -u
/usr/local/sbin/jupi-trial-guard.sh status 2>/dev/null | grep -q '^== TRIAL$' && { echo "REFUSE: a trial is armed; revert it first"; exit 1; }
systemctl disable --now jupi-trial-guard.service 2>/dev/null
rm -f /etc/systemd/system/jupi-trial-guard.service /usr/local/sbin/jupi-trial-guard.sh
rm -rf /etc/jupi-trial
systemctl daemon-reload
echo REMOVED  # /var/log/jupi-trial.log kept as evidence
