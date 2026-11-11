# JUPI documentation

Start with **[RUNBOOK.md](RUNBOOK.md)** if JUPI is frozen or unreachable right now.

| Doc | Covers |
|---|---|
| [RUNBOOK.md](RUNBOOK.md) | Freeze & recovery: triage flowchart, R0 warm mux, R1 gauge, R2 shed, R3 restart X, R4 HDMI re-handshake, R5 no-login paths, R6 post-reboot checks, R7 rollback, R8 log housekeeping, quick card |
| [MEMORY.md](MEMORY.md) | Unified memory (RAM + GTT + VRAM carve-out), anatomy of the Nov 10 freeze, health gauge, zones, DESKTOP/COMPUTE discipline |
| [BOOT-CHAIN.md](BOOT-CHAIN.md) | Rescue-shell origin, console OS → payload → kernel → root selector → loop root, exit codes, what is and isn't proven, storage layout |
| [AS-BUILT.md](AS-BUILT.md) | What JUPI is, hardware diagram, sysctl/systemd/zram/earlyoom/display config, lanes & access map, key fingerprints (truncated) |
| [TIMELINE.md](TIMELINE.md) | Nov 5 – Nov 10 life timeline (PST) with sources |
| [OPEN-ISSUES.md](OPEN-ISSUES.md) | Known open issues ranked by risk |
| [RECEIPTS.md](RECEIPTS.md) | Hashes, sizes, boot list, identity anchors |
| [field-manual/](field-manual/) | Typeset PDFs (28-page manual, 2-page digest) + sources + build script |
| [jupi2/](jupi2/) | JUPI 2 (PS4 Pro) final public study PDF, 11 Nov 2026 |
| [BENCHMARK-BASELINE-20261107.txt](BENCHMARK-BASELINE-20261107.txt) | Nov 7 benchmark baseline (pre-existing) |

All of this is the public edition. Addresses and key paths are role placeholders, and fingerprints are truncated.
