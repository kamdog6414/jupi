# JUPI 1 (PS4 base/slim) boot chain — why it starts Linux on its own
Read-only study, 2026-11-24 PST. JUPI 1's file times are UTC; they are converted to PST here.

## Short answer
JUPI 1 has an **auto-start entry** for the Linux loader, so the loader runs with no menu and no pick. Codex (ROACH-2) set this up on **Nov 6 at 12:49 AM PST**, and the founder approved the restart test. CONFIRMED by Codex's own report on Roach and by the files on the HDD. Linux is started on the console with a PS4 Linux loader; how that loader is delivered is out of scope and kept private.

## Step by step
| # | Step | Evidence | Grade |
|---|---|---|---|
| 0-2 | Power on → plain PS4 system software; Linux is then started with the loader (out of scope; kept private). The auto-start entry is a 51-byte file on the HDD (sha 89832cc8… per the Codex report). | file read | CONFIRMED file |
| 3 | The entry runs the internal loader `/data/payloads/linux-1024mb.bin` (sha `e11da9d2…`, the same file as on the Pro stick). A marker `/user/temp/linux-1024mbbin.loaded` was last written Nov 23 6:34 PM PST, exactly when that Linux boot started. | find + uptime -s 02:34:28 UTC | CONFIRMED |
| 4 | The same loader search, file by file: USB → HDD. The stick (PS4BOOT sda1) has bzImage `0bd27266…` and initramfs `ebfa1fd1…`; no bootargs or vram anywhere, so the built-in cmdline is used, and it matches /proc/cmdline. | FAT read, /proc/cmdline | CONFIRMED |
| 5 | initramfs root selector `usbroot.sh`: unlock UFS2 → check the image `jupi-linux-2a79fafeb62d61ff.img` (exactly 381,178,347,520 B), UUID 70dbf870…, and the sha of `/usr/local/bin/jupi` = 3f5d4eee… → switch_root. If it fails: fall back to the old USB root on sda2 "psxitarch". If there is no USB either: a BusyBox shell. | field manual; HDD initramfs extracted on Roach /tmp | CONFIRMED pins match today |
| 6 | panic=0, so a bad kernel hangs and doesn't restart. No auto-reboot (no jupi-aon heal config on JUPI 1; the jupi-agent `boot_manager` / `warm_boot_bundle` say "No reboot action" / "never load or execute it"; no kexec binary installed). | grep, /proc/sys/kernel/panic | CONFIRMED |

## The rescue copy on the internal HDD
`/data/linux/boot/`: bzImage `f0008d46…` (the original crashnt-4.7, before the pidfs fix) and initramfs `cdeaefdb…` (Nov 7). I extracted it read-only: its pins (image size, UUID, jupi sha 3f5d4eee) **still match today's JUPI 1**, so with the stick pulled it should land on the same root. CONFIRMED pins; the boot itself is UNPROVEN. Every receipt says `usb_absent_startup: UNVERIFIED`.
- Because the loader copy is **internal** on JUPI 1, pulling the stick still boots Linux: auto-start → loader → no USB bzImage → HDD pair. That is the built-in escape hatch. Design CONFIRMED on Nov 24; since then JUPI 1 has booted jupi-1.0 stickless (see ../flown-20261127/STATUS-20261127.md).
- The rescue kernel f0008d46 has the pidfs bug fixed on Nov 20 (B-list in ANALYSIS.md). It is good enough to get back in and fix the stick; it is not for long-term use.

## How a bad kernel would "loop" on JUPI 1
A bad bzImage on the stick + the auto-start entry = Linux starts at once → hang (black screen, panic=0) → Kam holds power → plain PS4 → the loader starts again → same hang. It **feels** automatic and there seems to be no way out. CONFIRMED mechanism; there is no record of it actually happening on JUPI 1.
**The way out without any tools: pull the stick before starting the loader.** The auto-start entry then boots the HDD rescue pair.

- groku
