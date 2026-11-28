# JUPI MANUAL v1.0

FullCircle ComXpress LLC. Written by groku for Kam Dabe. Tue Nov 24 2026 (PST).
Black and white on purpose. Print it. Keep it next to the machine.

How to read this manual:
- Every fact has a grade. CONFIRMED = we checked it on our own machines or in source code.
  OBSERVED = a published source says it; we have not tested it. SUSPECTED = our best reading.
  UNSOURCED = nobody has a source.
- Every file has a sha256 "fingerprint". Section 12 shows how to check one. If the fingerprint
  matches, you have the exact same file we tested. If it doesn't, stop and ask.
- Box = "do this". Plain text = "why".

-----------------------------------------------------------------

## 1. What JUPI is

JUPI (Joint Unix Platform Integrator) is an old PlayStation 4 that runs Linux instead of games.
It becomes a small, quiet science computer: it can run a local AI model (answers stay in the room),
do maths on its graphics chip, store data, and talk to other JUPIs over a cable.

Why: these machines are e-waste. Their memory and graphics chips still work. Reusing them is
recycling at the scale of compute.

How it starts, in one line: a small PS4 Linux loader (`linux-1024mb.bin`) is started on the console
and hands the machine to Linux. How that loader is delivered to the console is out of scope for this
repo and kept private. (CONFIRMED, see section 4.)

There are two in the rack today:

| Name | Console | Starts Linux | Boot stick label |
|---|---|---|---|
| JUPI 1 | PS4 (CUH-1001A, "Aeolia" chip) | by itself (auto-start entry) | PS4BOOT |
| JUPI 2 | PS4 Pro ("Belize" chip) | a person picks it each time | PS4PROBIN |

-----------------------------------------------------------------

## 2. Hardware list

| Item | Why | Grade |
|---|---|---|
| PS4 or PS4 Pro already able to start a PS4 Linux loader | the machine | CONFIRMED (both units) |
| One USB stick, FAT32, for boot files (512 MB is enough) | holds the kernel | CONFIRMED |
| Optional second small USB stick, "RESCUE", loader only | spare way in | design |
| Wired network cable + switch | JUPI is used over the network | CONFIRMED |
| TV/monitor (HDMI) + controller with USB cable | for start-up and Safe Mode | CONFIRMED |
| Another computer on the same network (any Linux/Mac/Windows) | to log in, check fingerprints | CONFIRMED |
| This manual + the recovery card for each unit, printed | | |

Firmware: keep the PS4 system software exactly as it is (section 3). Which firmware versions can start
the loader depends on how you start it; that is outside this manual.

-----------------------------------------------------------------

## 3. NEVER do these

| Never | Why |
|---|---|
| "Initialize PS4" (Settings or Safe Mode) | Erases the disk, Linux included. This is how JUPI 2 was lost on Nov 11. (CONFIRMED) |
| "Update System Software" | A new firmware may not support your loader method. Then Linux can't start. |
| Set up an auto-start entry for the loader on JUPI 2 or on a new unit | A bad auto-started loader can trap the console in a crash loop. Others report the same. (OBSERVED) |
| Pull the power cord while Linux is writing | Can damage files. Hold the power button instead. |
| Swap boot sticks between JUPI 1 and JUPI 2 | Each stick has its own label and files. |
| Change the loader to "update" JUPI | Updates are files on the stick, done from Linux (section 7). The loader stays fixed. |
| Run loaders or programs you didn't get from this manual's list | They can harm the console. |

-----------------------------------------------------------------

## 4. How the start-up works (the loader)

Think of it as a key and a door. The key is the PS4 Linux loader. How the loader is started on the
console is out of scope for this repo and kept private. Everything below assumes you already have a
working way to start it.

1. The loader `linux-1024mb.bin` is started on the console. It can live on a USB stick (`payloads`
   folder) and, as a spare, on the PS4's own disk (`/data/payloads`).
2. The loader reads up to four files, each one separately, first place wins
   (CONFIRMED in source and in our loader):
   1. USB stick 1, then USB stick 2, then the PS4 disk `/data/linux/boot/`
   2. Files: `bzImage` (the kernel, required), `initramfs.cpio.gz` (required),
      `bootargs.txt` (options, optional), `vram.txt` (graphics memory, optional).
3. Linux starts. The PS4 menu is gone until you power off.

JUPI 1 starts Linux by itself on power-up (an auto-start entry for the loader is set up on that unit).
JUPI 2 has no such entry. Nothing starts by itself on JUPI 2 (CONFIRMED Nov 24).

The loader never copies anything to the disk on our units (CONFIRMED). It never changes by itself.

The loader file, same on every unit:
`linux-1024mb.bin`, 329,088 bytes, sha256 e11da9d2f772bd2619587d1bc3bd49b257876d1b298fd4f01e1a1139414b6646 (CONFIRMED).

-----------------------------------------------------------------

## 5. First setup (per console)

Before you start: you must already have a working way to start the PS4 Linux loader on the console.
This manual does not cover how to get one.

### 5a. Both consoles
1. Format a USB stick FAT32. Label it (PS4BOOT for a PS4, PS4PROBIN for a Pro, or your own name).
2. Copy onto it: `bzImage`, `initramfs.cpio.gz`, and a `payloads/linux-1024mb.bin` (the loader).
   Check each fingerprint against the list in section 13 before copying.
3. Copy the loader a second time onto the PS4 disk at `/data/payloads/linux-1024mb.bin`
   (by any file transfer to the PS4 disk, or from Linux later). This is your spare key when the stick is bad.
4. Copy a known-good `bzImage` + `initramfs.cpio.gz` into `/data/linux/boot/` on the PS4 disk.
   This is the backup kernel used when no stick is plugged in.

### 5b. PS4 (like JUPI 1)
- Start: start the loader `linux-1024mb.bin` the way you normally do.
- Optional auto-start (only once the unit has booted cleanly at least 3 times): set up an auto-start
  entry for the loader, then Linux starts by itself.
- Escape when it auto-starts a bad kernel: pull the stick (it falls back to the disk backup).

### 5c. PS4 Pro (like JUPI 2)
- Start: start the loader `linux-1024mb.bin` the way you normally do. No auto-start. A person starts it every time.
- Escape when the stick is bad: pull the stick, then start the INTERNAL copy of the loader, `/data/payloads/linux-1024mb.bin`.
  JUPI 2 got this internal copy on Nov 24 2026 16:42 PST (CONFIRMED, Nov 24 change receipt).
  JUPI 2 then booted jupi-1.0 with the stick out that evening, and it has no auto-start, so that start
  can only have come from the internal copy (inferred; see flown-20261127/STATUS-20261127.md).

After Linux starts the first time:
- Wait 2-3 minutes. A black screen for 1-2 minutes is normal.
- Log in from the other computer over SSH.
- Run `uname -v` and write down what it says (that is which kernel booted).

-----------------------------------------------------------------

## 6. Everyday use

| Want to | Do | Grade |
|---|---|---|
| Ask the local AI something (JUPI 1) | `ollama run llama3.2:1b` (also installed: `qwen3:0.6b`) | CONFIRMED installed, Nov 24 |
| Run a local model on JUPI 2 | llama.cpp Vulkan build in `<lab-home>/groku-infer/` | CONFIRMED installed |
| Check the machine | `jupi-system` (JUPI 1) | CONFIRMED |
| See the GPU engine | `systemctl status jupi-engine` | CONFIRMED running on both |
| Turn it off | `sudo poweroff`, wait for the light to go off | |
| Turn it on again | start the loader again (section 4/5) | |

Nothing restarts JUPI by itself: kernel `panic=0`, and the self-heal service has reboots turned off
(CONFIRMED). If it hangs, a person decides.

-----------------------------------------------------------------

## 7. Updating JUPI (the safe way)

The rule: the launcher (the loader) never changes. An update only changes files on
the stick, from inside Linux, and every update can undo itself.

The tool that does the undo is the TRIAL GUARD (installed Nov 24 2026, idle, on both units; CONFIRMED):
- `/usr/local/sbin/jupi-trial-guard.sh` sha256 15ea6e93b6fb6fae96a74519da752b10fd357ede12bc7e6a0dbb5497b05ef085
- `/etc/systemd/system/jupi-trial-guard.service` sha256 5fbe9332a2e963f4cb3d9d1fb7ae0ade0b0dcdb26fd6dd6a156af0f68a58fba5

How a kernel update goes:
1. Copy the new kernel to the stick with a new name, e.g. `bzImage.jupi-1.0`. Check its sha256.
2. Arm one trial:
   `sudo jupi-trial-guard.sh arm bzImage.jupi-1.0 <new-sha> bzImage.pidfsfix-20261120 <good-sha> jupi-1.0`
   It refuses if a fingerprint is wrong.
3. Restart JUPI the normal way.
4. The guard checks every minute: network up, the peer answers, SSH running, no GPU hang/Oops.
   - 15 healthy minutes -> PASS. The new kernel stays.
   - 3 bad checks in a row -> REVERT. The old kernel is put back on the stick. Restart once more.
   - If the new kernel can't even start Linux: turn off, pull the stick, start (disk backup kernel),
     plug the stick back in, then run `sudo jupi-trial-guard.sh revert` (puts the old kernel back on
     the stick; the guard does not watch for a re-plugged stick by itself).
5. `sudo jupi-trial-guard.sh status` shows where you are. The log is `/var/log/jupi-trial.log`.

Stop switch: `sudo touch /etc/jupi-trial/DISABLE` (guard does nothing at all).
The guard never restarts or powers off the machine (CONFIRMED in code and in 11/11 simulated tests).
When idle it only reads the stick (CONFIRMED: whole-stick fingerprint identical before and after).

Coming later: one command, `sudo jupi-update <file> <sha256>`, that does steps 1-2 for you
(design only today; not published).

Not used for updates: kexec (Linux starting another Linux directly). It is built in, but others
report it freezes on PS4 (OBSERVED). Untested by us.

-----------------------------------------------------------------

## 8. Recovery card - JUPI 1 (PS4, auto-start)

GOLDEN RULE: something wrong -> PULL THE STICK first. Without the stick, JUPI 1 boots the
known-good backup kernel on its own disk. NEVER "Initialize PS4".

| If | Do |
|---|---|
| Linux won't start ("Failed to load file", or back at PS4 home) | Turn fully off. Push the stick in. Turn on, start the loader, wait 3 min. Still nothing: off, PULL THE STICK, on, start the loader (backup boot). |
| Bad boot every time (black or frozen) | Hold power until the light is OFF. Pull the stick. Turn on, start the loader. Once Linux is up, plug the stick back in. |
| Linux is up but unreachable | Wait 15 min (trial guard may be fixing it). Check the cable. Off, on, start the loader. Then pull-the-stick boot. |
| Black screen | Wait 3 full minutes. Ask the other computer "can you reach JUPI 1?". If not: hold power until off, pull AC 60 s, pull the stick, start. |
| PS4 itself won't start normally | Safe Mode: from OFF, hold power until the SECOND beep (~7 s), connect the controller by cable, press PS, choose "Restart PS4". NEVER Initialize. NEVER Update. |

-----------------------------------------------------------------

## 9. Recovery card - JUPI 2 (PS4 Pro, no auto-start)

GOLDEN RULE: something wrong -> turn fully OFF and PULL THE AC CORD FOR 60 SECONDS. NEVER "Initialize PS4".
Normal start: start the loader `linux-1024mb.bin` (from the stick) the way you normally do.

| If | Do |
|---|---|
| Linux won't start | Turn fully off. Push the stick in. Start the loader, wait 3 min. Still nothing: BACKUP BOOT. |
| Bad boot every time | Hold power until OFF. Pull AC 60 s. BACKUP BOOT. |
| BACKUP BOOT | Pull the PS4PROBIN stick. Start the INTERNAL copy of the loader, `/data/payloads/linux-1024mb.bin` (exists since Nov 24 2026). Linux starts from the disk backup kernel. Then plug the stick back in. (Passed on JUPI 2 the evening of Nov 24, see flown-20261127/STATUS-20261127.md.) |
| Linux up but unreachable | Wait 15 min. Check the cable. Off, on, start the loader. Then BACKUP BOOT. |
| Black screen | Wait 3 min. Ask the other computer "can you reach JUPI 2?". If not: off, AC 60 s, try once more, then BACKUP BOOT. |
| PS4 itself won't start normally | Don't start the loader. Safe Mode: hold power to the SECOND beep, controller by cable, PS, "Restart PS4". NEVER Initialize. NEVER Update. |

-----------------------------------------------------------------

## 10. Troubleshooting table

| You see | Most likely | Do | Grade |
|---|---|---|---|
| "Failed to load file" after starting the loader | stick not found or file missing | re-seat stick; check `bzImage` and `initramfs.cpio.gz` on it | CONFIRMED (loader source) |
| Loader file not found | stick not plugged, or no `payloads` folder | plug stick; use the internal copy | OBSERVED |
| Crash/restart right after the loader starts, every time | a bad auto-start entry | pull the stick; remove the entry | OBSERVED (others) |
| Black screen 1-2 min | normal | wait 3 min | CONFIRMED |
| Linux up, no network on JUPI 1 | known Aeolia network IRQ issue | wait; check cable; see kernel 1.0 notes | CONFIRMED (issue known) |
| `jupi-trial-guard status` says ARMED | an update trial is running | wait 15 min | CONFIRMED |
| `TRIAL-REVERTED` on the stick | the new kernel failed, old one restored | restart once; read `/var/log/jupi-trial.log` | CONFIRMED (sim) |
| Fingerprint doesn't match | wrong or damaged file | do not use it; ask | - |

-----------------------------------------------------------------

## 11. Glossary

- Orbis: the PS4's own operating system.
- Firmware: the PS4 system software version (e.g. 13.52). Don't update it.
- Loader: a small program (`linux-1024mb.bin`) that starts Linux on the PS4 with 1024 MB of graphics memory.
- Kernel (`bzImage`): the core of Linux. initramfs: a small start-up file system loaded with it.
- Boot stick: the USB stick with the kernel files.
- Trial guard: the program that keeps or undoes a kernel update by itself.
- sha256: a 64-character fingerprint of a file. Same fingerprint = same file.
- Receipt: a note of what changed, when (PST), who approved it, and the fingerprints.
- kexec: Linux starting another Linux without the PS4 menu. Not used for updates.

-----------------------------------------------------------------

## 12. Who to ask, and how to check a receipt

Owner and final say: Kam Dabe, FullCircle ComXpress LLC. Ask Kam before any restart test, any
change to the auto-start entry, the loader, or network settings.

Check a fingerprint (Linux/Mac):
```
sha256sum linux-1024mb.bin
```
Windows PowerShell:
```
Get-FileHash linux-1024mb.bin -Algorithm SHA256
```
Compare all 64 characters with this manual or the package's SHA256SUMS.

Check a whole package folder:
```
sha256sum -c SHA256SUMS
```
Every line must say OK.

A receipt is trusted when: it names what changed, when, who approved it, it has before/after
listings, it has a rollback line, and the fingerprints in it match the files.

-----------------------------------------------------------------

## 13. Known-good fingerprints (Nov 24 2026)

| File | Where | sha256 | Grade |
|---|---|---|---|
| linux-1024mb.bin (loader) | stick `payloads/`, and `/data/payloads/` on JUPI 2 | e11da9d2f772bd2619587d1bc3bd49b257876d1b298fd4f01e1a1139414b6646 | CONFIRMED |
| bzImage (Nov 20, pidfs fix, running today) | both sticks | 0bd2726640d571c1c28fad7a721ba7db65e04472adcb7f7674312ecf9d72b289 (also kept on the stick as bzImage.pidfsfix-20261120) | CONFIRMED |
| bzImage (original crashnt-4.7, disk backup) | `/data/linux/boot/` | f0008d466329d07d456fda63fe03129f7af0403a4040d357d3a62658e3d17293 | CONFIRMED |
| bzImage-jupi-1.0 (not published; hash only) | internal HDD on both units since Nov 24 | a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e | CONFIRMED (built; flown, see flown-20261127/STATUS-20261127.md) |
| jupi-trial-guard.sh v2 | `/usr/local/sbin/` | 15ea6e93b6fb6fae96a74519da752b10fd357ede12bc7e6a0dbb5497b05ef085 | CONFIRMED |

- groku
