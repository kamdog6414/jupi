# Fail-safe boot design for JUPI 1 and JUPI 2 — a bad kernel must never lock Kam out
Rule: **only use what the current loader and initramfs already support.** Anything that needs a new loader build is marked **[REBUILD]**. Anything that writes to a stick, the HDD or the console is marked **[KAM GO]**.

## What we can and can't control (CONFIRMED from the payload's path tables and source)
- The loader always loads the fixed name `bzImage` (and `initramfs.cpio.gz`, optional `bootargs.txt`, `vram.txt`). Each file is looked up separately in USB0 → USB1 → `/data/linux/boot` → `/user/system/boot`, and the first one found wins.
- It can't boot a "try once" file, can't count boots and can't fall back by itself. **A true A/B inside the loader needs a new loader build [REBUILD].** It's not proposed now: our binary's exact source and firmware build are UNSOURCED, and a wrong loader is a new brick risk.
- Linux can't loop on its own: `panic=0` makes a panic hang, there's no watchdog and no auto-reboot (CONFIRMED). Each "loop" round needs the loader to be started, which Kam does. On JUPI 1, the auto-start entry then fires Linux immediately.

## The design: three layers, simplest first

### Layer 1 — Two boot sets, one rule (no new code)
- **Stick = what you're testing. HDD `/data/linux/boot` = frozen known-good.** Never put a new kernel on the HDD first, and never change both on the same day.
- HDD today: JUPI 1 f0008d46 + cdeaefdb (pins still match the live root, CONFIRMED). JUPI 2 f0008d46 + 53dfd78b (the same initramfs as the stick, CONFIRMED).
- **Escape hatch = pull the stick before starting the loader.** With no bzImage on USB, the loader takes the HDD pair.
  - JUPI 1: works with today's setup because the loader copy is internal (`/data/payloads`, auto-start entry). CONFIRMED design; **untested when written**, and flown since (see ../flown-20261127/STATUS-20261127.md).
  - JUPI 2: **did not work when written.** The only loader copy was on the stick, so with the stick out there was nothing to start. Fix (one additive file) **[KAM GO]**, done Nov 24: copy `linux-1024mb.bin` (e11da9d2…) to `/ps4hdd/data/payloads/linux-1024mb.bin`, with **no auto-start entry**. Kam still chooses. The internal copy is then available whether the stick is in or out.
  - Option with no PS4 write at all: a tiny **rescue stick** holding only `payloads/linux-1024mb.bin` (no bzImage). Plug it in instead of the main stick and start the loader from it; the loader finds no USB bzImage and boots the HDD pair. It needs a spare USB stick.
- Keep the old good kernel on the stick under its own name (already there: `bzImage.pidfsfix-20261120` = 0bd27266 on both).

### Layer 2 — Boot-once guard with auto-revert (new small script on the Linux root, no payload change) [KAM GO to install]
`trial-guard/jupi-trial-guard.sh` plus `jupi-trial-guard.service` (designed Nov 24; the installed v2 passed 11/11 simulation tests, see `trial-guard/sim-test.log`; superseded by v4 in maintenance/20261125-stability/).
- `arm`: checks hashes, copies the candidate over `bzImage` on the stick and writes a `TRIAL` file. One trial at a time.
- Runs at **every** boot under **any** kernel, because it lives on the Linux root, not on the stick:
  - booted the trial kernel and it stays healthy for 15 min → `TRIAL-PASSED`, keep the new kernel;
  - 3 failed health checks in a row (no eth0 address, Roach <peer-ip> unreachable, sshd down, or a GPU hang/oops in dmesg) → put the good kernel back on the stick and write `TRIAL-REVERTED`;
  - the trial kernel booted a second time without ever passing (it was power-cycled mid-trial) → revert;
  - booted something that is **not** the trial kernel (for example the stick-pulled HDD rescue boot, with the stick plugged back in afterwards) → revert.
- It **never reboots and never powers off**, so it can't make a loop. A Linux reboot on a PS4 lands in Orbis anyway and needs Kam.
- Health probes were dry-run today on both nodes: eth0 up, Roach reachable, sshd active, 0 bad dmesg lines.
- It covers "boots but locked out" (no network, services dead): the next loader start is already back on the good kernel, and Kam only has to power-cycle and start the loader again.
- It does **not** cover a kernel that dies before userspace (black screen, nothing running). Layer 1 covers that: pull the stick.

### Layer 3 — PS4-side ways out (no tools needed)
- **Don't start the loader.** Without it nothing Linux runs. Every cold start is a plain PS4. CONFIRMED (the loader environment isn't stored on the HDD).
- **Hard power-off**: hold the power button until the light goes out. After any GPU hang, pull the AC cord for 60 s before trying again (SUSPECTED to matter on the Pro).
- **Safe Mode** (from fully off, hold power until the second beep, about 7 s; connect the controller with a USB cable): "Restart PS4" boots a clean Orbis; "Rebuild Database" keeps data. **Never** pick "Initialize PS4" (it erases the Linux image and /data, which is what happened Nov 11) or "Update System Software" (the loader may stop working on the new firmware).
- **JUPI 1 auto-start off switch**: remove or disable the auto-start entry (a one-line file on the PS4 disk) **[KAM GO]**. Not needed for the jupi-1.0 test, because pulling the stick already escapes.

### Things to never do (for other users too)
- Don't use a newer upstream loader without checking it: recent builds **auto-copy the USB kernel onto `/data/linux/boot`** (OBSERVED, upstream README), and that would overwrite your rescue copy with the kernel you're testing.
- Don't leave a `bootargs.txt` on the HDD. It also applies to stick boots that have none (each file is searched separately).
- Don't put a stick with a bzImage but no initramfs in the slot: the loader would mix the stick kernel with the HDD initramfs.

### [REBUILD] later, only if wanted
A loader that loads `bzImage.try` once if a `TRY` file exists (deleting the flag first) and otherwise `bzImage`. That's a true A/B with no Linux help. It needs the exact loader source for these firmwares, a build and a careful first test with the escape hatch proven. Not recommended until Layers 1–2 have been proven on hardware.

- groku
