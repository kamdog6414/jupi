#!/bin/bash
# jupi-trial-guard.sh — boot-once / auto-revert for a JUPI trial kernel.
# v2 (2026-11-24, pt3861u): idle path is READ-ONLY. With no TRIAL file the stick is mounted ro, read, unmounted.
# The stick is only remounted rw when a trial is armed (arm) or needs PASS/REVERT bookkeeping.
# Kill switch: touch /etc/jupi-trial/DISABLE  -> check does nothing at all.
# authored by Groku.2 (pt3860u design, pt3861u install).
#
# Why: the PS4 Linux payload always loads the fixed name "bzImage" (USB first, then /data/linux/boot).
# It cannot pick a different file by itself. So the revert has to be done from Linux, by whatever kernel
# boots next. This script lives on the Linux root (not on the stick), so it runs under ANY kernel:
# the trial kernel, the old kernel, or the HDD rescue kernel.
#
#   arm      copy the candidate over bzImage on the stick and write TRIAL (one trial).
#   check    run at every boot (systemd). Decides PASS / REVERT. Never reboots, never powers off.
#   revert   put the known-good kernel back on the stick now.
#   status   print the trial state.
#
# Files on the stick root (FAT):  TRIAL  (key=value lines), TRIAL-BOOTS (count),
#   results: TRIAL-PASSED or TRIAL-REVERTED (the TRIAL file is renamed, so it is one-shot).
# A REVERT never deletes the candidate file; it only puts the good bytes back in "bzImage".
set -u
CONF=${JUPI_TRIAL_CONF:-/etc/jupi-trial/conf}
# shellcheck disable=SC1090
[ -r "$CONF" ] && . "$CONF"
LABEL=${JUPI_TRIAL_LABEL:-}                 # PS4BOOT (JUPI 1) or PS4PROBIN (JUPI 2); set in the conf
MNT=${JUPI_TRIAL_MNT:-/run/jupi-trial/boot} # test hook: point at a plain directory and set JUPI_TRIAL_NOMOUNT=1
PROC_VERSION=${JUPI_TRIAL_PROC_VERSION:-/proc/version}
HEALTH_MIN=${HEALTH_MIN:-15}                # healthy minutes needed to PASS
BAD_LIMIT=${BAD_LIMIT:-3}                   # consecutive bad checks (1/min) before REVERT
ROACH_IP=${ROACH_IP:-192.0.2.10}
LOG=${JUPI_TRIAL_LOG:-/var/log/jupi-trial.log}
SLEEP=${JUPI_TRIAL_SLEEP:-60}

log(){ printf '%s %s\n' "$(date '+%F %T %Z')" "$*" | tee -a "$LOG" >&2; }
sha(){ sha256sum "$1" 2>/dev/null | awk '{print $1}'; }

mount_stick(){  # $1 = ro (default) or rw
  local mode=${1:-ro}
  [ "${JUPI_TRIAL_NOMOUNT:-0}" = 1 ] && return 0
  [ -n "$LABEL" ] || { log "no LABEL set"; return 1; }
  local dev=/dev/disk/by-label/$LABEL
  [ -b "$dev" ] || { log "stick $LABEL not present"; return 1; }
  if findmnt -rn -S "$(readlink -f "$dev")" >/dev/null && ! mountpoint -q "$MNT"; then log "stick already mounted elsewhere; refusing"; return 1; fi
  mkdir -p "$MNT"
  if mountpoint -q "$MNT"; then mount -o remount,"$mode" "$MNT"; else mount -t vfat -o "$mode",nosuid,nodev,noexec,flush "$dev" "$MNT"; fi
}
rw(){ mount_stick rw; }
umount_stick(){ [ "${JUPI_TRIAL_NOMOUNT:-0}" = 1 ] && return 0; sync; umount "$MNT" 2>/dev/null; }
get(){ sed -n "s/^$1=//p" "$MNT/TRIAL" 2>/dev/null | head -1; }

put_good_back(){  # $1 = reason
  rw || return 1
  local good good_sha
  good=$(get good_file); good_sha=$(get good_sha)
  [ -f "$MNT/$good" ] && [ "$(sha "$MNT/$good")" = "$good_sha" ] || { log "REVERT BLOCKED: $good missing or hash changed"; return 1; }
  cp "$MNT/$good" "$MNT/bzImage.revert-tmp" && sync
  [ "$(sha "$MNT/bzImage.revert-tmp")" = "$good_sha" ] || { log "REVERT BLOCKED: copy hash mismatch"; rm -f "$MNT/bzImage.revert-tmp"; return 1; }
  mv -f "$MNT/bzImage.revert-tmp" "$MNT/bzImage" && sync
  [ "$(sha "$MNT/bzImage")" = "$good_sha" ] || { log "REVERT FAILED: bzImage hash != good"; return 1; }
  { cat "$MNT/TRIAL"; echo "result=REVERTED"; echo "reason=$1"; echo "when=$(date '+%F %T %Z')"; } > "$MNT/TRIAL-REVERTED"
  rm -f "$MNT/TRIAL" "$MNT/TRIAL-BOOTS"; sync
  log "REVERTED: bzImage is the known-good kernel again ($good_sha). Reason: $1. No reboot done."
}

healthy(){
  ip -4 addr show eth0 2>/dev/null | grep -q 'inet ' || return 1
  ping -c1 -W3 "$ROACH_IP" >/dev/null 2>&1 || return 1
  systemctl is-active --quiet sshd || return 1
  ! dmesg 2>/dev/null | grep -qiE 'GPU (hang|recovery failed)|ring .* timeout|asic.*init failed|BUG:|Oops'
}

cmd_arm(){  # arm <candidate_file> <candidate_sha> <good_file> <good_sha> <candidate_version_tag>
  [ $# -eq 5 ] || { echo "usage: arm CAND CAND_SHA GOOD GOOD_SHA VERSION_TAG"; return 2; }
  mount_stick rw || return 1
  [ -e "$MNT/TRIAL" ] && { log "ARM REFUSED: a trial is already armed"; umount_stick; return 1; }
  [ "$(sha "$MNT/$1")" = "$2" ] || { log "ARM REFUSED: candidate hash"; return 1; }
  [ "$(sha "$MNT/$3")" = "$4" ] || { log "ARM REFUSED: good-copy hash"; return 1; }
  [ "$(sha "$MNT/bzImage")" = "$4" ] || { log "ARM REFUSED: bzImage is not the known-good kernel now"; return 1; }
  printf 'cand_file=%s\ncand_sha=%s\ngood_file=%s\ngood_sha=%s\ncand_tag=%s\narmed=%s\n' "$1" "$2" "$3" "$4" "$5" "$(date '+%F %T %Z')" > "$MNT/TRIAL"; sync
  cp "$MNT/$1" "$MNT/bzImage.arm-tmp" && sync && mv -f "$MNT/bzImage.arm-tmp" "$MNT/bzImage" && sync
  [ "$(sha "$MNT/bzImage")" = "$2" ] || { log "ARM FAILED, reverting"; put_good_back "arm copy failed"; return 1; }
  rm -f "$MNT/TRIAL-PASSED" "$MNT/TRIAL-REVERTED" "$MNT/TRIAL-BOOTS"; sync
  log "ARMED: next payload boot loads $1 ($2). Good copy: $3."
  umount_stick
}

cmd_check(){
  [ -e "${JUPI_TRIAL_DISABLE:-/etc/jupi-trial/DISABLE}" ] && { log "DISABLE present: doing nothing"; return 0; }
  mount_stick ro || return 0
  [ -f "$MNT/TRIAL" ] || { umount_stick; return 0; }   # idle: read-only look, nothing written
  rw || { umount_stick; return 0; }
  local tag boots; tag=$(get cand_tag)
  if ! grep -qF -- "$tag" "$PROC_VERSION"; then
    # We are NOT on the trial kernel (rescue boot from HDD, or old kernel): the trial did not make it.
    put_good_back "booted without the trial kernel (rescue path)"; umount_stick; return 0
  fi
  boots=$(( $(cat "$MNT/TRIAL-BOOTS" 2>/dev/null || echo 0) + 1 )); echo "$boots" > "$MNT/TRIAL-BOOTS"; sync
  if [ "$boots" -gt 1 ]; then
    put_good_back "trial kernel booted $boots times without passing"; umount_stick; return 0
  fi
  log "trial boot 1 on $tag: watching health for $HEALTH_MIN min"
  local good=0 bad=0
  while [ "$good" -lt "$HEALTH_MIN" ]; do
    sleep "$SLEEP"
    if healthy; then good=$((good+1)); bad=0; else bad=$((bad+1)); good=0; log "health check failed ($bad/$BAD_LIMIT)"; fi
    [ "$bad" -ge "$BAD_LIMIT" ] && { put_good_back "unhealthy $bad checks in a row"; umount_stick; return 0; }
  done
  { cat "$MNT/TRIAL"; echo "result=PASSED"; echo "when=$(date '+%F %T %Z')"; } > "$MNT/TRIAL-PASSED"
  rm -f "$MNT/TRIAL" "$MNT/TRIAL-BOOTS"; sync
  log "PASSED: $tag healthy for $HEALTH_MIN min. bzImage stays the trial kernel. Good copy kept on stick."
  umount_stick
}

cmd_revert(){ mount_stick ro || return 1; [ -f "$MNT/TRIAL" ] || { log "no armed trial"; umount_stick; return 0; }; put_good_back "manual revert"; umount_stick; }
cmd_status(){ mount_stick ro || return 1; for f in TRIAL TRIAL-BOOTS TRIAL-PASSED TRIAL-REVERTED; do [ -f "$MNT/$f" ] && { echo "== $f"; cat "$MNT/$f"; }; done; echo "bzImage $(sha "$MNT/bzImage")"; umount_stick; }

case "${1:-}" in arm) shift; cmd_arm "$@";; check) cmd_check;; revert) cmd_revert;; status) cmd_status;; *) echo "usage: $0 arm|check|revert|status"; exit 2;; esac
