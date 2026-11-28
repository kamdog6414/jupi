# RECEIPT: jupi-1.0 trial ARMED on JUPI 1 + trial guard v3 on both nodes
Tue Nov 24 2026, ~5:55-6:00 PM PST. Authorized by pt3879u ("Are we ready for the Jupi 1 reboot and test"). - groku
NO reboot, NO power-off, payloads.ini untouched, no network config, no JUPI 1 SDIO/Wi-Fi/BT, musegadget untouched.
(JUPI 1 clock is UTC; its guard log lines say GMT. 01:57 GMT = 5:57 PM PST.)

## 1. Guard bug: the real root cause (CORRECTED)
The brief's diagnosis ("reads TRIAL after removing it") was a symptom. Root cause (CONFIRMED, reproduced in a test rig):
- 17:25:57 PST on JUPI 2 someone ran `jupi-trial-guard.sh status` while the 15-min check was running. `status` remounts the stick ro and then UNMOUNTS it (journal: run-jupi-trial-boot.mount Deactivated 17:25:58).
- At 17:39:48 the check wrote TRIAL-PASSED into the empty /run/jupi-trial/boot directory on tmpfs (not the stick), `rm` found nothing, `cat TRIAL` failed, and `umount` failed with 32 -> service status=32.
- RESULT ON JUPI 2 NOW (CONFIRMED, read-only mount 17:51 PST): the stick still has TRIAL + TRIAL-BOOTS=1 and NO TRIAL-PASSED. The log line "PASSED" is true about health but was never recorded on the stick. If JUPI 2 reboots in this state, the guard sees TRIAL + boots=2 and REVERTS bzImage to pidfsfix. See jupi2-guard-install-and-stale-state.txt.
Fix = guard v3 (diff vs v2 is 5 hunks, v2 logic otherwise identical):
 a) status/revert/arm never unmount or remount-ro a mount they did not make (KEEP_MOUNT)
 b) PASS re-mounts rw, checks the stick is really mounted and TRIAL is on it, and writes from cached TRIAL text; otherwise logs "PASS NOT RECORDED" and leaves TRIAL
 c) umount can never fail the service
Test rig (bind-mount "stick", real script, stubs for ip/ping/systemctl/dmesg): v2 reproduces rc=32 + TRIAL-PASSED on tmpfs in both scenarios (status mid-run; forced umount mid-run). v3 rc=0, TRIAL-PASSED on the stick, TRIAL removed, nothing left on tmpfs in both. Regression on v3: idle check writes nothing, arm, manual revert, unhealthy x3 revert, rescue-path revert all pass. bash -n OK. (the real vfat stick was not used in the rig; rig used a bind mount)
Guard sha256:
- v2 (old, kept as /usr/local/sbin/jupi-trial-guard.sh.v2 on both nodes): 15ea6e93b6fb6fae96a74519da752b10fd357ede12bc7e6a0dbb5497b05ef085
- v3 (new, installed on JUPI 1 and JUPI 2): 654951b6839c2c0139fe57ef6782889ba4823f8a44b80331fc85705e9d7a472c
Install incident (mine, fixed in ~1 min): my first install attempt copied an empty file because the source path was wrong; I restored v2 on both nodes from the .v2 copy right away (sha 15ea6e93 verified), then installed v3 after a sha+bash -n gate. No boot happened in between. Services untouched (jupi-trial-guard enabled, inactive; JUPI 2 unit still shows the old "failed" from 17:39).
JUPI 2: script only. Its stick was NOT touched (read-only mount for inspection), not re-armed.

## 2/3. JUPI 1 state and escape path
- Running kernel (CONFIRMED): 6.15.4-crashnt-4.7_no-built-in-fw, uname -v "#1 SMP PREEMPT_DYNAMIC Fri Nov 20 16:52:41 PST 2026" = pidfsfix build; stick bzImage before = 0bd27266 = bzImage.pidfsfix-20261120 (OBSERVED match: build time vs file time; no hash of the running image possible). Up 23h.
- Boot path (CONFIRMED files, OBSERVED behavior): loader start -> auto-start entry (51 B file, sha 89832cc8 unchanged) -> loader (HDD copy /data/payloads/linux-1024mb.bin e11da9d2, same sha as Pro stick) -> loads bzImage + initramfs.cpio.gz from USB first (PS4BOOT), then HDD /data/linux/boot.
- Stick (CONFIRMED): /dev/sda, "Ultra", PS4BOOT sda1 vfat 512M, sda2 psxitarch, sda3 swap. Layout in jupi1-arm-before.txt. Not mounted at rest.
- Known-good copies on stick (CONFIRMED sha): bzImage.pidfsfix-20261120 0bd27266...b289; bzImage.crashnt-4.7-orig-20261120 f0008d46...7293.
- HDD fallback (CONFIRMED sha, read via /ps4hdd): /data/linux/boot/bzImage f0008d46...7293 (original crashnt-4.7, Nov 6) + initramfs.cpio.gz cdeaefdb...1e93 (Nov 17-era, same as stick copy initramfs.before-prime-key-20261117). Root pins match today's JUPI 1 (bootsafety 02-JUPI1-BOOT-CHAIN.md: image size, UUID 70dbf870, jupi sha 3f5d4eee) = CONFIRMED by that receipt.
- Escape path: pull the stick BEFORE starting the loader -> the auto-started loader finds no USB -> loads the HDD pair f0008d46 + cdeaefdb. Design CONFIRMED; the same f0008d46 kernel was booted as escape on JUPI 2 (OBSERVED, JUPI 2 arm receipt: "on HDD backup kernel #2 Mar 14"). Booting JUPI 1 from HDD with the stick pulled has NEVER been run: UNPROVEN on JUPI 1 (bootsafety receipts: usb_absent_startup UNVERIFIED). Last out: PS4 itself always boots plain Orbis; no hardware risk.
- postboot-check.sh location: NOT on either node. Copies: Roach <peer-home>/groku2/jupi-kernel-stage-20261124/postboot-check.sh, NIKOLAI ~/fullcircle-core/jupi-kernel-official-20261124/stage-20261124/postboot-check.sh. Run it with: ssh <node> 'bash -s' < postboot-check.sh
- Guard (CONFIRMED): jupi-trial-guard.service enabled, inactive, conf PS4BOOT / HEALTH_MIN 15 / BAD_LIMIT 3 / ROACH_IP <lab-ip>, no DISABLE file. Health preconditions pass now (eth0 <lab-ip>, ping Roach 1.7 ms, sshd active, no GPU/BUG lines in dmesg).

## 4. ARMED: YES (17:57 PST)
Decision: fallback files exist, are hash-matched, and the same kernel was proven as an escape on JUPI 2; JUPI 1's own HDD-boot is unproven. Armed anyway per the brief's condition (verified good fallback = hashes+pins), flagged for Kam. Undo is one command and free before the reboot.
Command (guard v3): jupi-trial-guard.sh arm bzImage.jupi-1.0 a06fdd7a...2b8e bzImage.pidfsfix-20261120 0bd27266...b289 jupi-1.0  -> rc 0, "ARMED".
Hash before/after (read-only mount, unmounted after): diff of per-file sums = exactly: bzImage 0bd27266... -> a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e (== bzImage.jupi-1.0), TRIAL added (sha 026abfbf...160c). Everything else on the stick and the HDD (payloads.ini, HDD boot pair, payload) byte-identical.
- sda1 whole-partition sha256 before 441e25c9570dda1e58926d1b328974b069bc9be2fa4d4432218e8deb622fa0f1, after 0660f4759cbdbab98b10c767afc4e4771703d9a7cd62523a1ea6c99bf34e2c46 (new baseline). fsck.vfat is not installed on JUPI 1, so no fsck was run.
- TRIAL: cand bzImage.jupi-1.0 a06fdd7a..., good bzImage.pidfsfix-20261120 0bd27266..., tag jupi-1.0, armed 2026-11-25 01:57:18 GMT.

## Undo (before the reboot)
ssh jupi1 'sudo /usr/local/sbin/jupi-trial-guard.sh revert'   -> bzImage back to 0bd27266, TRIAL-REVERTED written
By hand on any computer: copy bzImage.pidfsfix-20261120 over bzImage on the stick (sha 0bd27266...b289), delete TRIAL.
Kill switch: sudo touch /etc/jupi-trial/DISABLE

## Open item on JUPI 2 (NOT done, needs Kam's/parent's go: it writes to JUPI 2's stick)
Finalize the PASS record so a JUPI 2 reboot does not revert: 
ssh jupi2 'sudo mkdir -p /run/gk-fin && sudo mount -t vfat -o rw,nosuid,nodev,noexec /dev/disk/by-label/PS4PROBIN /run/gk-fin && cd /run/gk-fin && { cat TRIAL; echo result=PASSED; echo "when=2026-11-24 17:39:48 PST (recorded late by groku, pt3879u)"; } > TRIAL-PASSED && rm -f TRIAL TRIAL-BOOTS && sync && cd / && sudo umount /run/gk-fin && sudo rmdir /run/gk-fin'
