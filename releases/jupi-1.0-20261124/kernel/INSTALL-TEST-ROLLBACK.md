# jupi-1.0: per-node install, test and rollback plan (groku, Nov 24 2026, PST)

NOTHING here has been done. Every step that writes to a stick or reboots a node needs Kam's go, per node. I never reboot a JUPI; Kam does the reboot and the payload send.

Image: `artifacts/bzImage-jupi-1.0`, sha256 `a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e`. ONE image for both consoles: the live kernel already serves both, and every new path is gated to the Aeolia chip (JUPI 1, 104d:909e) and off by default. JUPI 2's Belize NIC (104d:90c9) can't enter poll mode (CONFIRMED by PCI IDs today).

## Boot path facts (read-only today, raw FAT read, no mount)
| | JUPI 1 stick PS4BOOT (/dev/sda1) | JUPI 2 stick PS4PROBIN (/dev/sdb1) |
|---|---|---|
| bzImage (live) | 0bd27266...b289 (pidfs, Nov 20) | 0bd27266...b289 (same) |
| bzImage.pidfsfix-20261120 (spare) | 0bd27266...b289 | 0bd27266...b289 |
| bzImage.crashnt-4.7-orig-20261120 | f0008d46...7293 | f0008d46...7293 |
| initramfs.cpio.gz | ebfa1fd1...d11d | 53dfd78b...27cd7 |
| bootargs.txt | absent | absent |
| HDD /ps4hdd/data/linux/boot/bzImage | f0008d46...7293 (original) | f0008d46...7293 (original) |
| payload | linux-1024mb.bin e11da9d2...6646 (Roach <lab-home>/ps4-linux/) | same file also on stick payloads/ |
All CONFIRMED today. /proc/cmdline on both = the payload default: `panic=0 clocksource=tsc consoleblank=0 net.ifnames=0 radeon.dpm=0 amdgpu.dpm=0 drm.debug=0 console=ttyS0,115200n8 console=tty0 video=HDMI-A-1:1920x1080@60`.
Payload search order USB -> HDD /data/linux/boot -> /user/system/boot and bootargs.txt support: OBSERVED (payload strings, Nov 11 receipt). Whether bootargs.txt replaces or appends: UNSOURCED, so the proposed file holds the full default plus the option, no trailing newline.

## Order (recommended)
1. JUPI 2 Stage A (image only). Lowest risk: no option needed, Wi-Fi is a second path if wired drops.
2. JUPI 1 Stage A (image only). The same reboot is the usual cure for the dead Wi-Fi (B2), giving JUPI 1 a second path back before the option test.
3. JUPI 1 Stage B (poll option on), then link-pull tests, soak, Stage C numbers.

## Stage 0: stage the file (Kam go "stage", per node; no boot file touched)
On each stick, as root: mount rw, `cp bzImage-jupi-1.0 bzImage.jupi-1.0`, `sync`, `sha256sum bzImage.jupi-1.0` = a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e, umount. Copy source over the existing Roach/JUPI path as on Nov 20. Write a receipt with before/after listings.

## Stage A: boot the image, options off (Kam go "boot A <node>")
1. On the stick: `cp bzImage.jupi-1.0 bzImage.new && mv bzImage.new bzImage && sync` (bzImage.pidfsfix-20261120 stays as the known-good copy). No bootargs.txt.
2. Kam reboots + resends the payload from Roach.
3. Pass (all):
   - `uname -v` starts `#jupi-1.0 SMP PREEMPT_DYNAMIC Tue Nov 24`; `uname -r` = `6.15.4-crashnt-4.7_no-built-in-fw` (unchanged on purpose); /proc/version shows `(jupi@nikolai)`.
   - New boot id; root /dev/loop0 (JUPI 1 UUID 70dbf870-bcb6-4be9-9fb5-f25c4718b71a; JUPI 2 proroot); SSH via Roach; `systemctl --failed` empty.
   - `/sys/module/sky2/parameters/aeolia_poll_phy` = N and `aeolia_skip_empty_phy_stat` = N; no `jupi:` line in `sudo journalctl -k -b | grep jupi:`.
   - `/proc/pressure` absent; `/sys/kernel/mm/lru_gen/enabled` = 0x0000; `cpuset` listed in /sys/fs/cgroup/cgroup.controllers.
   - IRQ 24 rate unchanged from baseline (JUPI 1 ~3,590/s expected here; JUPI 2 ~12/s); `nr_dying_subsys_pids` 0.
   - JUPI 2: eth0 1000 Mbps full, Wi-Fi up, groku-muse + groku-muse-vk status ok, musegadget active. JUPI 1: musegadget stays held (inactive) - do not start it.
   - Garlic/GPU floors as in JUPI-KERNEL-CGROUP-20261121.md (JUPI 1 gen >= 0.42279 tok/s, prompt >= 8.74361 tok/s, MemAvailable >= 3,748,432 KiB).
4. Any fail -> Rollback R2.

## Stage B: JUPI 1 only, poll option on (Kam go "boot B JUPI 1")
1. Put `artifacts/bootargs.txt.PROPOSED-jupi1-poll` (default + ` sky2.aeolia_poll_phy=1`) in the PS4BOOT root as `bootargs.txt`. Reboot + payload (Kam). Console/HDMI visible, Kam within reach of the cable.
2. Pass (all): /proc/cmdline ends `sky2.aeolia_poll_phy=1`; kernel log has `eth0: jupi: Aeolia PHY poll mode on`; IRQ 24 < 100/s idle (3 x 10 s); CPU 1 softirq < 5% idle; `taskset -c 1` busy loop gets a full core; 1000 Mbps full; ping 100/100 to NIKOLAI <lab-ip>; throughput within 5% of Stage A; no `nobody cared` / `Disabling IRQ` / `receiver hang`; /proc/irq/24/spurious unhandled not growing.
3. Link tests: 5 pulls of 10 s (carrier back expected 1-3 s, SUSPECTED from code), 3 quick pulls < 1 s; IRQ rate stays low after each.
4. 30 min soak with transfer; recheck at 5/15/30 min.
5. If the storm continues with the PHY IRQ masked (R1: IRQ 24 still > 1,000/s, or `Disabling IRQ #24` after ~28 s): delete bootargs.txt (R1 below). Optional Stage B' later: `artifacts/bootargs.txt.PROPOSED-jupi1-fastpath-fallback` (`sky2.aeolia_skip_empty_phy_stat=1`) instead, which only drops one of two MDIO reads per empty IRQ; CPU relief partial and unmeasured.

## Stage C: numbers (JUPI 1)
Codex measure-core replay with CPU 1 in the mask (stock arm 0,1,4,6 = 1.87 GFLOP/s; healthy arm ~26 GFLOP/s); 7-core prime; Garlic floors; dying cgroups. Compare JUPI 2 as reference.

## Abort (go straight to rollback)
Wired link not up 60 s after boot (JUPI 1 has no other path unless Wi-Fi came back); SSH/tailnet lost; IRQ 24 > 1,000/s with poll on; `Disabling IRQ`; link not back within 10 s of replug; oops/hang; GPU or Garlic regression; any boot-audit failure on JUPI 1 (`jupi-system` must still print PASS).

## Rollback (cheapest first; same on both sticks)
- R1 option only: delete bootargs.txt from the stick, reboot + payload. Same image, options off.
- R2 previous kernel: `cp bzImage.pidfsfix-20261120 bzImage.new && mv bzImage.new bzImage` (0bd27266...b289), remove bootargs.txt, reboot + payload. Check `uname -v` = `#1 SMP PREEMPT_DYNAMIC Fri Nov 20 16:52:41 PST 2026`.
- R3 original kernel: `bzImage.crashnt-4.7-orig-20261120` on the stick or HDD /ps4hdd/data/linux/boot/bzImage (f0008d46...7293). Note: original kernel brings the cgroup leak back.
- R4 no network, no console: power-cycle, start the loader; if Linux won't come up, pull the stick and fix it on any computer (plain FAT32), then do the same renames (Nov 20 receipt option B).
- Brick risk: a kernel file and a text file on a USB stick. No firmware, flash, Orbis, SDIO/Wi-Fi/Bluetooth or musegadget change. JUPI 2 network settings untouched.
