# What happened to JUPI 2 on Nov 10–11 (the boot loop that ended in a full PS4 restore)
Built from receipts on Roach (`<lab-home>/groku2/ps4pro/`, `<lab-home>/groku2/receipts/`) and the timestamps on the Pro's HDD. Times are PST.
The PS4 Initialize wiped `/data` and `/user`, so what was on the console before the restore can't be read any more. Everything about "why it looped" is graded with that in mind.

## Timeline
| When (PST) | What | Grade |
|---|---|---|
| Nov 10 4:51–5:20 PM | The loader is started five times (Kam go each time; delivery method out of scope, kept private). Then "Failed to load file: bzImage" on exFAT, and a black-screen hang with no Linux. | CONFIRMED (send receipts, FAT32 receipt) |
| Nov 10 5:18 PM | Groku.2 reformats the stick to FAT32 and adds bzImage, initramfs and `payloads/linux-1024mb.bin` (the loader). | CONFIRMED |
| Nov 10 evening | Linux runs on the Pro. 9:00 PM: disk-boot path ready (pro_internal initramfs → pro-linux.img). | CONFIRMED (DISKBOOT-READY receipt) |
| Nov 11 5:58 AM | The Pro goes dark during a heavy 6-job compile (Vulkan llama build). | CONFIRMED (GPU-PROBE receipt) |
| Nov 11 ~2:31 PM | GPU hang: "asic atom init failed, GPU Recovery Failed". | OBSERVED (SAFEBOOT receipt quotes it) |
| Nov 11 (before 3:00 PM) | Kam: **"The payload keeps killing the pro"** (pt2387u). Every loader attempt ends with the Pro dying. | OBSERVED (Kam's words, quoted in the receipt) |
| Nov 11 3:00 PM | Safe-boot files put on the stick (bootargs.txt nomodeset + fcsafe=1, rescue shell on :2323). | CONFIRMED |
| **Nov 11 ~3:37 PM** | **PS4 Initialize.** The Sony system folders on the user partition are all re-created at 15:37. The loader environment re-creates its folder at 15:41. | CONFIRMED (HDD dir times; rebuild receipt titled "after PS4 Initialize"; musegadget identity "erased by the PS4 Initialize") |
| Nov 11 3:29–4:30 PM | The stick is reworked (cleanboot), pro-linux.img is rebuilt from the stick root, HDD /data/linux/boot is written, and the desktop is back at 4:28 PM. | CONFIRMED |

## Why it kept going to a bad boot (graded)
1. **The stick always wins.** The loader loads bzImage, initramfs and bootargs from USB before the HDD. While the stick held a combination that killed the Pro, every loader run picked that same combination. There was no second, known-good choice that could be reached by hand, because on Nov 11 the HDD had no boot pair until the rebuild. CONFIRMED (search order). The empty HDD before the rebuild is SUSPECTED: the files are dated after the Initialize, and nothing earlier is recorded.
2. **The GPU stayed in a bad state between tries.** After the 2:31 PM GPU hang, each new loader run resets the GPU and reconfigures VRAM before Linux even starts. A PS4 "restart" or rest mode does not fully power the APU down, so the next try can die the same way. A full AC drain (cord out for 60 s) was the suggested fix. SUSPECTED (hypothesis in the Nov 11 receipt, never proven).
3. **Something started GPU work on every boot** (the desktop through radeonsi, or a bench/Vulkan job), so even a good kernel hit the bad GPU straight away. SUSPECTED (safe-boot plan; never confirmed because the Initialize came first).
4. **"Automatic":** whether something started the loader by itself on the Pro before the Initialize cannot be proven now: /data was erased and no receipt shows an auto-start entry being written to the Pro. UNSOURCED.
   Either way, the loader also says "kexec successfully armed. Please shut down the system": once it has run, the next shutdown or restart of the PS4 system goes into Linux. OBSERVED (binary strings).
5. **Why there was no way back in:** no keyboard escape (`panic=0` hang, no SysRq), no network while hung, the stick couldn't be pulled to fall back to the HDD, and nobody had written down "pull the stick" as an escape. The Initialize "worked" because it erased everything that could restart the bad path: /data (any auto-start entry, loader configuration, cached files) and /user/home (the Linux image). It also cost the Linux image, the musegadget identity and the setup. CONFIRMED (rebuild receipts).

## Lessons (these feed the design)
- Always keep **two** boot sets: the stick (what you're testing) and the HDD (frozen known-good). Never change both on the same day.
- The loader itself must stay reachable **without** the stick. Put an internal copy in /data/payloads on JUPI 2.
- Write the escape down where Kam can see it, as a printed card.
- **Never Initialize** unless the Linux image is backed up somewhere. Initialize is the most destructive way out, not the first one to try.
- Fully power off (or pull the AC cord for 60 s) after any GPU hang before trying again.

- groku
