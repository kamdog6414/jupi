#!/bin/bash
# Simulation of jupi-trial-guard.sh on a plain directory (no stick, no mount, no network). Run anywhere.
S=$(cd "$(dirname "$0")" && pwd)/jupi-trial-guard.sh
T=$(mktemp -d); cd "$T" || exit 1; mkdir stick
head -c 4096 /dev/urandom > stick/bzImage.good; head -c 4096 /dev/urandom > stick/bzImage.cand; cp stick/bzImage.good stick/bzImage
G=$(sha256sum stick/bzImage.good|cut -d' ' -f1); C=$(sha256sum stick/bzImage.cand|cut -d' ' -f1)
echo "Linux version 6.15.4 #jupi-1.0 SMP" > pv_cand; echo "Linux version 6.15.4 #1 SMP Fri Nov 20" > pv_old
export JUPI_TRIAL_NOMOUNT=1 JUPI_TRIAL_MNT=$T/stick JUPI_TRIAL_LOG=$T/log JUPI_TRIAL_CONF=/nonexistent JUPI_TRIAL_SLEEP=0 HEALTH_MIN=2
sed 's/^healthy(){/healthy(){ return 0;/' "$S" > s_ok.sh; sed 's/^healthy(){/healthy(){ return 1;/' "$S" > s_bad.sh
state(){ b=$( [ "$(sha256sum stick/bzImage|cut -d' ' -f1)" = "$G" ] && echo GOOD || echo CAND ); echo "$b $(cd stick; ls TRIAL* 2>/dev/null | tr '\n' ' ')"; }
arm(){ bash "$S" arm bzImage.cand "$C" bzImage.good "$G" '#jupi-1.0' 2>/dev/null; }
clean(){ rm -f stick/TRIAL*; cp stick/bzImage.good stick/bzImage; }
pass=0; fail=0; t(){ if [ "$2" = "$3" ]; then echo "PASS $1 -> $3"; pass=$((pass+1)); else echo "FAIL $1: want [$2] got [$3]"; fail=$((fail+1)); fi; }
arm; t "T1 arm puts candidate in bzImage" "CAND TRIAL " "$(state)"
bash "$S" arm bzImage.cand "$C" bzImage.good "$G" '#jupi-1.0' 2>/dev/null; t "T2 second arm refused, state unchanged" "CAND TRIAL " "$(state)"
JUPI_TRIAL_PROC_VERSION=pv_old bash "$S" check 2>/dev/null; t "T3 rescue/old-kernel boot reverts" "GOOD TRIAL-REVERTED " "$(state)"
clean; arm; JUPI_TRIAL_PROC_VERSION=pv_cand bash s_ok.sh check 2>/dev/null; t "T4 healthy trial passes, keeps candidate" "CAND TRIAL-PASSED " "$(state)"
clean; arm; JUPI_TRIAL_PROC_VERSION=pv_cand bash s_bad.sh check 2>/dev/null; t "T5 unhealthy trial reverts" "GOOD TRIAL-REVERTED " "$(state)"
clean; arm; echo 1 > stick/TRIAL-BOOTS; JUPI_TRIAL_PROC_VERSION=pv_cand bash s_ok.sh check 2>/dev/null; t "T6 2nd trial boot without pass reverts" "GOOD TRIAL-REVERTED " "$(state)"
clean; cp stick/bzImage.good good.bak; arm; echo x >> stick/bzImage.good; JUPI_TRIAL_PROC_VERSION=pv_old bash "$S" check 2>/dev/null; t "T7 corrupted good copy: revert blocked, TRIAL kept" "CAND TRIAL " "$(state)"; cp good.bak stick/bzImage.good
clean; JUPI_TRIAL_PROC_VERSION=pv_old bash "$S" check; rc=$?; t "T8 nothing armed: no-op rc0" "GOOD  rc0" "$(state) rc$rc"
cp stick/bzImage.cand stick/bzImage; bash "$S" arm bzImage.cand "$C" bzImage.good "$G" '#jupi-1.0' 2>/dev/null; t "T9 arm refused if bzImage is not the good kernel" "CAND " "$(state)"
clean; touch dis; arm; JUPI_TRIAL_DISABLE=$T/dis JUPI_TRIAL_PROC_VERSION=pv_old bash "$S" check 2>/dev/null; t "T10 DISABLE file: check does nothing" "CAND TRIAL " "$(state)"; clean
before=$(cd stick && ls -l --time-style=+%s.%N | md5sum); JUPI_TRIAL_PROC_VERSION=pv_cand bash "$S" check 2>/dev/null; after=$(cd stick && ls -l --time-style=+%s.%N | md5sum); t "T11 idle check writes nothing" "$before" "$after"
echo "RESULT pass=$pass fail=$fail"; echo "--- guard log"; cat "$T/log"; rm -rf "$T"
