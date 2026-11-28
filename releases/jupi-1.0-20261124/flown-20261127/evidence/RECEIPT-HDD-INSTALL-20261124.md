# RECEIPT: jupi-1.0 installed on each console's internal HDD (stickless boot path)
Tue Nov 24 2026, 6:55-7:05 PM PST. Authorized by pt3884u / pt3885u ("keep our backups on roach", booting without the sticks). - groku
No reboot, no power-off. payloads.ini, payload, network config, JUPI 1 SDIO/Wi-Fi/BT/musegadget untouched. Both sticks untouched (read-only mounts; every file re-hashed identical to the backup).
Both trials PASSED first: JUPI 2 17:39:48 PST (TRIAL-PASSED 2626a52d, finalized), JUPI 1 18:29:19 PST (guard v3 clean).

## 1. Backups on Roach: <peer-home>/jupi-kernel-backups-20261124/ (README.md, SHA256SUMS, 35 files, all re-verified)
Taken BEFORE any HDD write: full copy of both stick boot partitions, both HDD /data/linux/boot dirs, both payload copies, jupi-1.0 bzImage, guard v2+v3. Source-vs-copy sha256 compared for every file: identical (JUPI 1 stick 16 files, HDD boot 3, payloads 1; JUPI 2 stick 9, HDD boot 2, payloads 1).

## 2. Is the HDD /data/linux/boot safely writable from Linux?  YES, by evidence (not by upstream's word)
- How Linux sees Orbis /data: /ps4hdd/data (JUPI 1: sdb27 -> dm-crypt jupi-boot-internal; JUPI 2: sda27 -> pro-boot-internal), ufs2, mounted rw, onerror=lock. CONFIG_UFS_FS_WRITE=y in the running kernel.
- Upstream marks Linux UFS write support experimental. Why I still did it: this exact mount is written all day by production use (CONFIRMED): JUPI 1's 355 GB root image lives on it and was being written at 02:57 UTC; JUPI 2's 128 GB root image the same; JUPI 2's /data/payloads/linux-1024mb.bin was written through this path at 16:42 PST today (Kam go) and read back clean; /ps4hdd/data/profile.dat on both is touched by the running system. dmesg: 0 ufs errors on both, before and after. Writes here are tiny (15 MB kernel) next to what already happens.
- Method (no in-place overwrite): copy old to .prev-<sha8>, verify; stream new file in as a temp name, sync + drop caches + re-hash from disk (matches), chmod to match, then ONE atomic rename over bzImage, sync, drop caches, re-hash from disk. Never a moment without a bzImage.
- Residual risk: UFS write is not upstream-blessed; a power cut mid-write could leave the HDD /data fs needing Orbis repair. Worst case is Orbis rebuilding/checking, not a hardware brick. Orbis itself never reads /data/linux.

## 3. Installed (hashes re-read from disk after install)
JUPI 2  /data/linux/boot (log: jupi2-install.log)
- bzImage:        f0008d466329d07d456fda63fe03129f7af0403a4040d357d3a62658e3d17293 -> a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e (jupi-1.0)
- bzImage.prev-f0008d46 (new): f0008d46...7293 (the old HDD kernel)
- initramfs.cpio.gz 53dfd78b1402caf05568968b6ba5bf37c8cb8f773fb1792f2aedc8736e527cd7 UNCHANGED: it is byte-identical to the stick initramfs that jupi-1.0 booted with (CONFIRMED), so it is the proven one.
JUPI 1  /data/linux/boot (log: jupi1-install.log)
- bzImage:        f0008d46...7293 -> a06fdd7a...2b8e (jupi-1.0)
- bzImage.prev-f0008d46 (new): f0008d46...7293
- initramfs.cpio.gz: cdeaefdb30c7b60ad25fa478ef41eb365fb5132795257011f753578537d11e21 -> ebfa1fd11c7bbebfae160ea7f9b6454e66fe92013898cac4ccd9211ea034d11d (the stick initramfs jupi-1.0 PASSED with)
- initramfs.prev-cdeaefdb.cpio.gz (new): cdeaefdb...1e93 (old HDD initramfs). initramfs.before-disk-only-20261107... unchanged (7eec9f0e).
- Why the initramfs swap on JUPI 1 (the stick and HDD copies differed): diff of the unpacked archives = only usbroot.sh. ebfa1fd1 adds the "Jupi-Prime" key step (use the loader-provided /key/eap_hdd_key.bin first; only if the loader gave none, look for a recovery USB root; rc 1 = carry on, rc 2 = hold). With the loader providing the key, stickless boot takes the first branch and needs no USB. The rest of the selector (find the PS4 GPT disk by scanning every /dev/sd?, unlock partition 27, check image size/UUID/jupi sha, switch_root) is identical. The old cdeaefdb is the same minus the key step. I read no key bytes.
- Not changed on either: /data/payloads/linux-1024mb.bin e11da9d2, the JUPI 1 auto-start entry file 89832cc8 (JUPI 2 has none).
- UNPROVEN (needs Kam at the console): an actual boot of either console with no stick. JUPI 2's earlier HDD escape boot proves its payload->HDD path; JUPI 1's HDD path has never run.

## 4. Escape path now
- Payload reads USB first, then HDD. STICK IN = the stick's bzImage wins (today both sticks hold jupi-1.0 as bzImage, plus pidfsfix 0bd27266 and original f0008d46 copies). STICK OUT = HDD jupi-1.0.
- If the HDD jupi-1.0 ever breaks: insert the stick whose bzImage is a known-good kernel. Today the stick's bzImage is ALSO jupi-1.0, so as it stands the stick is no escape from a jupi-1.0 problem.
- RECOMMENDED (not done, needs Kam's go): set each stick's bzImage back to pidfsfix (0bd27266), i.e. make the stick a pure "plug in for the old kernel" escape. Tradeoff: with the stick in you boot the OLD kernel and lose the new one; to run jupi-1.0 you pull the stick (that is the whole stickless idea, so it fits). Stick files are already there; command per console (guard v3, no trial armed): copy bzImage.pidfsfix-20261120 over bzImage on the stick and re-hash. If the HDD kernel itself is bad and no stick is handy: Linux can't help (it's the thing that's down); recovery = stick from the backups on Roach, or any PC copying a bzImage onto the stick's FAT root.
- JUPI 1 only: a second out is to pull the stick AND the HDD pair is now jupi-1.0, so the old f0008d46 pair is no longer the stick-out fallback. The old pair sits as bzImage.prev-f0008d46 + initramfs.prev-cdeaefdb on the HDD and in the Roach backups.
- The trial guard is dormant (no TRIAL, label PS4BOOT/PS4PROBIN); with no stick it logs "stick not present" and does nothing.

## 5. Stickless boot test, per console (needs Kam; reboot = Kam's go)
JUPI 2: groku runs sync + clean shutdown; light off; pull the STICK (and keep it handy); power on; start the loader the usual way and use the INTERNAL linux-1024mb.bin (/data/payloads; Kam starts it; JUPI 2 has no auto-start). Expect a desktop, uname -v = #jupi-1.0 ... Nov 24 15:26:06 PST 2026, root loop0 proroot, SSH answers. 
JUPI 1: groku sync + clean shutdown; light off; pull the STICK; power on; start the loader the usual way; the auto-start entry runs the HDD loader with no menu. Expect #jupi-1.0, root loop0 JUPIROOT from /ps4hdd/home/jupi-linux-2a79fafeb62d61ff.img. Black screen 1-3 min is normal.
Failure (no SSH after ~8 min, black screen): hold power until light off, plug the stick in (bzImage must be a known-good kernel for this to be an escape: see 4), boot again.
Do one console at a time. JUPI 2 first (it has already booted from the HDD with no stick).

## 6. (JUPI 1 network-address diagnosis: lab network detail, omitted from the public edition. Not kernel-related.)
