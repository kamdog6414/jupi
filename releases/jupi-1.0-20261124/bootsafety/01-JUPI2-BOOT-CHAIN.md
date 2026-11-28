# JUPI 2 (PS4 Pro) boot chain — from the loader to a running system
Read-only study, 2026-11-24 ~4:00–4:40 PM PST. Groku.2, authorized_by pt3860u.
Grades: CONFIRMED (read from the device/file myself) · OBSERVED (seen in a receipt, log or public source, not re-proven) · SUSPECTED (best explanation, not proven) · UNSOURCED (no evidence found).

## Short answer
- Linux is started on the console with a PS4 Linux loader; how that loader is delivered is out of scope and kept private. You start it yourself on the console. The loader `linux-1024mb.bin` makes the PS4 restart straight into Linux.
- The loader file is on the PS4PROBIN stick in `payloads/` (placed by Groku.2 on Nov 10 at 5:18 PM PST, Kam go pt2286u; CONFIRMED by receipt and the file on the stick).
- There is **no auto-start on JUPI 2**. Nothing boots Linux on its own. CONFIRMED on Nov 24: no auto-start configuration and no `/data/payloads/` existed then.

## Step by step
| # | Step | Evidence | Grade |
|---|---|---|---|
| 0-3 | Power on → stock PS4 system software from the internal HDD. Linux is then started with the loader (out of scope; kept private). The loader `linux-1024mb.bin` (sha `e11da9d2…`, 329,088 B) is read from the stick's `payloads/` folder; there was no internal copy on Nov 24. | file read, stick FAT read | CONFIRMED |
| 4 | The loader ("PS4 Linux Payloads AIO", 1 GiB VRAM variant) loads **each file separately, first match wins**: `/mnt/usb0/X` → `/mnt/usb1/X` → `/data/linux/boot/X` → `/user/system/boot/X`, for X = bzImage, initramfs.cpio.gz, bootargs.txt, vram.txt. bzImage and initramfs are required; bootargs and vram are optional. | path tables in our binary (CONFIRMED). Load logic in the public source ps4boot/ps4-linuxpayloads `linux/main.c` macro `L()` (commit 6ebcc6c8, same family; our build adds the 4th path) | CONFIRMED paths, OBSERVED logic |
| 5 | Today that gives: stick `bzImage` 0bd27266… (the pidfs-fix kernel) and stick `initramfs.cpio.gz` 53dfd78b… There is no bootargs.txt anywhere, so the built-in cmdline is used: `panic=0 clocksource=tsc consoleblank=0 net.ifnames=0 radeon.dpm=0 amdgpu.dpm=0 drm.debug=0 console=ttyS0,115200n8 console=tty0 video=HDMI-A-1:1920x1080@60`. That matches `/proc/cmdline` exactly. No vram.txt, so 1 GiB. | FAT read, HDD ls, /proc/cmdline | CONFIRMED |
| 6 | The loader arms kexec, resets the GPU (and VRAM/IOMMU on Belize), then makes Orbis restart itself and jumps into Linux. | binary strings ("kexec successfully armed", "Resetting GPU", "SceSysCoreReboot"); source `reboot_thread` | OBSERVED |
| 7 | initramfs (`pro_internal` path) unlocks the PS4 user partition (dm-crypt `pro-boot-internal`), loop-mounts `/ps4hdd/home/pro-linux.img` (128 GiB, LABEL proroot), then switch_root → systemd → lightdm/XFCE. | live `lsblk`, `findmnt /` = loop0 | CONFIRMED |
| 8 | Linux never reboots itself into a loop: `panic=0` means a panic **hangs** (it doesn't restart), there is no hardware watchdog, and the self-heal script `jupi-aon-heal` has ALLOW_REBOOT=0 plus a DISABLE file. | /proc/sys/kernel/panic=0, heal.conf | CONFIRMED |

## The rescue copy on the internal HDD
`/ps4hdd/data/linux/boot/` (= `/data/linux/boot` on the PS4) holds bzImage `f0008d46…` (the original crashnt-4.7) and initramfs `53dfd78b…`, the **same initramfs as the stick**. CONFIRMED. These were written Nov 11 at about 4:30 PM PST during the rebuild after the PS4 Initialize (the "Dec 31 1969" dates come from the clock running before NTP). This copy only gets used when there is **no** bzImage on the USB drives.
- Our loader does **not** copy USB files onto the HDD. CONFIRMED: the stick kernel has booted many times since Nov 20 and the HDD still has the older f0008d46. Newer upstream loader builds **do** auto-copy (OBSERVED, upstream README). **Never "upgrade" the loader without checking this, or it will overwrite the rescue copy.**
- **Gap on Nov 24 (closed the same day):** pulling the stick also removed the only copy of the loader, so the HDD rescue kernel could not be reached. The fix was one additive file, an internal loader copy at `/data/payloads/linux-1024mb.bin` with no auto-start entry (04-FAILSAFE-DESIGN.md). Later, JUPI 2 booted jupi-1.0 with the stick out.

## Who placed what (JUPI 2)
| Item | Placed by | When (PST) | Grade |
|---|---|---|---|
| stick `payloads/linux-1024mb.bin`, `bin/README.txt`, first README | Groku.2 (Kam go pt2286u) | Nov 10 5:18 PM | CONFIRMED (RECEIPT-PS4PRO-USB-FAT32-20261111T011856Z.md) |
| HDD `/data/linux/boot` pair, `pro-linux.img` rebuild | Groku.2 (pt2408u) | Nov 11 ~4:30 PM | CONFIRMED (RECEIPT-JUPI2-INTERNAL-REBUILD) |
| stick bzImage 0bd27266 | NIKOLAI pidfs-fix swap (Kam go pt3526u) | Nov 20 5:09 PM | OBSERVED (gaz receipt) |
| stick bzImage.jupi-1.0 (not loaded; wrong name for the loader) | Groku.2 (pt3859u) | Nov 24 | CONFIRMED |

Boots that day (journal): 10:11, 10:18 and 10:26 AM PST. The current boot had been up since 10:26 AM (10:40 AM by the Linux clock, which is wrong before the NTP sync). OBSERVED.

- groku
