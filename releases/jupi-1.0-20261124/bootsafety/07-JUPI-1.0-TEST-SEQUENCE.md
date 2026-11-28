# Test sequence for kernel jupi-1.0 using the fail-safe
JUPI 2 goes first (no auto-start, so Kam starts each boot by hand), then JUPI 1. Each step shows who does it and whether it needs Kam's go.
Candidate: `bzImage.jupi-1.0` a06fdd7a… (already on both sticks). Known-good: `bzImage.pidfsfix-20261120` 0bd27266… (on both sticks, and currently `bzImage`).

| # | Step | Who | Writes? | Needs |
|---|---|---|---|---|
| 0 | Done today: read-only checks, hashes, health-probe dry run, guard simulation 9/9. | Groku | none | — |
| 1 | JUPI 2: add the internal loader copy `/ps4hdd/data/payloads/linux-1024mb.bin` (e11da9d2…). **No** auto-start entry. Hash read-back, receipt. | Groku | 1 new file on the PS4 HDD | **KAM GO** |
| 2 | Both: install `jupi-trial-guard.sh` + service + `/etc/jupi-trial/conf` (label PS4PROBIN / PS4BOOT). It does nothing until a TRIAL file exists. Run `status`. | Groku | Linux root only | **KAM GO** |
| 3 | JUPI 2 escape-hatch proof: Groku runs `sync`; Kam shuts down → **pulls the stick** → turns on → starts the internal linux-1024mb.bin loader. Expect: desktop, `uname -v` = `#2 SMP PREEMPT_DYNAMIC Sat Mar 14 11:01:12 UTC 2026` (the HDD rescue kernel f0008d46), root loop0 proroot. Then stick back in, full power-off, normal boot → back on 0bd27266. | Kam (physical) + Groku checks | none | **KAM GO** (reboot) |
| 4 | JUPI 2 trial: `jupi-trial-guard.sh arm bzImage.jupi-1.0 a06fdd7a… bzImage.pidfsfix-20261120 0bd27266… '#jupi-1.0'`. This replaces running promote.sh. | Groku | stick: bzImage + TRIAL | **KAM GO** |
| 5 | Kam: full power-off, AC cord out 60 s, turn on, start the loader (stick in). | Kam | none | **KAM GO** (reboot) |
| 6 | Watch: after 3 min, Groku reaches jupi2 from Roach. `postboot-check.sh`, `uname -v` shows `#jupi-1.0`. The guard marks PASSED after 15 healthy min. Then a 24 h soak. | Groku | guard writes TRIAL-PASSED | — |
| 6F | If it fails: hang or black screen → card "bad boot" (pull the stick → internal loader → HDD rescue → plug the stick back → the guard reverts). Locked out → the guard has already reverted; Kam power-cycles and starts the loader again. Either way Groku writes a crash receipt with evidence. | Kam + Groku | guard revert | — |
| 7 | JUPI 1 escape-hatch proof (pull the stick, start the loader, auto-start → HDD pair f0008d46 + cdeaefdb; expect `uname -v` `#2 … Sat Mar 14 11:01:12 UTC 2026`, root loop0 70dbf870). Stick back, normal boot. | Kam + Groku | none | **KAM GO** (reboot) |
| 8 | JUPI 1 trial: `arm` with label PS4BOOT, Kam reboots (the auto-start entry fires), watch as in step 6. Optional Aeolia PHY options stay off (they need bootargs; held). | Groku + Kam | stick | **KAM GO** |
| 9 | After 7 days of passes: decide whether to move the HDD known-good to the new kernel. Default: **leave the HDD frozen.** | Kam | HDD | **KAM GO** |

Never in this sequence: Initialize, firmware updates, auto-start changes on JUPI 2, network changes on JUPI 2, JUPI 1 Wi-Fi/SDIO/BT/musegadget, or reboots without Kam.

- groku
