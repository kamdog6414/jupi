#!/bin/bash
# JUPI trial guard v4 (2026-11-25). No reboot or controller/driver operation.
# Compatible commands/conf and boot filenames: arm, check, revert, status.
# Pre-commit failures retain TRIAL; verified terminal receipts reconcile cleanup.
# Real media power-loss consistency is a separate qualification from these checks.
set -uo pipefail
umask 077
CONF=${JUPI_TRIAL_CONF:-/etc/jupi-trial/conf}
if [ -e "$CONF" ] || [ -L "$CONF" ]; then
  [ -f "$CONF" ] && [ ! -L "$CONF" ] || { echo 'unsafe configuration file' >&2; exit 1; }
  read -r conf_owner conf_mode < <(stat -c '%u %a' -- "$CONF")
  [ "$conf_owner" = 0 ] && (( (8#$conf_mode & 022) == 0 )) || { echo 'configuration must be root-owned and not group/other writable' >&2; exit 1; }
  # Trusted administrator configuration, never data from the boot volume.
  # shellcheck disable=SC1090
  . "$CONF"
fi
LABEL=${JUPI_TRIAL_LABEL:-}
MNT=${JUPI_TRIAL_MNT:-/run/jupi-trial/boot}
PROC_VERSION=${JUPI_TRIAL_PROC_VERSION:-/proc/version}
BOOT_ID_FILE=${JUPI_TRIAL_BOOT_ID_FILE:-/proc/sys/kernel/random/boot_id}
HEALTH_MIN=${HEALTH_MIN:-15}
BAD_LIMIT=${BAD_LIMIT:-3}
ROACH_IP=${ROACH_IP:-192.0.2.3}
LOG=${JUPI_TRIAL_LOG:-/var/log/jupi-trial.log}
SLEEP=${JUPI_TRIAL_SLEEP:-60}
LOCK=${JUPI_TRIAL_LOCK:-/run/jupi-trial/control.lock}
NOMOUNT=${JUPI_TRIAL_NOMOUNT:-0}
OWN_MOUNT=0
RESTORE_RO=0
EXPECTED_DEV=''
TEMP_FILES=()
TRIAL_TEXT=''
TRIAL_SHA=''
CAND=''; CAND_SHA=''; GOOD=''; GOOD_SHA=''; TAG=''; ARMED_BOOT_ID=''

log() {
  local line; line="$(date '+%F %T %Z') $*"
  printf '%s\n' "$line" >&2
  printf '%s\n' "$line" >> "$LOG" || printf '%s\n' 'warning: trial log append failed' >&2
}
fail() { log "HOLD: $*"; return 1; }
sha() { sha256sum -- "$1" 2>/dev/null | awk '{print $1}'; }
regular() { [ -f "$1" ] && [ ! -L "$1" ]; }
safe_name() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$ ]] &&
    [[ "$1" != . && "$1" != .. && "$1" != *. && "${1,,}" != bzimage && "${1,,}" != trial* ]]
}
safe_hash() { [[ "$1" =~ ^[0-9a-f]{64}$ ]]; }
valid_settings() {
  [[ "$HEALTH_MIN" =~ ^[0-9]+$ && "$BAD_LIMIT" =~ ^[0-9]+$ ]] &&
    (( 10#$HEALTH_MIN >= 1 && 10#$HEALTH_MIN <= 1440 && 10#$BAD_LIMIT >= 1 && 10#$BAD_LIMIT <= 60 )) || return 1
  [[ "$SLEEP" =~ ^[0-9]+([.][0-9]+)?$ ]] || return 1
  [[ "$ROACH_IP" =~ ^[A-Za-z0-9][A-Za-z0-9.:-]*$ ]] || return 1
  [[ "$MNT" = /* && "$LOCK" = /* && "$MNT" != / && "$LOCK" != / ]] || return 1
}
valid_settings || { echo 'invalid trial-guard configuration' >&2; exit 1; }

mount_identity() {
  [ "$NOMOUNT" = 1 ] && return 0
  local source type
  mountpoint -q -- "$MNT" || return 1
  source=$(findmnt -rn -M "$MNT" -o SOURCE) || return 1
  type=$(findmnt -rn -M "$MNT" -o FSTYPE) || return 1
  [ "$type" = vfat ] && [ "$(readlink -f -- "$source")" = "$EXPECTED_DEV" ]
}
mount_stick() {
  local mode=${1:-ro} opts actual_label resolved_dev
  [ "$NOMOUNT" = 1 ] && { [ -d "$MNT" ] && [ ! -L "$MNT" ]; return; }
  [ "$EUID" = 0 ] || { fail 'mount operations require root'; return 1; }
  [[ "$LABEL" =~ ^[A-Za-z0-9_-]{1,11}$ ]] || { fail 'invalid or absent volume label'; return 1; }
  resolved_dev=$(readlink -f -- "${JUPI_TRIAL_DEVICE:-/dev/disk/by-label/$LABEL}") || return 1
  [ -z "$EXPECTED_DEV" ] || [ "$EXPECTED_DEV" = "$resolved_dev" ] || { fail 'declared boot device changed during operation'; return 1; }
  EXPECTED_DEV=$resolved_dev
  [ -b "$EXPECTED_DEV" ] || { fail 'declared boot device absent'; return 1; }
  actual_label=$(blkid -p -s LABEL -o value -- "$EXPECTED_DEV") || return 1
  [ "$actual_label" = "$LABEL" ] || { fail 'boot device label mismatch'; return 1; }
  [ ! -L "$MNT" ] || { fail 'mount path is a symlink'; return 1; }
  mkdir -p -- "$MNT" || return 1
  if mountpoint -q -- "$MNT"; then
    mount_identity || { fail 'mount source or filesystem differs from declared boot device'; return 1; }
    opts=$(findmnt -rn -M "$MNT" -o OPTIONS) || return 1
    if [ "$mode" = rw ] && [[ ",$opts," != *,rw,* ]]; then
      mount -o remount,rw -- "$MNT" || return 1
      [ "$OWN_MOUNT" = 1 ] || RESTORE_RO=1
    fi
  else
    if findmnt -rn -S "$EXPECTED_DEV" >/dev/null; then
      fail 'boot device already mounted elsewhere'; return 1
    fi
    mount -t vfat -o "$mode",nosuid,nodev,noexec,flush -- "$EXPECTED_DEV" "$MNT" || return 1
    OWN_MOUNT=1
  fi
  mount_identity || { fail 'boot mount identity check failed'; return 1; }
}
rw() { mount_stick rw; }
cleanup() {
  local status=$? p
  # Only this process's unique temporary paths and owned mount are touched.
  if [ "$NOMOUNT" = 1 ] || mount_identity; then
    for p in "${TEMP_FILES[@]}"; do [ -e "$p" ] && rm -f -- "$p" 2>/dev/null || :; done
  fi
  if [ "$NOMOUNT" != 1 ]; then
    if [ "$OWN_MOUNT" = 1 ] && mount_identity; then
      umount -- "$MNT" || { log 'owned boot mount could not be unmounted'; [ "$status" != 0 ] || status=1; }
    elif [ "$RESTORE_RO" = 1 ] && mount_identity; then
      mount -o remount,ro -- "$MNT" || { log 'original read-only mount mode could not be restored'; [ "$status" != 0 ] || status=1; }
    fi
  fi
  trap - EXIT
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM HUP

# All commands serialize against one trusted host-side lock, not a FAT lock.
[ ! -L "$LOCK" ] || { fail 'lock file is a symlink'; exit 1; }
mkdir -p -- "${LOCK%/*}" || exit 1
exec 9>"$LOCK" || exit 1
flock -n 9 || { log 'BUSY: another guard operation holds the control lock'; exit 75; }

new_tmp() {
  local name; name=$(mktemp -- "$MNT/.jupi-trial.$1.XXXXXX") || return 1
  TEMP_FILES+=("$name")
  TMP_RESULT=$name
}
same_trial() {
  mount_identity && regular "$MNT/TRIAL" && [ "$(sha "$MNT/TRIAL")" = "$TRIAL_SHA" ]
}
write_atomic() {
  local target=$1 content=$2 stage expected
  [ ! -L "$MNT/$target" ] || return 1
  [ ! -e "$MNT/$target" ] || regular "$MNT/$target" || return 1
  mount_identity || return 1
  [ -z "$TRIAL_SHA" ] || [ "$target" = TRIAL ] || same_trial || return 1
  new_tmp receipt || return 1; stage=$TMP_RESULT
  printf '%s\n' "$content" > "$stage" || return 1
  expected=$(printf '%s\n' "$content" | sha256sum | awk '{print $1}') || return 1
  [ "$(sha "$stage")" = "$expected" ] || return 1
  sync -f "$stage" || return 1
  mount_identity || return 1
  [ -z "$TRIAL_SHA" ] || [ "$target" = TRIAL ] || same_trial || return 1
  mv -T -f -- "$stage" "$MNT/$target" || return 1
  sync -f "$MNT" || return 1
  regular "$MNT/$target" && [ "$(sha "$MNT/$target")" = "$expected" ]
}
stage_image() {
  local source=$1 digest=$2 stage
  regular "$MNT/$source" && [ "$(sha "$MNT/$source")" = "$digest" ] || return 1
  new_tmp image || return 1; stage=$TMP_RESULT
  cp -- "$MNT/$source" "$stage" || return 1
  [ "$(sha "$stage")" = "$digest" ] || return 1
  sync -f "$stage" || return 1
  IMAGE_STAGE=$stage
}
activate_image() {
  local stage=$1 digest=$2
  same_trial || { fail 'trial generation or mount changed before image activation'; return 1; }
  regular "$MNT/bzImage" || return 1
  [ "$(sha "$stage")" = "$digest" ] || return 1
  mv -T -f -- "$stage" "$MNT/bzImage" || return 1
  sync -f "$MNT" || return 1
  regular "$MNT/bzImage" && [ "$(sha "$MNT/bzImage")" = "$digest" ]
}
load_trial() {
  local key value line n=0 count_c=0 count_cs=0 count_g=0 count_gs=0 count_t=0 count_a=0 count_gen=0 count_boot=0
  regular "$MNT/TRIAL" || return 1
  [ "$(stat -c %s -- "$MNT/TRIAL")" -le 4096 ] || return 1
  TRIAL_TEXT=$(cat -- "$MNT/TRIAL") || return 1
  TRIAL_SHA=$(sha "$MNT/TRIAL") || return 1
  [ "$(printf '%s\n' "$TRIAL_TEXT" | sha256sum | awk '{print $1}')" = "$TRIAL_SHA" ] || return 1
  CAND=''; CAND_SHA=''; GOOD=''; GOOD_SHA=''; TAG=''; ARMED_BOOT_ID=''
  while IFS= read -r line || [ -n "$line" ]; do
    n=$((n+1)); [[ "$line" = *=* ]] || return 1
    key=${line%%=*}; value=${line#*=}
    case "$key" in
      cand_file) CAND=$value; count_c=$((count_c+1));;
      cand_sha) CAND_SHA=$value; count_cs=$((count_cs+1));;
      good_file) GOOD=$value; count_g=$((count_g+1));;
      good_sha) GOOD_SHA=$value; count_gs=$((count_gs+1));;
      cand_tag) TAG=$value; count_t=$((count_t+1));;
      armed) [[ -n "$value" && ${#value} -le 100 ]] || return 1; count_a=$((count_a+1));;
      generation) [[ "$value" =~ ^[0-9a-f-]{36}$ ]] || return 1; count_gen=$((count_gen+1));;
      armed_boot_id) [[ "$value" =~ ^[0-9a-f-]{36}$ ]] || return 1; ARMED_BOOT_ID=$value; count_boot=$((count_boot+1));;
      *) return 1;;
    esac
  done <<< "$TRIAL_TEXT"
  (( count_c==1 && count_cs==1 && count_g==1 && count_gs==1 && count_t==1 && count_a==1 && count_gen<=1 && count_boot<=1 && n<=8 )) || return 1
  safe_name "$CAND" && safe_name "$GOOD" && [ "${CAND,,}" != "${GOOD,,}" ] &&
    safe_hash "$CAND_SHA" && safe_hash "$GOOD_SHA" && [[ "$TAG" =~ ^[A-Za-z0-9._+-]{1,80}$ ]] && same_trial
}
pending_cleanup() {
  same_trial || return 1
  rm -f -- "$MNT/TRIAL-BOOTS" "$MNT/TRIAL-BOOT-ID" || return 1
  # TRIAL is removed last; a terminal receipt can reconcile interrupted cleanup.
  rm -f -- "$MNT/TRIAL" || return 1
  sync -f "$MNT"
}
receipt_matches() {
  local result=$1 text prefix body recorded expected
  regular "$MNT/TRIAL-$result" || return 1
  [ "$(stat -c %s -- "$MNT/TRIAL-$result")" -le 8192 ] || return 1
  text=$(cat -- "$MNT/TRIAL-$result") || return 1
  [[ "$text" = *$'\nreceipt_sha256='* ]] || return 1
  body=${text%$'\n'receipt_sha256=*}
  recorded=${text##*$'\n'receipt_sha256=}
  safe_hash "$recorded" || return 1
  expected=$(printf '%s\n' "$body" | sha256sum | awk '{print $1}') || return 1
  [ "$recorded" = "$expected" ] || return 1
  prefix=$(printf '%s\nresult=%s\n' "$TRIAL_TEXT" "$result")
  [[ "$body" = "$prefix"$'\n'* ]]
}
seal_receipt_text() {
  local body=$1 digest
  digest=$(printf '%s\n' "$body" | sha256sum | awk '{print $1}') || return 1
  printf '%s\nreceipt_sha256=%s' "$body" "$digest"
}
reconcile_terminal() {
  local result hash
  for result in PASSED REVERTED; do
    receipt_matches "$result" || continue
    hash=$GOOD_SHA; [ "$result" != PASSED ] || hash=$CAND_SHA
    regular "$MNT/bzImage" && [ "$(sha "$MNT/bzImage")" = "$hash" ] || { fail 'terminal receipt and selected image disagree'; return 1; }
    sync -f "$MNT/TRIAL-$result" && sync -f "$MNT" && pending_cleanup || return 1
    log "RECONCILED: durable $result receipt; pending-state cleanup completed"
    return 0
  done
  return 2
}
put_good_back() {
  local reason=$1 stage result observed_boot
  rw && same_trial || return 1
  stage_image "$GOOD" "$GOOD_SHA" || { fail 'known-good image missing, changed or unstaged'; return 1; }
  stage=$IMAGE_STAGE
  activate_image "$stage" "$GOOD_SHA" || { fail 'known-good image activation failed; pending trial retained'; return 1; }
  observed_boot=$(cat -- "$BOOT_ID_FILE" 2>/dev/null) || observed_boot=UNKNOWN
  [[ "$observed_boot" =~ ^[0-9a-f-]{36}$ ]] || observed_boot=UNKNOWN
  result=$(printf '%s\nresult=REVERTED\nreason=%s\nwhen=%s\nobserved_boot_id=%s' "$TRIAL_TEXT" "$reason" "$(date '+%F %T %Z')" "$observed_boot")
  result=$(seal_receipt_text "$result") || return 1
  same_trial && write_atomic TRIAL-REVERTED "$result" || { fail 'revert receipt commit failed; pending trial retained'; return 1; }
  pending_cleanup || { fail 'revert committed but pending-state cleanup incomplete'; return 1; }
  log "REVERTED: known-good image restored ($GOOD_SHA); reason: $reason; no reboot performed"
}
healthy() {
  local kernel_log
  ip -4 addr show eth0 2>/dev/null | grep -q 'inet ' || { log 'HEALTH: no eth0 IPv4'; return 1; }
  ping -c1 -W3 "$ROACH_IP" >/dev/null 2>&1 || { log 'HEALTH: configured peer unavailable'; return 1; }
  systemctl is-active --quiet sshd || { log 'HEALTH: sshd inactive'; return 1; }
  kernel_log=$(dmesg 2>/dev/null) || { log 'HEALTH: kernel log unreadable'; return 1; }
  # Preserve the existing conservative whole-boot fault policy. No old/new
  # fault filtering or GPU/radio recovery is silently introduced here.
  if grep -qiE 'GPU (hang|recovery failed)|ring .* timeout|asic.*init failed|BUG:|Oops' <<< "$kernel_log"; then
    log 'HEALTH: kernel fault pattern present in whole-boot log'; return 1
  fi
}
cmd_arm() {
  [ $# -eq 5 ] || { echo 'usage: arm CAND CAND_SHA GOOD GOOD_SHA VERSION_TAG' >&2; return 2; }
  safe_name "$1" && safe_hash "$2" && safe_name "$3" && safe_hash "$4" && [ "${1,,}" != "${3,,}" ] &&
    [[ "$5" =~ ^[A-Za-z0-9._+-]{1,80}$ ]] || { fail 'invalid arm names, hashes or version tag'; return 1; }
  local armed_boot
  armed_boot=$(cat -- "$BOOT_ID_FILE") || return 1
  [[ "$armed_boot" =~ ^[0-9a-f-]{36}$ ]] || { fail 'invalid live boot ID while arming'; return 1; }
  mount_stick rw || return 1
  [ ! -e "$MNT/TRIAL" ] && [ ! -L "$MNT/TRIAL" ] || { fail 'a pending trial already exists'; return 1; }
  regular "$MNT/bzImage" && [ "$(sha "$MNT/bzImage")" = "$4" ] || { fail 'selected image is not the declared known-good image'; return 1; }
  regular "$MNT/$3" && [ "$(sha "$MNT/$3")" = "$4" ] || { fail 'known-good copy differs'; return 1; }
  stage_image "$1" "$2" || { fail 'candidate staging failed before activation'; return 1; }
  local stage=$IMAGE_STAGE generation text
  generation=$(cat /proc/sys/kernel/random/uuid) || return 1
  text=$(printf 'cand_file=%s\ncand_sha=%s\ngood_file=%s\ngood_sha=%s\ncand_tag=%s\narmed=%s\ngeneration=%s\narmed_boot_id=%s' "$1" "$2" "$3" "$4" "$5" "$(date '+%F %T %Z')" "$generation" "$armed_boot")
  write_atomic TRIAL-BOOTS 0 || { fail 'initial boot counter commit failed'; return 1; }
  rm -f -- "$MNT/TRIAL-BOOT-ID" || return 1
  write_atomic TRIAL "$text" || { fail 'pending trial commit failed before activation'; return 1; }
  load_trial || return 1
  activate_image "$stage" "$2" || { fail 'candidate activation failed; pending trial retained'; return 1; }
  log "ARMED: selected $CAND ($CAND_SHA); known-good copy retained; no reboot performed"
}
cmd_check() {
  [ ! -e "${JUPI_TRIAL_DISABLE:-/etc/jupi-trial/DISABLE}" ] || { log 'DISABLE present: no boot-volume access'; return 0; }
  # An internally booted computer normally runs with its removable boot volume
  # absent. Only this exact absence is a clean CHECK skip, never a trial PASS.
  # A dangling label entry, invalid config, explicit device error or wrong mount
  # still enters mount_stick and fails closed. arm/revert/status never skip.
  if [ "$NOMOUNT" != 1 ] && [ -z "${JUPI_TRIAL_DEVICE:-}" ] &&
     [[ "$LABEL" =~ ^[A-Za-z0-9_-]{1,11}$ ]] &&
     [ ! -e "/dev/disk/by-label/$LABEL" ] && [ ! -L "/dev/disk/by-label/$LABEL" ] &&
     [ ! -L "$MNT" ] && ! mountpoint -q -- "$MNT"; then
    log 'SKIP_NO_MEDIA: no trial inspected or approved; configured removable boot volume absent'
    return 0
  fi
  mount_stick ro || return 1
  [ ! -e "$MNT/TRIAL" ] && [ ! -L "$MNT/TRIAL" ] && return 0
  load_trial || { fail 'invalid pending trial'; return 1; }
  [ -n "$ARMED_BOOT_ID" ] || { fail 'legacy trial lacks arm boot identity; explicit review/revert required'; return 1; }
  local boot_id
  boot_id=$(cat -- "$BOOT_ID_FILE") || return 1
  [[ "$boot_id" =~ ^[0-9a-f-]{36}$ ]] || { fail 'invalid live boot ID'; return 1; }
  if [ "$boot_id" = "$ARMED_BOOT_ID" ]; then
    regular "$MNT/bzImage" && [ "$(sha "$MNT/bzImage")" = "$CAND_SHA" ] || { fail 'armed trial is not selected while awaiting new boot'; return 1; }
    log 'WAIT_NEW_BOOT: trial armed on this kernel boot; no health qualification or PASS performed'
    return 0
  fi
  rw && same_trial || return 1
  local reconciled
  reconcile_terminal; reconciled=$?
  [ "$reconciled" = 2 ] || return "$reconciled"
  if ! grep -qF -- "$TAG" "$PROC_VERSION"; then
    put_good_back 'booted without trial kernel (rescue/known-good path)'; return
  fi
  local selected
  selected=$(sha "$MNT/bzImage") || return 1
  if [ "$selected" = "$GOOD_SHA" ]; then
    put_good_back 'selected image already restored before qualification'; return
  fi
  [ "$selected" = "$CAND_SHA" ] || { fail 'selected image differs from trial candidate'; return 1; }
  local boots=0 prior_id='' counter_identity='' counter mirror=0 record body recorded
  if [ -e "$MNT/TRIAL-BOOTS" ]; then
    regular "$MNT/TRIAL-BOOTS" || return 1
    counter=$(cat -- "$MNT/TRIAL-BOOTS") || return 1
    [[ "$counter" =~ ^[0-9]{1,4}$ ]] || { fail 'invalid boot counter'; return 1; }
    mirror=$((10#$counter)); boots=$mirror
  fi
  if regular "$MNT/TRIAL-BOOT-ID"; then
    [ "$(stat -c %s -- "$MNT/TRIAL-BOOT-ID")" -le 1024 ] || return 1
    record=$(cat -- "$MNT/TRIAL-BOOT-ID") || return 1
    [[ "$record" = *$'\nreceipt_sha256='* ]] || { fail 'unsealed boot counter'; return 1; }
    body=${record%$'\n'receipt_sha256=*}; recorded=${record##*$'\n'receipt_sha256=}
    safe_hash "$recorded" && [ "$recorded" = "$(printf '%s\n' "$body" | sha256sum | awk '{print $1}')" ] || { fail 'boot counter content seal differs'; return 1; }
    [ "$(printf '%s\n' "$body" | wc -l)" -eq 3 ] || return 1
    counter_identity=$(sed -n 's/^trial_sha=//p' <<< "$body")
    prior_id=$(sed -n 's/^boot_id=//p' <<< "$body")
    counter=$(sed -n 's/^boots=//p' <<< "$body")
    [ "$counter_identity" = "$TRIAL_SHA" ] || { fail 'boot counter belongs to a different trial'; return 1; }
    [[ "$prior_id" =~ ^[0-9a-f-]{36}$ ]] || return 1
    [[ "$counter" =~ ^[1-9][0-9]{0,3}$ ]] || return 1
    boots=$((10#$counter))
    [ "$mirror" -eq "$boots" ] || { fail 'boot counter mirror differs from authoritative sealed record'; return 1; }
  elif [ "$mirror" -gt 0 ]; then
    fail 'legacy nonzero counter has no boot identity; explicit review/revert required'; return 1
  fi
  if [ "$prior_id" != "$boot_id" ]; then boots=$((boots+1)); fi
  [ "$boots" -gt 0 ] || boots=1
  # Never overwrite the first observed boot ID before deciding that this is a
  # forbidden second boot. The ID and count otherwise commit in ONE record.
  [ "$boots" -le 1 ] || { put_good_back 'trial reached a second kernel boot without passing'; return; }
  record=$(seal_receipt_text "$(printf 'trial_sha=%s\nboot_id=%s\nboots=%s' "$TRIAL_SHA" "$boot_id" "$boots")") || return 1
  write_atomic TRIAL-BOOT-ID "$record" && write_atomic TRIAL-BOOTS "$boots" || return 1
  log "trial boot $boots on $TAG: health window $HEALTH_MIN checks"
  local good=0 bad=0 result
  while [ "$good" -lt "$HEALTH_MIN" ]; do
    sleep "$SLEEP" || return 1
    same_trial || { fail 'trial generation or mount changed during health window'; return 1; }
    if healthy; then good=$((good+1)); bad=0; else bad=$((bad+1)); good=0; fi
    [ "$bad" -lt "$BAD_LIMIT" ] || { put_good_back "health failed $bad consecutive checks"; return; }
  done
  rw && same_trial || return 1
  regular "$MNT/$GOOD" && [ "$(sha "$MNT/$GOOD")" = "$GOOD_SHA" ] &&
    regular "$MNT/$CAND" && [ "$(sha "$MNT/$CAND")" = "$CAND_SHA" ] &&
    regular "$MNT/bzImage" && [ "$(sha "$MNT/bzImage")" = "$CAND_SHA" ] || { fail 'image identity/recovery copy changed before PASS'; return 1; }
  result=$(printf '%s\nresult=PASSED\nwhen=%s\nobserved_boot_id=%s' "$TRIAL_TEXT" "$(date '+%F %T %Z')" "$boot_id")
  result=$(seal_receipt_text "$result") || return 1
  write_atomic TRIAL-PASSED "$result" || { fail 'PASS receipt commit failed; pending trial retained'; return 1; }
  pending_cleanup || { fail 'PASS committed but pending-state cleanup incomplete'; return 1; }
  log "PASSED: $TAG health and image identities verified; candidate remains selected"
}
cmd_revert() {
  mount_stick ro || return 1
  [ ! -e "$MNT/TRIAL" ] && [ ! -L "$MNT/TRIAL" ] && { log 'no pending trial'; return 0; }
  load_trial || { fail 'invalid pending trial'; return 1; }
  put_good_back 'manual revert'
}
cmd_status() {
  mount_stick ro || return 1
  local f
  for f in TRIAL TRIAL-BOOTS TRIAL-BOOT-ID TRIAL-PASSED TRIAL-REVERTED; do
    if regular "$MNT/$f"; then printf '== %s\n' "$f"; cat -- "$MNT/$f" || return 1; fi
  done
  printf 'guard_version=4\n'
  local selected
  regular "$MNT/bzImage" || { fail 'selected image is absent or nonregular'; return 1; }
  selected=$(sha "$MNT/bzImage") || return 1
  safe_hash "$selected" || return 1
  printf 'selected_bzImage_sha256=%s\n' "$selected"
}
case "${1:-}" in
  arm) shift; cmd_arm "$@";;
  check) cmd_check;;
  revert) cmd_revert;;
  status) cmd_status;;
  *) echo 'usage: jupi-trial-guard.sh arm|check|revert|status' >&2; exit 2;;
esac
