# JUPI boot chain

> Public edition, generated from the JUPI as-built scan of 2026-11-10 8:10 AM PST (sha256 `3559b934…`). LAN/tailnet addresses, key paths and full fingerprints are redacted to role placeholders. Times are PST. Full typeset version: [`field-manual/JUPI-Field-Manual.pdf`](field-manual/JUPI-Field-Manual.pdf).

## 2. Origin: the rescue-shell story

JUPI did not start as a plan. It started as a boot that never finished.

### 2.1 The first boot script, and the typo

Kam's first custom boot hook, `fc.sh`, was meant to decrypt the PS4 drive, mount Sony's UFS2
filesystem at `/ps4hdd`, open the stock 50 GiB `linux.img` read-only and lay a writable overlay
from the USB stick over it. Here it is exactly as preserved in rescue checkpoint 02
(sha256 `4c4f902b…2fe6143b`). It is still inside today's initramfs as an inert file:

```
sleep 4;P=/dev/sda27;U=/dev/sdb2;[ -b /dev/sdb27 ]&&P=/dev/sdb27&&U=/dev/sda2
cryptsetup -d <loader key file in initramfs> --cipher aes-xts-plain64 -s 256 --offset 0 --skip 0 create ps4hdd $P
mkdir -p /ps4hdd /ro /rw /newroot && mount -t ufs -o ro,ufstype=ufs2 /dev/mapper/ps4hdd /ps4hdd
losetup -r /dev/loop0 /ps4hss/home/linux.img && mount -t ext4 -o ro,noload /dev/loop0 /ro
                      ^^^^^^^
                      "/ps4hss" -- should be /ps4hdd. The image is never attached.
mount -t ext4 -o rw $U /rw && mkdir -p /rw/u/home /rw/w && mount -t overlay overlay \
      -o lowerdir=/ro,upperdir=/rw/u,workdir=/rw/w /newroot
```

The domino run is mechanical. `losetup` fails on a path that does not exist, so nothing is mounted
on `/ro`. The overlay has no lower layer, so `/newroot` stays empty. The initramfs (`better-initramfs`)
then cannot mount or `switch_root` into `/newroot`. Its `die` path calls `rescueshell`, and the PS4
sits at a BusyBox prompt. *(Inferred from the init and functions.sh in checkpoint 02. The exact
on-screen error is UNKNOWN.)*

> **A second hazard was hiding in the same log.** Checkpoint 01's kernel log shows
> `/dev/sdb2: Can't lookup blockdev` at **5.45 s**, while Sony's USB-SATA bridge (the internal HDD)
> did not enumerate until **6.65 s** (after an `error -110` retry). `fc.sh` slept only 4 s, so at
> the moment it chose `P`/`U` the internal disk did not exist yet. Even with the typo fixed, that
> boot was racing the hardware. *(Observed timings, inferred consequence.)*

### 2.2 The rescue-shell records (CP01–CP03)

With no real-time clock inside the initramfs, everything written from the rescue shell is dated
**1 Jan 1970**. Kam's notes were saved on the USB root under `/fullcircle/ps4-rescue-inventory/`.
Fast copies are on Roach in `~/ps4-linux`.

```
 /fullcircle/ps4-rescue-inventory/            (USB sda2, timestamps = 1970, clock not set)
 |-- checkpoint-01/   system.txt  boot-hashes.txt  kernel-log.txt  SHA256SUMS   (02:41 "1970")
 |-- checkpoint-02/   fc.sh  init  functions.sh                    SHA256SUMS   (02:46-02:48)
 `-- checkpoint-03/   initramfs.pre-v3.cpio.gz  initramfs.v3.cpio.gz   SHA256SUMS (04:15-04:31)
 /root/ps4boot-work/  initramfs.original / initramfs.fixed / f.gz, unpacked trees t/ tree/ verify/
```

CP01 captured the rescue environment: kernel `6.15.4-crashnt-4.7`, USB `sda2` mounted
`ro,norecovery` at `/usb`, `PS4BOOT` at `/ps4boot`, and the filesystem list (which already included
`ufs`). The absolute time of CP01–CP03 is **UNKNOWN**. They fall after the USB was prepared
(Nov 5, ~6:01–6:50 PM, real-clock files on the stick) and before the first successful boot
(Nov 5, 11:45 PM). *(Ordering inferred.)*

### 2.3 From rescue shell to Arch, step by step

```
 Nov 5  ~6-7 PM   USB stick prepared (psxitarch image + PS4BOOT kernel/initramfs)
        (1970)    fc.sh boot -> typo + 4 s race -> RESCUE SHELL; CP01..CP03 written by hand
 Nov 5 11:45 PM   Roach sends linux-1024mb.bin (329,088 B) to the PS4 payload port
       11:47 PM   Ethernet returns; OpenSSH 10.6 answers; host key awkaTxgG... first seen
       11:55 PM   Kam confirms: XFCE desktop on the PS4 screen
 Nov 6 12:34 AM   Verified root: loop0 <- /ps4hdd/home/linux.img (stock 50 GiB image) on UFS2
       12:41 AM   Autostart files added to the HDD (/data/linux/boot, payload AutoRun)
     by 1:02 PM   Root is the USB stick (sda2) after a reported MANUAL switch_root: the USB
                  selector died on a syntax error -- "[ -x /newroot/sbin/init }"  (missing "]")
 Nov 6  1:06 PM   CP05: one-byte fix "}" -> "]", 10/10 selector tests, rollback copies x3
        1:21 PM   Restart test boots USB root automatically (boot b00c61e1)
        8:48 PM   FIRST BOOT ON THE JUPI IMAGE: loop0 <- jupi-linux-....img (40 GiB), boot 54f4c94e
        9:13 PM   Disk-only selector activated on both boot copies
        9:16 PM   Image grown online 40 GiB -> 355 GiB
 Nov 7 11:15 PM   Kernel reboot -> boot 5c74d073 (the current boot)
```

### 2.4 Why the user is `pi` and the clock says London

Root's 2022 shell history on the USB image (`/root/.bash_history`, 429 bytes, dated 26 Jun 2022)
shows how the base image was originally set up:

```
useradd pi -m -G wheel
ln -sf /usr/share/zoneinfo/Europe/London /etc/localtime
nano /etc/locale.gen ; locale-gen ; nano /etc/hostname ; nano /etc/sudoers
```

JUPI's image was built from that USB root, so `pi`, `en-GB` and London time came along with it
*(inferred: the image still carries the USB root's Nov 6 dotfiles such as
`.bash_profile.before-nikolai-20261106T2239Z`)*. The USB image's `/version` reads `2022.06.01`.
The machine is a PS4 (`x86_64`), and the Pi-style names are inherited.


## 3. Boot chain

JUPI's boot runs in two halves. The first half belongs to the PS4: Sony's console OS has to be
running before a homebrew payload can hand control to Linux. The second half belongs to Linux: an
initramfs root selector decides, with strict checks, whether to boot the JUPI image from the
internal HDD or fall back to the old USB root.

### 3.1 Step diagram

```
 [0] POWER ON  ->  Orbis OS (Sony firmware) boots from the internal HDD
        |
 [1] Homebrew enabler runs; its AutoRun launches the Linux payload
        |   /data/GoldHEN/payloads.ini AutoRun -> /user/data/payloads/linux-1024mb.bin (329,088 B, e11da9d2...)
        |   "1024mb" = the loader variant that reserves 1 GiB of the shared pool as GPU VRAM
        |   Whether this step needs a human at the console each boot: UNKNOWN
        v
 [2] Payload loads bzImage + initramfs and starts Linux
        |   copies: USB PS4BOOT (sda1)  or  HDD /ps4hdd/data/linux/boot/   -> which one: UNKNOWN
        |   both copies: kernel f0008d46...  initramfs cdeaefdb...  (same bytes)
        |   the loader hands the HDD unlock key to Linux as a 32-byte file in the initramfs
        v
 [3] Kernel 6.15.4-crashnt-4.7 starts
        |   cmdline: panic=0 clocksource=tsc consoleblank=0 net.ifnames=0 radeon.dpm=0
        |            amdgpu.dpm=0 drm.debug=0 console=ttyS0,115200n8 console=tty0
        |            video=HDMI-A-1:1920x1080@60
        v
 [4] better-initramfs /init  ->  ". /usbroot.sh"   (line 97; it replaced ". /fc.sh")
        |
        |   +------------------------- ROOT SELECTOR  usbroot.sh  (sha256 f65941df...) ----------+
        |   | sleep 5                                                                            |
        |   | any UFS / mapper / /newroot already present? ---------------- yes -> HOLD (rc 2)   |
        |   | key file present and exactly 32 bytes? ----------------------- no -> USB  (rc 1)   |
        |   | exactly one /dev/sdX whose GPT header + partition-27 GUID match? 0 -> USB (rc 1)   |
        |   |                                                      more than 1 -> HOLD (rc 2)    |
        |   | cryptsetup create jupi-boot-internal (plain, aes-xts-plain64, 256, offset 0)       |
        |   | mount UFS2 READ-ONLY at /ps4hdd (nosuid,nodev,noexec)                              |
        |   | image file present, size = 40 GiB or 355 GiB exactly?                              |
        |   | losetup -r ; blkid: UUID 70dbf870... and TYPE ext4?                                |
        |   | mount ext4 READ-ONLY,noload ; /usr/local/bin/jupi sha256 == pinned 3f5d4eee... ;   |
        |   |   /sbin/init resolves inside /newroot and is executable                            |
        |   | unmount, detach  ->  remount UFS2 READ-WRITE  ->  losetup RW  ->  recheck UUID     |
        |   | mount ext4 RW at /newroot ; recheck content ; mount --move /ps4hdd /newroot/ps4hdd |
        |   | print  JUPI_INTERNAL_ROOT_SELECTED_BOOT_UNPROVEN                    -> rc 0        |
        |   | any failure: JUPI_INTERNAL_UNAVAILABLE_<STEP>, clean teardown -> rc 1 (USB)        |
        |   |              teardown itself fails -> JUPI_HOLD_CLEANUP          -> rc 2 (HOLD)    |
        |   +------------------------------------------------------------------------------------+
        |
        |   rc 0 -> continue with JUPI image            rc 2 -> "JUPI_HOLD_INTERNAL_STATE", /bin/sh
        |   rc 1 -> legacy USB selector: mount the "psxitarch" ext4 on sda2/sdb2 RW
        |           HOLD_NO_USB / HOLD_MOUNT / HOLD_INIT -> /bin/sh
        v
 [5] Key-retention hook: if absent, copy the loader's key to a root-only file on the new root
        |   (<sealed root-only copy on the image>, mode 600, cmp-verified)
        |   prints JUPI_CONSOLE_KEY_RETAINED / _ALREADY_RETAINED / _DIFFERENT_EXISTING_FILE_PRESERVED
        v
 [6] switch_root /newroot  ->  systemd  ->  multi-user.target + jupi-platform.target
        |   ps4hdd backing stays mounted at /ps4hdd (UFS2 rw, onerror=lock)
        v
 [7] lightdm  ->  autologin pi  ->  XFCE  ->  ghostie-display-keeper keeps DPMS off
```

### 3.2 Selector exit paths at a glance

| Selector result | Console message(s) | What boots | Operator meaning |
|---|---|---|---|
| rc 0 | `JUPI_INTERNAL_ROOT_SELECTED_BOOT_UNPROVEN` | JUPI image (HDD) | Normal |
| rc 1 | `JUPI_INTERNAL_UNAVAILABLE_<STEP>` or none (no key / no disk) | **Old USB root** `sda2` *psxitarch* | Silent fallback. Looks like JUPI is up, but it is the 2022-based USB system |
| rc 1, no USB | `HOLD_NO_USB`, `HOLD_MOUNT`, `HOLD_INIT` | BusyBox shell | Rescue shell (Section 2 déjà vu) |
| rc 2 | `JUPI_HOLD_EXISTING_STATE`, `_AMBIGUOUS_PARTITION`, `_CLEANUP`, `_LOOP_STATE`, `_BACKING_LOCATION` … then `JUPI_HOLD_INTERNAL_STATE` | BusyBox shell | Selector refused to guess. Read the message, do not force |

`<STEP>` is one of `UFS_RO, IMAGE, FREE_LOOP, LOOP_NAME, LOOP_RO, IDENTITY, ROOT_RO, ROOT_CONTENT,
ROOT_RO_RELEASE, LOOP_RO_RELEASE, UFS_RW, LOOP_RW, IDENTITY_RW, ROOT_RW, ROOT_CONTENT_RW, BACKING_MOVE`.

> **Watch the silent fallback.** If the HDD bridge enumerates late, the GPT check finds no disk and
> the selector takes rc 1. JUPI then boots the *USB* root without complaint. In the rescue era
> the bridge appeared at 6.65 s, and the selector waits only 5 s. Whether 5 s is always enough on
> this hardware is **UNKNOWN**. After every reboot, confirm `findmnt -no SOURCE /` prints `/dev/loop0`
> (Runbook R6).

### 3.3 Design notes worth stealing

- **Two-phase mount.** Every check runs on a read-only mount first (`ro,noload`, no journal replay).
  Only then is the UFS remounted read-write and the image reattached read-write. A wrong image is
  never opened writable.
- **Identity pinning.** The selector accepts the image only if three things match: an exact byte size,
  the ext4 UUID, and the sha256 of a specific binary inside it (`/usr/local/bin/jupi`). That binary is
  why the README says it must stay *byte-for-byte* unchanged.
- **Refuse rather than guess.** Pre-existing state, two candidate disks, or a failed teardown all
  stop at a shell (rc 2) instead of picking one.
- **Symlink paranoia.** Every path test also rejects symlinks (`jupi_block`, `jupi_file`, `jupi_dir`).

### 3.4 What is proven and what is not

| Claim | Status | Evidence |
|---|---|---|
| Internal root selected and booted | Proven on 2 kernel boots (54f4c94e, 5c74d073) | boot receipts |
| Same kernel/initramfs bytes on USB and HDD copies | Proven on disk | `disk-boot-activation.json`, hashes |
| Which copy the loader read this boot | **UNKNOWN** | receipt: "loaded_boot_file_bytes UNKNOWN" |
| USB stick physically absent at boot | **Untested** | `usb_absent_boot_test: pending` |
| Unattended return after total power loss | **Not verified** | `cold_boot_verified: false` ×3 |
| Userspace soft-reboot | Proven once, Nov 7 (SoftRebootsCount 0→1) | `/etc/jupi/AGENTS.md` |
| kexec warm reboot | **Held**: early GPU firmware set incomplete | `native-warm-qualification.json` |
| Serial console ttyS0 as recovery path | **Not usable**: UART init disabled in source | `/etc/jupi/AGENTS.md` |


## 4. Storage layout

```
 sda  SanDisk USB, 114.6 GiB, DOS label 0xeac72143            (boot medium + fallback root)
 |-- sda1   512 MiB  vfat  PS4BOOT    891E-578E    kernel + initramfs (USB boot copy)
 |-- sda2 106.1 GiB  ext4  psxitarch  2ec1035f...  OLD root (fallback), not mounted
 `-- sda3     8 GiB  swap  ps4swap    7762469a...  retired Nov 6 9:17 PM (commented in fstab)

 sdb  Internal HDD via Sony USB-SATA bridge, 465.8 GiB, GPT 66FB93BD-..., 15 partitions
 |-- sdb27 420.1 GiB  --dm-crypt plain aes-xts-plain64-->  /dev/mapper/jupi-boot-internal
 |                                                         `-- UFS2 (Sony)  mounted at /ps4hdd
 |                                                             414 G size, 48 G used, 333 G free
 |     /ps4hdd/home/jupi-linux-2a79fafeb62d61ff.img   381,178,347,520 B (355 GiB) -> /dev/loop0 = /
 |     /ps4hdd/home/linux.img                          53,687,091,200 B (50 GiB, stock image, idle)
 |     /ps4hdd/data/linux/boot/{bzImage, initramfs.cpio.gz, initramfs.before-disk-only-...}
 |     /ps4hdd/data/{GoldHEN, payloads, sce_logs, ...}  + Sony system dirs (appmeta, system, ...)
 `-- sdb1..sdb31 (14 other Sony partitions, unknown types) -- never touched

 zram0  2 GiB  lz4   swap  JUPI_ZRAM   prio 100   (jupi-zram.service)
 zram1  2 GiB  zstd  swap  groku-zram  prio 200   (groku-zram.service, used first)
```

| Mount | Source | Type / options | Size / used / free |
|---|---|---|---|
| `/` | `/dev/loop0` | ext4 rw,relatime | 350 G / 33 G / 313 G |
| `/ps4hdd` | `/dev/mapper/jupi-boot-internal` | ufs rw,nosuid,nodev,noexec,ufstype=ufs2,onerror=lock | 414 G / 48 G / 333 G |
| `/tmp` | tmpfs | 3.4 G | 113 M used |
| `/run/user/1000` | tmpfs | 691 M | — |

> **The image is sparse. Its free space is borrowed.** The root reports 313 GiB free. Those blocks do
> not exist until written, and they come out of the UFS's 333 GiB. `/etc/jupi/boot.json` keeps a
> **16 GiB backing headroom** (`backing_headroom_bytes: 17179869184`). Do not grow another image
> into that reserve. If the UFS fills, the root filesystem fails underneath a running system.

> **Do not touch** the 14 other Sony partitions, `/ps4hdd/system`, `/ps4hdd/home/<ps4-user-id>` (the
> console user profile) or the Orbis-side files. They are what make step [0]–[1] of the boot work.
