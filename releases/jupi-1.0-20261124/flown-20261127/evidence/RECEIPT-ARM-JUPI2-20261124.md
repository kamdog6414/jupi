# RECEIPT: jupi-1.0 trial ARMED on JUPI 2 (groku, Tue Nov 24 2026, PST)
Authorized: pt3867u (Kam: "Let's do it, Stick is back in and you have my go"). Guard: trial guard v2 (sha 15ea6e93...f085).
No reboot, no power-off, no bootargs.txt, JUPI 1 / JUPI 2 network / auto-start entry untouched.

Before (17:17-17:18 PST, stick re-inserted, unmounted, JUPI 2 on HDD backup kernel #2 Mar 14):
- whole sdb1 sha256 05b90ff6c86fe9ed3c5a0313c05719fb909ee6bcbb1734ad8be53ec1c0b08fc1 = identical to the 16:46 PST after-hash (CONFIRMED)
- bzImage 0bd27266...b289 | bzImage.pidfsfix-20261120 0bd27266...b289 | bzImage.jupi-1.0 a06fdd7a...2b8e
- bzImage.crashnt-4.7-orig-20261120 f0008d46...7293 | initramfs 53dfd78b...cd7 | payloads/linux-1024mb.bin e11da9d2...6646

Action 17:18:51 PST: jupi-trial-guard.sh arm bzImage.jupi-1.0 <a06fdd7a...> bzImage.pidfsfix-20261120 <0bd27266...> jupi-1.0  -> rc 0, "ARMED".

After (read-only mount, then unmounted; fsck.vfat -n clean):
- bzImage = a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e (== bzImage.jupi-1.0)
- new file TRIAL sha 2be5fa2b...f851 (cand/good file+sha, cand_tag=jupi-1.0, armed 17:18:50 PST)
- every other file hash unchanged (diff of before/after = exactly: bzImage changed, TRIAL added)
- whole sdb1 sha256 now ff1f62d4574a87b14126938cfab06e271c7db056a8bac67635b7b3f4e9af4d25 (new baseline)
Guard: enabled, inactive (runs at next boot), no DISABLE file, log /var/log/jupi-trial.log has the ARMED line.

Rollback (any time before the restart): sudo /usr/local/sbin/jupi-trial-guard.sh revert  -> good kernel back in bzImage, TRIAL-REVERTED written.
Rollback by hand on any computer: copy bzImage.pidfsfix-20261120 over bzImage on the stick (sha 0bd27266...b289).
Files: jupi2-arm-prehash/before/run/after/posthash.txt
- groku
