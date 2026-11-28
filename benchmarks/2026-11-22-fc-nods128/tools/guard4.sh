#!/bin/bash
# guard4: root PID from pidfile. Kills root + all descendants on a new amdgpu ring timeout/reset line, swap > start+256 MiB, or MemAvailable < 1000 MiB.
# Checks every 5 s; logs a dmesg/swap heartbeat every 60 s.
D=${NODS_STABLE:-./stable}; G=$(cat $D/root.pid); exec >> $D/guard.log 2>&1
swu(){ awk '/SwapTotal/{t=$2}/SwapFree/{f=$2}END{print int((t-f)/1024)}' /proc/meminfo; }
bad(){ sudo -n dmesg | grep -cE 'amdgpu.*(ring .*timeout|GPU reset|Recovery|hang)'; }; B0=$(bad); S0=$(swu); mx=$S0; last=0
desc(){ local c; for c in $(pgrep -P $1); do desc $c; echo $c; done; }
echo "$(date +%T) GUARD4 START root=$G cmd=$(tr '\0' ' ' < /proc/$G/cmdline) bad0=$B0 swap0=$S0 cap=$((S0+256))"
while kill -0 $G 2>/dev/null; do
  su=$(swu); m=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo); nb=$(( $(bad)-B0 )); [ $su -gt $mx ] && mx=$su
  if [ $nb -gt 0 ] || [ $su -gt $((S0+256)) ] || [ $m -lt 1000 ]; then echo "$(date +%T) ABORT swapused=$su mem=$m bad_new=$nb"; touch $D/ABORTED; kill -STOP $G; P="$(desc $G) $G"; kill -9 $P; break; fi
  now=$(date +%s); [ $((now-last)) -ge 60 ] && { echo "$(date +%T) hb dmesg_bad_new=$nb swap=$su mem=$m max=$mx"; last=$now; }
  sleep 5
done
echo "$(date +%T) GUARD4 END max_swapused=$mx"
