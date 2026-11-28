# RECEIPT: JUPI push readiness — read-only verification
Fri Nov 27 2026, ~1:50–2:05 PM PST. Authorized by pt4069u ("We literally did usb absent boot... they are up now with no sticks"), and Kam's earlier "Just check and verify everything obviously". Read-only: no writes on JUPI 1, JUPI 2, sticks or Roach; no mounts, kills, reboots, network changes; no xchain/HCDU appends. Only this file was written. - groku

## Verdict
The sealed kernel jupi-1.0 (bzImage sha a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e) is ALREADY the internal-HDD default on both consoles and has run both of them stickless for ~2d18h. Kam is right: USB-absent boot is flown on both. READY as fleet default, with open items (see bottom), none of them a blocker for "sealed kernel as default".

## 1. Live (read-only, via Roach; both nodes up)
| | JUPI 1 (hostname playstation) | JUPI 2 (hostname jupi2) |
|---|---|---|
| uname -v | #jupi-1.0 SMP PREEMPT_DYNAMIC Tue Nov 24 15:26:06 PST 2026, (jupi@nikolai), 6.15.4-crashnt-4.7_no-built-in-fw | same |
| boot (from /proc/uptime) | Tue Nov 24 7:40:39 PM PST (238273 s at 1:51:52 PM Nov 27) | Tue Nov 24 7:32:55 PM PST (238737 s) |
| root | /dev/loop0 ext4 LABEL JUPIROOT UUID <uuid>, backing /ps4hdd/home/jupi-linux-2a79fafeb62d61ff.img on /dev/mapper/jupi-boot-internal | /dev/loop0 ext4 LABEL proroot UUID <uuid>, backing /ps4hdd/home/pro-linux.img on /dev/mapper/pro-boot-internal |
| disks | sda = internal HGST 465.8G behind Sony 054c:084e USB-SATA bridge (Aeolia internal; base-PS4 design), no other mass storage | sda = internal HGST 931.5G on ATA, no USB mass storage at all |
| USB at boot (kernel ring intact from 0.000000) | only usb-storage 4-1 = internal bridge; no second mass-storage device, no disconnects | only device disconnect = 054c:05c4 DualShock 4 controller |
| is-system-running | running | running |
| cmdline | payload default + sky2.aeolia_poll_phy=1 (HDD bootargs.txt) | payload default |
| kexec_loaded | 0 | 0 |
HDD boot files (/ps4hdd/data/linux/boot):
- JUPI 1: bzImage a06fdd7a… (written Nov 24 6:58 PM PST), bzImage.prev-f0008d46 = f0008d466329d07d456fda63fe03129f7af0403a4040d357d3a62658e3d17293 (original crashnt-4.7), initramfs.cpio.gz ebfa1fd11c7bbebfae160ea7f9b6454e66fe92013898cac4ccd9211ea034d11d, bootargs.txt 0265bdbd37acf20a13d5225089fd63602914346f8b010f2a0d3927658f08f068. /etc/jupi/boot.json pins kernel_sha256 a06fdd7a…. Boot receipt for boot_id <uuid> at 7:43:06 PM PST Nov 24, sha 08de8a850e7854f43e6d065965dc73c230a8be209912bc4d643d93b681f0a2ff (it lists jupi-boot-record.service failed at that time; system is "running" now).
- JUPI 2: bzImage a06fdd7a… (Nov 24 6:57 PM PST), bzImage.prev-f0008d46 (f0008d46…), initramfs.cpio.gz 53dfd78b1402caf05568968b6ba5bf37c8cb8f773fb1792f2aedc8736e527cd7.
Kernel identity: running build string equals the string inside stick copy bzImage.jupi-1.0 (a06fdd7a…). Sol's pidfsfix (0bd2726640d571c1c28fad7a721ba7db65e04472adcb7f7674312ecf9d72b289) is "(sol@nikolai) #1 … Fri Nov 20 16:52:41 PST"; orig f0008d46 is "(root@466d84d2fb08) #2 … Mar 14 2026". The sticks' default bzImage is pidfsfix, so a stick-in boot could not show #jupi-1.0 => the running kernel came from the HDD.

## 2. Sticks on NIKOLAI (already mounted before this check; FAT rw by udisks, ext4 ro,norecovery; nothing mounted/unmounted by me)
- sde SanDisk Ultra 114.6G: sde1 PS4BOOT 891E-578E (= JUPI 1 boot.json usb_boot_uuid), sde2 LABEL psxitarch (ext4, /mnt/study-j1), sde3 ps4swap.
  TRIAL-PASSED sha 15f54734ef064b27022078c6fe9e911eb3591916fb816c5e954ae13fb6f517b7: cand bzImage.jupi-1.0 a06fdd7a…, good bzImage.pidfsfix-20261120 0bd27266…, armed 01:57:18 GMT = Nov 24 5:57:18 PM PST, PASSED 02:29:19 GMT = 6:29:19 PM PST.
- sdd ST9160412AS 149.1G (USB): sdd1 PS4PROBIN 2498-F8A4, sdd2 LABEL JUPI2ROOT (not psxitarch) at /mnt/study-j2.
  TRIAL-PASSED sha 2626a52d38989c2f316d4886cab212325b908092c196536bbffed53fec681d68: same cand/good, armed Nov 24 5:18:50 PM PST, PASSED 5:39:48 PM PST (recorded late by groku, pt3879u).
- Both sticks: bzImage = bzImage.pidfsfix-20261120 = 0bd27266…; bzImage.jupi-1.0 = a06fdd7a…; bzImage.crashnt-4.7-orig-20261120 = f0008d46…. PS4BOOT initramfs.cpio.gz ebfa1fd1… (= JUPI 1 HDD); PS4PROBIN initramfs.cpio.gz 53dfd78b… (= JUPI 2 HDD).

## 3. (Lab storage cleanup check: omitted from the public edition; internal housekeeping, not about the kernel.)

## 4. Gates
- Cold boot on the metal, jupi-1.0: CONFIRMED (TRIAL-PASSED on both sticks + both consoles currently on #jupi-1.0 after a clean power-off).
- USB-absent boot: CONFIRMED both. JUPI 2: Roach receipt ~/groku2/hdd-install-20261124/RECEIPT-JUPI2-STICKLESS-PASS-20261124.md (SHA256SUMS -c all OK) plus live data, same boot. JUPI 1: no prior receipt found on Roach; live evidence above is the record (boot 7:40:39 PM PST Nov 24, kernel from HDD, no stick ever enumerated this boot). Stale self-reports still say untested: JUPI 1 health-native "usb_absent_boot_test: pending"; /etc/jupi/cold-start-assessment.json (Nov 7) usb_absent_cold_start_tested false.
- Uptime/soak: OBSERVED ~2d18h each, systemd running.
- kexec: Orbis->Linux payload kexec handoff is exercised on every boot (CONFIRMED, it is the boot path). Linux->Linux kexec of jupi-1.0: not flown; kexec_loaded 0, JUPI 1 platform.json kexec_boot_validated false. UNSOURCED.
- Power-loss survival (unclean power cut while Linux is up): no test record found; JUPI 2's last 3 boots all ended in clean systemd poweroff. UNSOURCED.
- Attestation: no record found on Roach or NIKOLAI. UNSOURCED.

## Open items (not blockers for default)
1. HDD rollback on both consoles is bzImage.prev-f0008d46 (original crashnt-4.7, pre-pidfs-fix), not Sol's pidfsfix 0bd27266. Sol's build exists only on the sticks, which are now on NIKOLAI.
2. Sticks' default bzImage is pidfsfix; plugging a stick back in boots pidfsfix, not jupi-1.0.
3. JUPI 1 stale self-reports (usb_absent pending) should be updated by whoever owns them.
4. JUPI 2 stick root label is JUPI2ROOT, not psxitarch. Not used by the stickless internal path.
5. (Lab ssh-path note omitted from the public edition.)
