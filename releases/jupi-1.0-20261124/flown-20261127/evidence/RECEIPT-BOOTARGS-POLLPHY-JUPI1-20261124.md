# RECEIPT: JUPI 1 HDD bootargs.txt = default + sky2.aeolia_poll_phy=1 (for the stickless test)
Tue Nov 24 2026, 7:07 PM PST. Authorized by pt3888u ("Yes fold it in to the stickless test"). Additive to hdd-install-20261124/. - groku
No reboot, no power-off. Stick untouched. payloads.ini, network, SDIO/Wi-Fi/BT/musegadget untouched. Kernel and initramfs hashes on the HDD unchanged.

## 1. Param name (CONFIRMED from the patch)
Patch `0001-sky2-aeolia-poll-phy.patch`: `static bool aeolia_poll_phy; module_param(aeolia_poll_phy, bool, 0444);` in the sky2 driver.
Boot argument: `sky2.aeolia_poll_phy=1` (module param, not __setup).
Sysfs after boot: `/sys/module/sky2/parameters/aeolia_poll_phy` should be Y.
Patch `0003` log line when it takes: `eth0: jupi: Aeolia PHY poll mode on (PHY IRQ masked, link polled once per second)`.
Not used: `aeolia_eth.poll_phy=1` (wrong). The 0002 fallback `sky2.aeolia_skip_empty_phy_stat=1` is NOT in this file.

## 2. How the payload gets boot args on a stickless boot (CONFIRMED paths)
linux-1024mb.bin e11da9d2...6646 path table (strings in the binary, consecutive, after the initramfs "Checked paths" table):
  /mnt/usb0/bootargs.txt → /mnt/usb1/bootargs.txt → /data/linux/boot/bootargs.txt → /user/system/boot/bootargs.txt
Same order as bzImage and initramfs. Each file is looked up separately; first match wins. bootargs.txt is optional: if none of the four exist, the payload uses its built-in default, which is the exact cmdline JUPI 1 is running now.
On a stickless boot there is no /mnt/usb0 or /mnt/usb1, and /user/system/boot does not exist on JUPI 1, so /data/linux/boot/bootargs.txt is the file that will be used. (CONFIRMED paths in the binary. OBSERVED load logic from the public ps4-linuxpayloads L() macro, same family, documented in bootsafety 01-JUPI2-BOOT-CHAIN.md. An actual HDD-bootargs boot on JUPI 1 is UNPROVEN until this test runs.)
bootargs.txt REPLACES the default, it does not append. CONFIRMED by the Nov 11 safe-boot file, which was a full default cmdline plus extra options (nomodeset fcsafe=1 ...), not a fragment. So this file holds the full current default plus ` sky2.aeolia_poll_phy=1`, and has no trailing newline (INSTALL-TEST-ROLLBACK.md / artifacts/bootargs.txt.PROPOSED-jupi1-poll).

SIDE EFFECT (document, do not ignore): because each file is searched separately, this HDD bootargs.txt will also apply if Kam boots WITH the stick in, as long as the stick has no bootargs.txt of its own (it does not, CONFIRMED just before the write). The current stick bzImage is also jupi-1.0, so a "stick in" boot would get poll mode too. If the stick is later set back to pidfsfix as an escape, that older kernel would see `sky2.aeolia_poll_phy=1` as an unknown param and ignore it (typical kernel behavior; not tested here). To make a stick boot ignore HDD bootargs, put a default-only bootargs.txt on the stick (not done; stick is untouched).

## 3. Write
Before: /ps4hdd/data/linux/boot/bootargs.txt ABSENT. Stick PS4BOOT: ABSENT. Backup of that absence: Roach <peer-home>/jupi-kernel-backups-20261124/jupi1/NOTE-ABSENCE-bootargs-before-pollphy.txt (sha 75457e6bfe3084bb0246fbf6c9226d08c5ca8e635284d1387d0e54c82e5928f8). Proposed file also stored there as bootargs.txt.PROPOSED-jupi1-poll.
After (atomic: stage as bootargs.txt.new, hash, rename, drop caches, re-hash from disk):
- path: /ps4hdd/data/linux/boot/bootargs.txt
- sha256: 0265bdbd37acf20a13d5225089fd63602914346f8b010f2a0d3927658f08f068
- size: 177 bytes, last byte 0x31 ('1'), no trailing newline
- contents: panic=0 clocksource=tsc consoleblank=0 net.ifnames=0 radeon.dpm=0 amdgpu.dpm=0 drm.debug=0 console=ttyS0,115200n8 console=tty0 video=HDMI-A-1:1920x1080@60 sky2.aeolia_poll_phy=1
Siblings unchanged (re-read): bzImage a06fdd7a...2b8e, initramfs.cpio.gz ebfa1fd1...d11d, payloads.ini 89832cc8..., linux-1024mb.bin e11da9d2...6646. dmesg ufs errors: 0. Stick still has no bootargs.txt.

## 4. Post-boot verify (from Roach, after Linux is up)
ssh jupi1 'bash -s' < postboot-verify-jupi1-pollphy.sh
Pass, all of:
- uname -v starts `#jupi-1.0 SMP PREEMPT_DYNAMIC Tue Nov 24 15:26:06 PST 2026`
- /proc/cmdline ends with `sky2.aeolia_poll_phy=1` (and otherwise matches the default)
- /sys/module/sky2/parameters/aeolia_poll_phy = Y
- dmesg has `eth0: jupi: Aeolia PHY poll mode on`
- eth0 operstate=up, speed=1000, duplex=full; ping <lab-ip> (Roach) 5/5
- IRQ 24 rate < 100/s idle (script takes 3 x 10 s samples); /proc/irq/24/spurious unhandled not growing
- CPU 1 softirq low (not 100%); a `taskset -c 1` busy loop can use the core
- no `nobody cared` / `Disabling IRQ` / Oops / receiver hang in dmesg; recheck at 15 min
- root is still loop0 JUPIROOT from the HDD image (not the stick's psxitarch)

## 5. Undo (no reboot by itself; takes effect on the next payload boot)
ssh jupi1 'sudo rm -f /ps4hdd/data/linux/boot/bootargs.txt && sync && test ! -e /ps4hdd/data/linux/boot/bootargs.txt && echo ABSENT-AGAIN'
That restores the pre-write state (no file). Next boot uses the payload default, poll mode off.
If Linux is down: any PC (or a file transfer to the PS4 disk) can delete /data/linux/boot/bootargs.txt on the PS4 HDD, or boot with a stick that has its own bootargs.txt (USB wins).

## 6. Kam's exact steps for the JUPI 1 stickless + poll_phy test
Do JUPI 2's stickless test first if that is still the plan (JUPI 2 has no poll_phy file and does not need one). Then JUPI 1, one console at a time:
1. Groku runs `sync` and a clean Linux shutdown. Do not use the smart plug while Linux is up. Wait until the light is fully off.
2. PULL THE STICK and keep it handy.
3. Pull the AC cord for 60 seconds, plug it back in, power on.
4. Start the loader the usual way (out of scope here; kept private).
5. Let the auto-start entry run the loader; do not change it.
6. Black screen for 1-3 minutes is normal. Groku watches from Roach and runs the verify script once SSH answers, then again at 15 minutes.
If it hangs or there is no SSH after ~8 minutes: hold power until the light is off, plug the stick back in, start the loader again. Because the stick has no bootargs.txt, HDD bootargs still apply on a stick-in boot of jupi-1.0 (see side effect above). To get poll mode OFF immediately, delete bootargs.txt from the HDD (/data/linux/boot/bootargs.txt on the PS4 disk) before the retry, or have Groku delete it once any kernel is up. Worst case the PS4 still boots plain Orbis.
