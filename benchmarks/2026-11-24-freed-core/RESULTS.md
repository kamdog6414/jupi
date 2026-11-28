# Freed-core benchmarks: JUPI 1 before/after, JUPI 1 vs JUPI 2 (Nov 24 2026)

Grades: CONFIRMED = measured by me this run from the raw logs here, repeatable, same binary/model/args; OBSERVED = measured once or cross-run/cross-day comparison; baseline rows are from earlier receipts and graded as stated. Kernel `#jupi-1.0` on both consoles, stickless, HDD roots. JUPI 1 has `sky2.aeolia_poll_phy=1`; JUPI 2 has no poll_phy (no storm there).

## 1. Headline: CPU 1 freed on JUPI 1

| metric | before (poll off) | after (poll on) | change | grade |
|---|---:|---:|---:|---|
| eth0 IRQ 24 rate, idle | ~3,590 /s | ~14 /s (10 s idle sample, includes my ssh traffic; ~1.4/s in the first post-boot check) | -99.6% | CONFIRMED (before: Codex trace, 3,590 entries in 1.002 s) |
| CPU1 softirq at 100% before | 100% | 0.0% in every CPU benchmark (all 8 cores loaded) | storm gone | CONFIRMED |
| 4 workers incl. CPU 1 (mask 0,1,4,6): FP32 SGEMM GFLOP/s | 1.87 | 26.63 | **14.2x** | CONFIRMED (same pinned fixture sha 63adf7b6, same harness logic) |
| same mask: sysbench prime events/s | 2,169 | 2,997 | 1.38x | CONFIRMED |
| same mask: triad logical GB/s | 1.9 | 10.21 | 5.4x | CONFIRMED |
| best prime before (7 cores, no CPU 1) vs all 8 cores now | 4,879 | 5,986 | 1.23x | CONFIRMED |
| best SGEMM before (6 cores) vs all 8 cores now | 33.21 | 51.21 | 1.54x | CONFIRMED |
| healthy-four (0,2,4,6) sanity: prime / SGEMM | 2,920 / 26.32 | 2,982 / 26.61 | ~same | CONFIRMED (control: unchanged cores did not move, so the gain is CPU 1) |
| llama.cpp qwen3-0.6B Q4_K_M tg128 t=4 | 11.77 tok/s (Nov 10, load avg 12-15, CPU1 storm) | 13.57 | 1.15x | OBSERVED (different day and load; same commit 3b4d6ab, model sha 7f403014, args) |
| llama.cpp 0.6B pp512 t=4 | 32.17 | 35.90 | 1.12x | OBSERVED |
| llama.cpp 0.6B tg128 t=6 | 6.77 (storm contention) | 18.35 | 2.71x | OBSERVED |
| llama.cpp 0.6B t=8 tg128 | UNKNOWN (killed by 20-min timeout) | 22.00 (pp512 65.48) | now completes | CONFIRMED |
| llama.cpp 1.7B Q4_K_M tg128 t=4 | 4.44 | 5.73 | 1.29x | OBSERVED |

Caveat on the llama rows: the Nov 10 baseline ran under heavy load (ChatGPT, grok-bot, codex), so the t=4 gain mixes the freed core with a quiet machine. The mask table above is the controlled before/after (same fixture, same masks). Baseline sources: `jupi1-pollphy-20261124/inputs/performance.json`, `~/groku-infer/RESULTS-20261110T074751Z.md` on JUPI 1.

## 2. CPU by core mask (median of 2 passes in opposite order; fixture pinned sha 63adf7b6, binary 1ec56bcf on both consoles)

| mask | cores | J1 prime ev/s | J1 SGEMM GF | J1 triad GB/s | J2 prime ev/s | J2 SGEMM GF | J2 triad GB/s | J2/J1 prime | J2/J1 SGEMM |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| healthy-four | 0,2,4,6 | 2,982 | 26.61 | 10.21 | 3,939 | 34.91 | 15.19 | 1.32x | 1.31x |
| cpu1-four | 0,1,4,6 | 2,997 | 26.63 | 10.21 | 3,940 | 34.96 | 15.16 | 1.31x | 1.31x |
| healthy-six | 0,2,3,4,5,6 | 4,491 | 39.34 | 11.19 | 5,911 | 51.47 | 16.02 | 1.32x | 1.31x |
| seven-no-cpu1 | 0,2,3,4,5,6,7 | 5,241 | 42.24 | 10.58 | 6,889 | 55.07 | 15.01 | 1.31x | 1.30x |
| seven-with-cpu1 | 0,1,2,3,4,5,6 | 5,240 | 42.09 | 10.69 | 6,890 | 54.80 | 14.97 | 1.31x | 1.30x |
| all-eight | 0,1,2,3,4,5,6,7 | 5,986 | 51.21 | 11.88 | 7,790 | 60.36 | 16.91 | 1.30x | 1.18x |

All runs: zero fixture mismatches (verified arithmetic). CONFIRMED.

### Per-core (sysbench prime 10000, 1 thread pinned, events/s)

| CPU | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| JUPI 1 | 749.0 | 749.0 | 749.0 | 747.3 | 749.1 | 748.8 | 749.1 | 748.8 |
| JUPI 2 | 985.0 | 985.0 | 984.5 | 985.1 | 984.8 | 984.4 | 984.9 | 984.9 |

JUPI 1 CPU 1 now matches its siblings (spread 747.3 to 749.1). JUPI 2 per-core is 1.32x JUPI 1. CONFIRMED.

### sysbench cpu, prime 20000, 10 s, unpinned (events/s)

| threads | JUPI 1 | JUPI 2 | J2/J1 |
|---:|---:|---:|---:|
| 1 | 293.3 | 385.6 | 1.31x |
| 2 | 586.6 | 770.9 | 1.31x |
| 4 | 1,173.5 | 1,542.4 | 1.31x |
| 6 | 1,760.2 | 2,313.5 | 1.31x |
| 7 | 2,051.9 | 2,698.9 | 1.32x |
| 8 | 2,342.9 | 3,072.9 | 1.31x |

JUPI 1 scaling 1 to 8 threads: 7.99x (ideal 8). JUPI 2: 7.97x. CONFIRMED.

### 7-Zip benchmark (`7z b`, total rating MIPS) and OpenSSL (MB/s at 16 KiB blocks)

| test | JUPI 1 | JUPI 2 | J2/J1 |
|---|---:|---:|---:|
| 7z b, 8 threads, total MIPS | 12,565 | 16,646 | 1.32x |
| 7z b, 4 threads on CPUs 0,2,4,6, total MIPS | 6,910 | 9,309 | 1.35x |
| openssl aes-128-cbc, 1 core | 486 | 637 | 1.31x |
| openssl aes-128-cbc, -multi 8 | 3,358 | 5,102 | 1.52x |
| openssl sha256, 1 core | 90 | 119 | 1.32x |
| openssl sha256, -multi 8 | 724 | 954 | 1.32x |

No pre-freed baseline exists for 7z/openssl on JUPI 1. CONFIRMED as current values only.

## 3. Memory

Real DRAM streaming is the triad column above (96 MB working set, 3 arrays): JUPI 1 10.2 to 11.9 GB/s by mask, JUPI 2 14.7 to 16.9 GB/s. The sysbench memory test uses a 1 MiB block that stays in cache, so its MiB/s are cache speed, not DRAM; shown for completeness (the write t=4 on JUPI 2 and t=8 on JUPI 1 dip below lower thread counts: noisy, single 8 s sample, OBSERVED). Earlier receipts quote a 130 GB/s figure that this run does not reproduce (OBSERVED, not re-derived here).

| sysbench memory seq, 1 MiB block (MiB/s) | JUPI 1 | JUPI 2 |
|---|---:|---:|
| read t=1 | 6,009 | 8,252 |
| read t=2 | 12,770 | 16,126 |
| read t=4 | 25,512 | 30,661 |
| read t=8 | 49,789 | 65,580 |
| write t=1 | 4,334 | 5,725 |
| write t=2 | 8,647 | 11,490 |
| write t=4 | 17,322 | 4,989 |
| write t=8 | 6,076 | 7,538 |

## 4. Local LLM, llama.cpp CPU (same binary sha 596d83ac, commit 3b4d6ab, `-p 512 -n 128`, tok/s mean)

| config | J1 pp512 | J1 tg128 | J2 pp512 | J2 tg128 | J2/J1 tg | Nov 10 J1 baseline tg |
|---|---:|---:|---:|---:|---:|---|
| 0.6B Q4_K_M, t=1 | 9.53 | 3.89 ± 0.00 | 11.54 | 5.03 ± 0.00 | 1.29x | - |
| 0.6B Q4_K_M, t=2 | 18.95 | 7.13 ± 0.03 | 24.68 | 9.54 ± 0.00 | 1.34x | - |
| 0.6B Q4_K_M, t=4 | 35.90 | 13.57 ± 0.01 | 47.51 | 17.69 ± 0.00 | 1.30x | 11.77 |
| 0.6B Q4_K_M, t=6 | 47.84 | 18.35 ± 0.42 | 61.26 | 23.78 ± 0.00 | 1.30x | 6.77 |
| 0.6B Q4_K_M, t=7 | 53.40 | 20.16 ± 0.12 | 71.12 | 25.64 ± 0.01 | 1.27x | - |
| 0.6B Q4_K_M, t=8 | 65.48 | 22.00 ± 0.66 | 83.33 | 27.71 ± 0.81 | 1.26x | unknown |
| 0.6B, t=4 pinned 0,2,4,6 | 35.17 | 13.56 ± 0.05 | 47.32 | 17.72 ± 0.01 | 1.31x | - |
| 0.6B, t=6 pinned 0,2,3,4,5,6 | 47.70 | 18.59 ± 0.03 | 61.17 | 23.85 ± 0.03 | 1.28x | - |
| 1.7B Q4_K_M, t=4 | 13.27 | 5.73 ± 0.00 | 17.82 | 7.37 ± 0.00 | 1.29x | 4.44 |
| 1.7B Q4_K_M, t=8 | 25.53 | 8.52 ± 1.47 | 32.10 | 12.03 ± 0.02 | 1.41x | - |

JUPI 2 t=4 tg128 17.69 vs its Nov 10-11 records 17.29/17.34/17.42: consistent. CONFIRMED (current), OBSERVED (vs earlier day). GPU inference not run: Vulkan on radv 21.3.2 produced garbage output on JUPI 1 (RESULTS-20261110T074751Z.md) and was not re-tested here.

## 5. Disk (fio, O_DIRECT, 2 GiB file on the HDD-backed loop root, 20 s each)

| test | JUPI 1 MB/s | JUPI 1 IOPS | JUPI 2 MB/s | JUPI 2 IOPS |
|---|---:|---:|---:|---:|
| seqread-1M-qd4 | 62.4 | 59 | 59.2 | 56 |
| randread-4k-qd1 | 1.0 | 249 | 1.2 | 281 |
| randread-4k-qd32 | 2.1 | 501 | 2.2 | 548 |
| seqwrite-1M-qd4 | 83.4 | 79 | 63.6 | 60 |

Both read through dm-crypt + loop + spinning HDD (JUPI 2's drive is larger). CONFIRMED. The 2 GiB test file was created and deleted by the harness (own file only).

## 6. Network (wired eth0, gigabit link both)

- Ping to Roach, 20 packets: JUPI 1 rtt min/avg/max/mdev = 1.432/1.691/2.324/0.181 ms. JUPI 2: ping to Roach 1.5 ms in the earlier stickless check (not repeated in suite).

- 1 GiB ssh stream with Roach, timed from JUPI 1: to Roach 12.6 s (85 MB/s), from Roach 13.0 s (83 MB/s). Timed from Roach with the console's counters (two runs on JUPI 1, one on JUPI 2): see net-roach/. JUPI 1 58 to 69 MB/s, JUPI 2 75 to 77 MB/s. These are ssh-crypto bound on a Jaguar core, not line rate. OBSERVED.
- **IRQ 24 with traffic context:** during the 7:55 PM recheck IRQ 24 counted ~338/s, because my 1.1 GB pacman download was running (about 2.3 MB/s average over ~8 minutes, real packets). During ssh streams it ran 4,900 to 7,400 IRQs/s with CPU 1 softirq 15 to 28 ticks/s (15 to 28% of one core at HZ=100) and the other cores near zero. So real traffic still lands on CPU 1 (IRQ affinity), proportional to packets; idle is ~14/s and 0% softirq. The storm was 3,590/s with zero packets. JUPI 2 shows the same traffic-proportional pattern (CPU 1 9.8 to 27.4 ticks/s). CONFIRMED (counters from /proc/interrupts and /proc/stat).
- **iperf3 not run.** Both consoles have a deliberate nft input-drop firewall (JUPI 1 table `jupi`, JUPI 2 `jupi_integrator_peer`, only tcp 22 open) and Roach runs ufw. Opening a port is a live-service change, so I did not. iperf3 3.22 is installed on both for when Kam says go.

## 7. Games on screen (real X session :0, user pi, 1920x1080)

| benchmark | JUPI 1 (Mesa-ps4 21.3.2 radeonsi, HDMI-A-0 connected) | JUPI 2 (Mesa 26.2.6 radeonsi, HDMI-1 reported disconnected) |
|---|---|---|
| glmark2 2023.01 score (1080p, `--fullscreen --annotate`; window came up maximized) | **2763** | **1059** |
| glmark2 frame time (median of 35 tests) | 0.278 ms | 0.837 ms |
| glmark2 FPS min / median / max over tests | 370 / 3592 / 3940 | 91 / 1195 / 1488 |
| Xonotic 0.8.6 `-benchmark demos/the-big-keybench` 1080p, 35,534 frames, default quality | **80.5 fps avg** over 441 s; 1-second fps min/avg/max 52/83/123; mean frame time 12.4 ms | **126.3 fps avg** over 281 s; min/avg/max 61/129/193; mean frame time 7.9 ms |

On-screen proof (JUPI 1, ffmpeg x11grab of :0): `shots/glmark2-j1-1.png` (terrain scene) and `shots/xonotic-j1-1.png` (Xonotic with its own fps counter, 64 fps at that moment, 58/78/123 one-second min/avg/max). OBSERVED. I could not see the TVs; the screenshots are the X server's framebuffer.

Notes, all OBSERVED: (a) JUPI 2's DRM connector status read `disconnected` and xrandr agrees, so there may be no live TV on the Pro's HDMI (cable, input or TV off); the benchmark still rendered to the 1920x1080 X screen on hardware GL (radeonsi), so the numbers are valid but nobody could have watched it. (b) The two consoles use different Mesa builds (21.3.2 PS4 build vs 26.2.6), so the JUPI 1 vs JUPI 2 GPU comparison mixes hardware and driver; glmark2 on JUPI 2 sat near a flat ~1,400 fps (driver/compositor bound) while Xonotic, which is GPU/CPU heavy, ran 1.57x faster on the Pro. (c) glmark2 per-test FPS on JUPI 1 plateaus near 3,600 to 3,900 on light tests (same style of ceiling). (d) No pre-freed game baseline exists for JUPI 1 (would need the old kernel), so games carry no before/after claim; Xonotic keybench is partly CPU-bound and should gain from CPU 1, SUSPECTED, not measured. (e) Real-time reaction latency, Kam's headline metric for game-play runs, was not measured by these timedemos; they report throughput fps and one-second min fps only.

## 8. Thermals and memory safety

JUPI 1 k10temp: idle 72 to 77 C, peak 86 C (end of glmark2), llama runs 74 to 82 C. JUPI 2: idle 65 C, peak 81 C (glmark2). The hwmon `high` threshold prints 70 C and `crit` 100 C; the harness aborted nothing (guard 95 C). MemAvailable never fell below ~5.0 GiB on either console. No swap thrash. Nothing of Kam's was closed. One bench at a time per console. CONFIRMED (per-step min/max in each step's .json).

## 9. What misbehaved

- `openssl speed -evp a -evp b` is invalid syntax; the first openssl step failed instantly on JUPI 2 (rc=1, 0.1 s). Fixed in suite2.py and rerun on both; logs from the failed attempt were overwritten by the rerun.
- JUPI 2 first `pacman -S` failed (Landlock unsupported by the kernel; then stale db 404s). Installed from JUPI 1's package cache with `pacman -U` and `pacman -S --disable-sandbox openblas`. No database sync, no system upgrade. Side effect: pacman created system users `gluster` and `rpc` on JUPI 2 (glusterfs/rpcbind came in as fio dependencies; no services enabled).
- Roach and NIKOLAI shells dropped out for a few seconds several times ("temporarily unreachable"); no benchmark was affected.
- JUPI 1 boot-time journal errors at the 15-minute check (ACPI mutex errors, `usb 4-1 device not accepting address`, `EXT4-fs (loop0): write access unavailable, skipping orphan cleanup`, `apcie_irq_msi_compose_msg`) are all stamped 03:37:20 to 03:37:32 GMT, i.e. boot time, none repeated afterwards. OBSERVED.
- sysbench mem is cache-resident (see section 3).

