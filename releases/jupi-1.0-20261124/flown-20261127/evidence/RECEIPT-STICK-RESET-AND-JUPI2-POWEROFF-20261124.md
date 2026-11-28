# RECEIPT: both sticks reset to pidfsfix escape kernel; JUPI 2 clean shutdown for stickless test
Tue Nov 24 2026. Authorized by pt3889u ("Do it") covering stick reset, JUPI 2 shutdown, and later JUPI 1 shutdown. This receipt is the first two only: JUPI 1 was left running. - groku
No payloads.ini, network, SDIO/Wi-Fi/BT, or musegadget changes. Guard status was not run. JUPI 1 was not shut down.

## 1. Stick reset (19:25:15–19:25:41 PST)
On both sticks, bzImage.jupi-1.0 was already present and hash-identical to the live bzImage (a06fdd7a), so it was left alone. Only bzImage was replaced: copy of bzImage.pidfsfix-20261120 staged as bzImage.reset-tmp, hashed, atomically renamed over bzImage, unmounted, remounted read-only, re-hashed, unmounted clean. Initramfs, TRIAL-PASSED, payloads, and every other file unchanged (per-file sha before vs after: only bzImage changed).

| Stick | File | Before | After |
|---|---|---|---|
| JUPI 2 PS4PROBIN | bzImage | a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e (jupi-1.0) | 0bd2726640d571c1c28fad7a721ba7db65e04472adcb7f7674312ecf9d72b289 (pidfsfix) |
| JUPI 2 PS4PROBIN | bzImage.jupi-1.0 | a06fdd7a...2b8e (already present, left alone) | same |
| JUPI 2 PS4PROBIN | bzImage.pidfsfix-20261120 | 0bd27266...b289 | same |
| JUPI 2 PS4PROBIN | initramfs.cpio.gz | 53dfd78b1402caf05568968b6ba5bf37c8cb8f773fb1792f2aedc8736e527cd7 | same |
| JUPI 2 PS4PROBIN | TRIAL-PASSED | 2626a52d38989c2f316d4886cab212325b908092c196536bbffed53fec681d68 | same |
| JUPI 1 PS4BOOT | bzImage | a06fdd7a...2b8e (jupi-1.0) | 0bd27266...b289 (pidfsfix) |
| JUPI 1 PS4BOOT | bzImage.jupi-1.0 | a06fdd7a...2b8e (already present, left alone) | same |
| JUPI 1 PS4BOOT | bzImage.pidfsfix-20261120 | 0bd27266...b289 | same |
| JUPI 1 PS4BOOT | initramfs.cpio.gz | ebfa1fd11c7bbebfae160ea7f9b6454e66fe92013898cac4ccd9211ea034d11d | same |
| JUPI 1 PS4BOOT | TRIAL-PASSED | 15f54734ef064b27022078c6fe9e911eb3591916fb816c5e954ae13fb6f517b7 | same |

Both sticks unmounted cleanly after the write. Full before/after listings: stick-reset-pidfsfix.log. A copy also lives at Roach ~/jupi-kernel-backups-20261124/stick-reset-pidfsfix-20261124/ (the earlier full-tree backups in that folder are the pre-HDD-install snapshot and were not overwritten).

Escape rule now: stick IN = pidfsfix (uname `#1 … Nov 20 16:52:41 PST 2026`). Stick OUT = HDD jupi-1.0 (`#jupi-1.0 … Nov 24 15:26:06 PST 2026`). That also makes uname itself the proof of which path booted.

## 2. JUPI 2 HDD re-verify immediately before poweroff (19:26:03 PST)
/ps4hdd/data/linux/boot:
- bzImage a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e (jupi-1.0)
- initramfs.cpio.gz 53dfd78b1402caf05568968b6ba5bf37c8cb8f773fb1792f2aedc8736e527cd7
- bzImage.prev-f0008d46 f0008d46...7293 kept beside them
- NO bootargs.txt on the HDD (CONFIRMED). Payload will use its built-in default cmdline.
- /data/payloads/linux-1024mb.bin e11da9d2...6646 present (the internal loader copy)
sync completed.

## 3. JUPI 2 clean shutdown (JUPI 1 left running)
- Issued `sudo sync && sudo systemctl poweroff` at 19:26:14 PST. The console itself printed `SHUTDOWN-ISSUED 2026-11-24 19:26:14 PST`.
- SSH no longer answered at 19:26:17 PST. Ping to <lab-ip> down at 19:26:19 PST; ping to <lab-ip> down at 19:26:21 PST. (CONFIRMED from Roach: the Linux network stack is gone. The front-panel light may still take a few seconds to go fully off — Kam should wait for that before pulling the stick or the AC cord.)
- JUPI 1 was still up on `#jupi-1.0` after this (uptime 1 h 12 m). (CONFIRMED)

## 4. Post-boot verify (once SSH answers)
From Roach: ssh jupi2 'bash -s' < ~/groku2/hdd-install-20261124/postboot-verify-jupi2-stickless.sh
(copy also in this receipt folder). Pass: uname `#jupi-1.0 … Nov 24 15:26:06 PST 2026`, root loop0 proroot, no PS4PROBIN/stick in lsblk, HDD bzImage still a06fdd7a, eth0 up, ping Roach <lab-ip> 5/5, dmesg clean, no jupi poll-mode line (Belize, poll stays off).

## 5. Kam's JUPI 2 stickless steps
1. Wait until the JUPI 2 (PS4 Pro) light is fully OFF.
2. PULL THE STICK and keep it handy (it is now the pidfsfix escape).
3. Pull the AC cord for 60 seconds, plug it back in, power on.
4. Start the loader the usual way (out of scope here; kept private).
5. Use the INTERNAL `linux-1024mb.bin` (the one on the PS4's disk, not a USB path). Do not add an auto-start entry.
6. Black screen for 1–3 minutes is normal. Groku will check from Roach the moment SSH answers.
If it hangs or there is no SSH after about 8 minutes: hold power until the light is off, plug the stick back in, power on, start the loader, and use the stick copy (or the internal one with the stick in — USB wins, so you get pidfsfix). Worst case the Pro still boots plain Orbis.
Do not start JUPI 1's test until this one is confirmed.
