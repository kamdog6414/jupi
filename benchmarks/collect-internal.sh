#!/bin/bash
# Runs ON ROACH. Collects Roach's own state + JUPI's internal state via ssh.
# This is the cluster measuring itself from inside the island.
OUT=${1:-/tmp/internal-capture}
# JUPI_LAN_IP defaults to an RFC 5737 documentation address (TEST-NET-1).
# Export the real lab JUPI LAN IP before running this collector.
JUPI_LAN_IP="${JUPI_LAN_IP:-192.0.2.52}"
mkdir -p $OUT
{
  echo "COLLECTOR roach $(date -Is)"
  hostname; uptime
  echo "--- LINK TO JUPI ---"
  ping -c 5 -q ${JUPI_LAN_IP} | tail -2
  ip -br link | head -6
  for d in /sys/class/net/*/speed; do echo "$d = $(cat $d 2>/dev/null)"; done
  echo "--- ROACH SENSORS ---"; sensors 2>/dev/null | head -8
  echo "--- ROACH VIEW OF PS4-LINUX STORE ---"; ls -la ~/ps4-linux/ | head -8
} > $OUT/roach-side.txt 2>&1
ssh -o BatchMode=yes -o ConnectTimeout=8 pi@${JUPI_LAN_IP} 'bash -s' < /tmp/jupi-inner.sh > $OUT/jupi-via-roach-ssh.txt 2>&1
echo "COLLECT DONE $(date -Is)" >> $OUT/roach-side.txt
ls -la $OUT
