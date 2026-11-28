# JUPI 1.0 release package (2026-11-24)


Kernel 1.0 + boot safety + the JUPI MANUAL v1.0, for JUPI 1 (PS4) and JUPI 2 (PS4 Pro).
Prepared by groku (Groku.2) for Kam Dabe, FullCircle ComXpress LLC. Black and white. Plain words.

Start here: `manual/JUPI-MANUAL-v1.0.md` (also as PDF). Print the two recovery cards.

| Folder | What |
|---|---|
| manual/ | JUPI MANUAL v1.0 (md + pdf), recovery cards v1.1 for JUPI 1 and JUPI 2 (txt + pdf) |
| kernel/ | jupi-1.0 kernel: 4 patches, full config, config diff vs live, build script, build receipt, analysis, perf, install/test/rollback plan |
| bootsafety/ | how each JUPI boots, the Nov 11 boot-loop reconstruction, the fail-safe design, the 1.0 test sequence, and the trial guard v2 (script, unit, installer, rollback, simulation test 11/11) |
| flown-20261127/ | what was tested on hardware: status matrix, TRIAL-PASSED records, receipts, rebuild proof and recipe, portable REBUILD.md |
| opcount/ | why the fc-nods128 op counts were 2754/1109 vs 2722/1093 (duplicate case names), with evidence |

## Status (be precise)

Current matrix: [flown-20261127/STATUS-20261127.md](flown-20261127/STATUS-20261127.md). Short form (Nov 27):

| Thing | Status | Grade |
|---|---|---|
| jupi-1.0 kernel | installed on both consoles' internal drives; guarded cold boot passed on both (Nov 24); both running it stickless | CONFIRMED |
| Trial guard | v2 installed idle Nov 24; v4 source in [maintenance/20261125-stability/](../../maintenance/20261125-stability/) | CONFIRMED (v2 install), tests only (v4) |
| JUPI 2 internal loader copy in /data/payloads | in place, no auto-start entry | CONFIRMED |
| jupi-update command | design only, not published | - |
| kexec Linux->Linux on PS4 | reported to freeze by others; untested here | OBSERVED |

## Verify

```
sha256sum -c SHA256SUMS
```

## Scope

This package covers the kernel, the boot-safety design and the manual. Linux is started on the console with a
PS4 Linux loader; how that loader is delivered is out of scope and kept private. The sky2 Aeolia patches in
`kernel/patches` come from Codex (credited in `kernel/README-BUILD.md`).

- groku
