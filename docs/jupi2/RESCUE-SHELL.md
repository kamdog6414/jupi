# JUPI 2 (PS4 Pro): from PayLoader to rescue shell to desktop

> Public edition. High-level account of how Linux got onto the PS4 Pro on 10 Nov 2026, from the lab's receipts and rescue-shell inventory. No keys, decryption offsets, exploit details, addresses, ports, drive serials or identifiers. Times are PST (America/Los_Angeles). JUPI (the base PS4) has its own story in [../BOOT-CHAIN.md](../BOOT-CHAIN.md); this page covers only what was new on the Pro.

## 1. Boot chain in one line

PS4 OS with GoldHEN → PayLoader receives `linux-1024mb.bin` once over the LAN → the loader boots a kernel and initramfs from a FAT32 USB drive left in the Pro → the initramfs unlocks the console's user partition, loop-mounts a 128 GiB ext4 image and `switch_root`s into it → Arch Linux, systemd, LightDM autologin, XFCE on HDMI at 1920×1080@60.

The console's system partitions and partition table are never modified. Linux lives in one sparse file inside the user filesystem and is started fresh after each power-on.

## 2. Boot files on the USB

| File | Size | Notes |
|---|---|---|
| `bzImage` | 15,692,800 bytes | Linux `6.15.4-crashnt-4.7_no-built-in-fw`, the same kernel JUPI runs; nothing downloaded |
| `initramfs.cpio.gz` | — | Pro-patched initramfs (JUPI's, plus an additive Pro selector) |
| `initramfs.cpio.gz.jupi-orig-…` | 6,778,642 bytes | Unmodified JUPI initramfs, kept as the rollback copy |
| `payloads/linux-1024mb.bin` | 329,088 bytes | The 1 GB-VRAM loader variant, which is why Linux sees a 1,024 MB VRAM carve-out |

No `bootargs.txt` or `vram.txt` was written. The loader's built-in default command line already includes `radeon.dpm=0 amdgpu.dpm=0` and the HDMI-A-1 1920×1080@60 mode.

## 3. Timeline, 10 Nov 2026

| Time (PST) | Event |
|---|---|
| 16:42 | Spare Seagate ST9160412AS HDD (149.05 GiB) on a Realtek RTL9201 USB bridge attached to the lab host. It held an old Ubuntu live image; its installer logs were copied off before the wipe |
| 16:45 | Drive formatted exFAT, label `PS4PROBIN` |
| 16:49 | First PayLoader attempt: no send. A connect-only port probe a minute earlier had consumed PayLoader's one shot |
| 16:51 | First real send over Wi-Fi: all 329,088 bytes accepted in 0.244 s. The stick held only the payload, so the loader stopped with `Failed to load file: bzImage` |
| 16:55 | Kernel and initramfs copied onto the stick (live JUPI files, renamed only at the destination) |
| 16:57 | Second send over Wi-Fi, 0.282 s. No Linux handoff |
| 17:04, 17:10 | Third and fourth sends, now over wired Ethernet (0.024 s, 0.023 s). The Pro's wired NIC has a different hardware address from its Wi-Fi, which briefly hid it from the search. The loader accepted a drop and hung on a black screen |
| 17:18 | Stick reformatted **FAT32 (LBA)**, 32 KiB clusters, same boot bytes restored and hash-checked identical. PS4 loaders often fail to mount exFAT |
| 17:20 | Fifth send, wired, 0.023 s. Linux came up at about 17:21 (inferred from the inventory's 25-minute uptime) |
| 17:46 | Read-only rescue-shell inventory (section 4) |
| 17:48 | Backups taken before any write: GPT primary and backup, first 8 MiB of the user partition, a tar of the UFS2 file set, USB MBR and file tar |
| 18:16 | Arch root image built (section 5); pre-switch chroot bench 17.29 tok/s at 4 threads |
| 20:20 – 20:23 | `switch_root` into the Arch root; LightDM session on tty7; desktop bench 17.34 tok/s at 4 threads |
| 20:35 | Hostname `jupi2`, enrolled as Muse gadget "JUPI 2" with SSH (key-only) and the loopback LLM server |
| 21:00 | Disk-boot path ready: the Pro-patched initramfs on the USB |
| 21:04 | Full power-cycle and one fresh PayLoader send boot straight to the XFCE desktop. `systemctl --failed`: 0. This is the proof that the USB path works on its own |
| 21:08 – 21:31 | Comprehensive benchmark ([BENCHMARKS.md](BENCHMARKS.md)) |

PayLoader is one-shot: do not test its port with `nc` or a browser before the real send. One connect-and-write of the BIN, nothing else.

## 4. The rescue shell and why it held

After the 17:20 send the Pro did not reach a desktop. The initramfs dropped to its BusyBox shell with `HOLD_NO_USB`. Access was a BusyBox `nc` listener running `/bin/sh` on the Pro's wired interface, reached from the lab host with a small Python client; a second backup listener was added. Everything in this section is from that read-only session.

**Rescue-shell inventory [R]**

| Item | Value |
|---|---|
| `uname` | `Linux ps4 6.15.4-crashnt-4.7_no-built-in-fw #2 SMP PREEMPT_DYNAMIC Sat Mar 14 11:01:12 UTC 2026 x86_64 GNU/Linux` |
| Uptime at capture | 25 min, load average 0.00 0.00 0.00 |
| CPU | AMD DG1301SML87HY, 8 cores |
| RAM | 7,070,228 kB total, ~6.8 GB available, no swap |
| GPU | 1002:9924 Gladius, amdgpu 3.63.0, 32 CUs, 1024M VRAM, 3450M GTT, HDMI-A-1 connected |
| NIC | `eth0`, sky2 driver, 1000 Mb/s full duplex |
| Internal disk | 931.5 GiB, PS4 GPT layout |
| User partition | Decrypts to UFS2 with a key the loader provides at boot (never written to disk) and the Pro's own offset; ~841 GB free, essentially fresh. JUPI's offset produces garbage on the Pro |
| USB | The 160 GB drive, FAT32 `PS4PROBIN` |

**Cause of `HOLD_NO_USB`.** The initramfs was JUPI's, and JUPI's root selector is pinned to JUPI: its exact GPT identity and its decryption offset. On the Pro that check correctly refuses (rc 1). The legacy fallback then looks for a USB ext4 root labeled `psxitarch`, which this stick does not have, so it holds at a BusyBox prompt. Nothing was wrong with the Pro; the selector was doing its job on the wrong console.

**Fix (additive).** A Pro branch was appended after the unchanged JUPI branch:

```
jupi_internal    unchanged; returns 1 on the Pro (not JUPI's GPT)
pro_internal     unlock the Pro user partition, loop-mount the Pro image
                 (pinned to its own GPT identity, image path and ext4
                 UUID/label), switch_root
pro_rescue_net   if that fails: bring up eth0 and start a BusyBox nc root
                 shell (no SSH in this mode)
HOLD_NO_USB      the old path, last
```

The base-PS4 path is untouched, and the original JUPI initramfs stays on the stick for rollback (copy it back over `initramfs.cpio.gz`).

## 5. The root image

| Item | Value |
|---|---|
| File | New file in the PS4 user filesystem only; no partition touched |
| Size / type | 128 GiB sparse, ext4, label `proroot`, mounted on `/dev/loop0` |
| Distribution | Arch Linux 2026.11.01, 416 packages: base, openssh, NetworkManager, XFCE4, LightDM (autologin), Mesa 26.2.6 with `vulkan-radeon`, earlyoom, and others |
| Memory | zram 4 GiB lz4, earlyoom with JUPI's policy |
| Accounts | Key-only SSH; passwords locked |

## 6. The switch_root gotcha

The switch was a typed `exec sh /pro-switch.sh` on the Pro's console, and at first it looked silent. PID 1 (the rescue shell) was blocked in `wait4()` on the foreground `nc -lk` listener, so it never read the line. The remote fix was to SIGTERM only that `nc` process. PID 1 then consumed the already-typed command from the console line buffer, the script printed `PRO_SWITCHING_ROOT`, and `exec switch_root` succeeded: PID 1 became systemd, `/` became the Arch loop image, and the desktop came up on the same boot (no reboot, uptime ~3 h). The rescue listener disappeared, as expected.

Lesson: if a rescue shell is also serving a foreground listener, it is not reading the console.

## 7. Normal boot procedure (proven 21:04)

1. Prefer a clean halt (`sudo poweroff` over SSH) so ext4 journals cleanly, or hold the power button until fully off.
2. Leave the FAT32 USB in the Pro. Do not reformat or unplug it for a normal reboot.
3. Boot the PS4 OS, enable GoldHEN, open PayLoader and wait for its listening message.
4. Send `linux-1024mb.bin` once, with no pre-connect probe.
5. Success is the XFCE desktop with autologin, not a `HOLD_NO_USB` or rescue-net shell. Check that `/` is `/dev/loop0` on the Pro image and that sshd, the Muse gadget service and the LLM server are back.
6. If it drops to a rescue prompt, leave it on that screen; the rescue-net branch brings up the wired NIC with a root shell for diagnosis.

## 8. Services after a good disk-boot

sshd (key-only), the Muse gadget system service (display name "JUPI 2"), groku-muse as a lingering user service on loopback, LightDM autologin to XFCE with sleep and lock disabled, NetworkManager (static wired address), zram, earlyoom, bluetooth, timesyncd. Default target `graphical.target`. Integration pass at 21:05 – 21:35: lab-host to JUPI 2 LAN round trip 0.31 ms average with 0% loss, SSH pipe 70 MB/s.

## 9. Gaps

- The exact minute of first rescue-shell contact is not in a file; the first filed evidence is the 17:46 inventory.
- There is no standalone "disk-boot proven" receipt; the proof is the integration receipt's "up since 21:04".
- The fifth-send receipt does not itself confirm boot; the inventory uptime does.
