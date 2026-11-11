# JUPI 2 (PS4 Pro) benchmarks: full tables

> Public edition. Text companion to [JUPI2-FINAL-20261111.pdf](JUPI2-FINAL-20261111.pdf). It carries the raw tables the PDF summarizes or leaves out. Every figure is copied from a lab receipt or raw log; nothing is invented. Addresses, ports, key paths and receipt hashes are omitted. Times are PST (America/Los_Angeles, UTC-8).

Tags: **[M]** measured on JUPI 2 · **[R]** lab record (receipt, inventory or probe log) · **[R/U]** published architect figure, not measured by us · **[U]** unmeasured or unverified.

## 1. Node and harness

| Item | Value |
|---|---|
| Node | JUPI 2 = Sony PS4 Pro, hostname `jupi2` |
| OS | Arch Linux 2026.11.01 |
| Kernel | `6.15.4-crashnt-4.7` (bench, desktop); `6.15.4-crashnt-4.7_no-built-in-fw` (rescue inventory, GPU probe) |
| CPU | 8-core AMD Jaguar, SoC string `AMD DG1301SML87HY`, no SMT. Flags include AVX, F16C, AES; no AVX2, no FMA [R] |
| Clock | Published 2.1 GHz [R/U]; inventory snapshot ~2091 MHz on 7 of 8 cores, one at ~1594 MHz [R] (snapshot, not under load) |
| RAM | MemTotal 7,070,228 kB in the rescue inventory; 6904 MB reported on the running desktop root [R] |
| Swap | zram 4 GiB lz4; swap used during the bench: 0 [R] |
| Root | 128 GiB sparse ext4 loop image on the internal HDD; `df` reported 125G, 5% used [R] |
| Engine | llama.cpp commit `3b4d6ab3f` (build 12242), CPU backend |
| Model | Qwen3-0.6B Q4_K_M GGUF, 492.75 MiB, 751.63 M parameters, file hash prefix `7f403014…e1fa` |
| Repeats | r = 3 for every row except the sustained soak (r = 1). ± is llama-bench's sample standard deviation |
| Baseline | JUPI (base PS4) record at 4 threads: tg128 11.77 tok/s, pp512 32.17 tok/s [R]. JUPI was not reachable for a same-night rerun |

## 2. Three runs, same binary and GGUF (10 Nov 2026)

| Run | When (PST) | Context |
|---|---|---|
| Pre-switch chroot | receipt 18:16 | Idle rescue root, Arch root built but not booted into, no desktop |
| Desktop | 20:21:37 – 20:23:21 | XFCE live after switch_root; load average 0.97 at start, 4.99 at end |
| Comprehensive | 21:08:15 – 21:31:10 | After the USB disk-boot (up since 21:04); `systemctl --failed` = 0; load average start 0.15 0.43 0.22, end 4.21 5.83 4.34 |

| Test | Pre-switch chroot | Desktop | Comprehensive | vs JUPI (4t) |
|---|---|---|---|---|
| pp512 @ 4t | 48.75 ± 0.04 | 48.62 ± 0.36 | 47.86 ± 0.02 | 1.52× / 1.51× / 1.49× |
| tg128 @ 4t | 17.29 ± 0.00 | 17.34 ± 0.01 | 17.42 ± 0.01 | 1.47× / 1.47× / 1.48× |
| pp512 @ 8t | 86.69 ± 0.05 | 86.69 ± 0.14 | 87.70 ± 0.13 | — |
| tg128 @ 8t | 27.43 ± 0.07 | 27.70 ± 0.09 | 27.98 ± 0.16 | — |

All tok/s [M]. The desktop did not regress token generation against the idle chroot.

## 3. Comprehensive run (21:08 – 21:31 PST) [M]

Script order: A thread sweep, B size sweep, C combined, D flash-attention, E sustained soak, F memory/crypto, G disk. The per-step error logs were present and empty (0 bytes).

### 3.1 Thread sweep, pp512 / tg128, r = 3

| Threads | pp512 tok/s | tg128 tok/s | tg ÷ JUPI 11.77 | tg efficiency | pp efficiency |
|---|---|---|---|---|---|
| 1 | 12.59 ± 0.00 | 5.05 ± 0.00 | 0.43× | 1.000 | 1.000 |
| 2 | 24.83 ± 0.00 | 9.41 ± 0.00 | 0.80× | 0.932 | 0.986 |
| 3 | 33.91 ± 0.01 | 13.08 ± 0.00 | 1.11× | 0.863 | 0.898 |
| 4 | 47.86 ± 0.02 | 17.42 ± 0.01 | 1.48× | 0.862 | 0.950 |
| 5 | 53.98 ± 0.15 | 20.64 ± 0.01 | 1.75× | 0.817 | 0.858 |
| 6 | 63.67 ± 0.02 | 23.93 ± 0.03 | 2.03× | 0.790 | 0.843 |
| 7 | 72.33 ± 0.15 | 25.79 ± 0.04 | 2.19× | 0.730 | 0.821 |
| 8 | 87.70 ± 0.13 | 27.98 ± 0.16 | 2.38× | 0.693 | 0.871 |

Efficiency = tok/s ÷ (1-thread mean × threads).

### 3.2 Amdahl fits

Model: R(n) = R1 · n / (s · n + 1 − s), least squares over n = 1…8. R∞ = R1 / s is an extrapolation, never a measured rate.

| Series | Fit | s | R1 tok/s | R∞ tok/s | R² | RMSE |
|---|---|---|---|---|---|---|
| tg128 | R1 fixed (primary) | 0.0603 | 5.05 measured | 83.8 | 0.998 | 0.36 |
| tg128 | R1 free (check) | 0.0631 | 5.11 fit | 80.9 | 0.998 | 0.35 |
| pp512 | R1 fixed (primary) | 0.0294 | 12.59 measured | 429 | 0.991 | 2.24 |
| pp512 | R1 free (check) | 0.0178 | 11.89 fit | 667 | 0.992 | 2.06 |

Generation fits cleanly (predicted 28.41 at 8t vs measured 27.98). Prompt processing does not: the 8-thread point sits +4.15 tok/s above the fit and the asymptote moves from 429 to 667 when R1 is freed, so the pp asymptote is poorly constrained.

### 3.3 Prompt and generation size sweep, 8 threads, r = 3

| Test | tok/s |
|---|---|
| pp64 | 85.36 ± 1.06 |
| pp256 | 93.68 ± 0.13 |
| pp512 | 87.70 ± 0.13 (from 3.1) |
| pp1024 | 75.99 ± 0.26 |
| pp2048 | 59.50 ± 0.06 |
| tg32 | 29.38 ± 0.23 |
| tg128 | 27.98 ± 0.16 (from 3.1) |
| tg256 | 26.16 ± 0.08 |
| tg512 | 24.00 ± 0.26 |

### 3.4 Combined pp512 + tg128, r = 3

| Threads | tok/s |
|---|---|
| 4 | 30.54 ± 0.03 |
| 8 | 52.48 ± 0.20 |

### 3.5 Flash-attention on vs off, 8 threads, r = 3

| fa | pp512 tok/s | tg128 tok/s |
|---|---|---|
| on | 86.89 ± 0.21 | 27.90 ± 0.13 |
| off | 72.58 ± 0.23 | 24.97 ± 0.14 |
| on ÷ off | 1.197 (+20%) | 1.117 (+12%) |

### 3.6 Sustained soak

| Test | tok/s |
|---|---|
| tg1024 @ 8t, r = 1 | 21.01 ± 0.00 |

The soak ran last, on a package that had already peaked near 80 °C, so length and temperature are confounded.

### 3.7 Memory and crypto (single process)

| Test | Result |
|---|---|
| Python 64 MiB array copy (read + write) | 3747 MiB/s. Crude; not a bandwidth claim |
| `openssl speed -seconds 3 -evp aes-256-gcm`, 16 KiB blocks | 1,012,263.59 kB/s ≈ 1012 MB/s |
| `openssl speed -seconds 3 sha256`, 16 KiB blocks | 119,220.91 kB/s ≈ 119 MB/s |

### 3.8 Loop-root disk, 1 GiB sequential, O_DIRECT

| Direction | Raw `dd` line | Rate |
|---|---|---|
| write | 1073741824 bytes (1.1 GB, 1.0 GiB) copied, 51.999 s | 20.6 MB/s |
| read | 1073741824 bytes (1.1 GB, 1.0 GiB) copied, 20.6276 s | 52.1 MB/s |

HDD-class. A cold read of the 492.75 MiB model takes many seconds at this rate.

### 3.9 Implied weight traffic (derived, not measured)

If every generated token streamed the full 492.75 MiB of weights from DRAM:

| Row | tok/s | Implied GB/s | % of published 218 GB/s [R/U] |
|---|---|---|---|
| JUPI 2 tg 1t | 5.05 | 2.61 | 1.2% |
| JUPI tg 4t [R] | 11.77 | 6.08 | 2.8% |
| JUPI 2 tg 4t | 17.42 | 9.00 | 4.1% |
| JUPI 2 tg 8t | 27.98 | 14.46 | 6.6% |
| JUPI 2 pp 8t | 87.70 | 45.31 | 20.8% |

176 / 218 GB/s are architect-disclosed GPU-class peaks (Cerny via Digital Foundry, 2016), not CPU-visible bandwidth. No STREAM-class tool was run.

## 4. Thermals [M]

k10temp package temperature, load average and MemAvailable sampled every 5 s across the comprehensive run (274 samples, 21:08:15 – 21:31:07 PST).

| Event | Time | Temp | Load | MemAvailable |
|---|---|---|---|---|
| Start | 21:08:15 | 66.0 °C | 0.15 | 6237 MB |
| First ≥ 70 °C | 21:12:25 | 70.2 °C | 1.11 | 6099 MB |
| First ≥ 75 °C | 21:18:52 | 75.5 °C | 5.32 | 6075 MB |
| Minimum MemAvailable | 21:21:28 | 78.0 °C | 7.58 | 5886 MB |
| Maximum load | 21:25:04 | 78.8 °C | 7.95 | 6108 MB |
| Peak | 21:27:25 | 79.8 °C | 7.02 | 6093 MB |
| Peak (repeat) | 21:27:30 | 79.8 °C | 7.09 | 6092 MB |
| End | 21:31:07 | 70.8 °C | 4.21 | 6192 MB |

k10temp limits: vendor "high" 70 °C, critical 100 °C. No throttle errors, no OOM, swap 0. The integration receipt rounds MemAvailable as "never < 6.0 GB"; the raw log minimum is 5886 MB. Both are given; the raw value is the measurement. Recommendation on record: check airflow before any 24/7 8-thread load.

## 5. Local LLM server, end to end [M]

The production server (groku-muse) is a different shape from llama-bench: it spawns `llama-cli` per request at 4 threads, caps output at 64 tokens, binds to loopback only, and is reached from the lab host through one SSH tunnel. Health, model list, completions, chat completions and session endpoints all returned HTTP 200; `/health` answered in 28 ms.

| Request | Wall time |
|---|---|
| Cold first request after a page-cache drop, 64 tokens | 14.88 s (model reload off the loop disk) |
| Warm, max_tokens 1 | 1.49 s (spawn + load floor) |
| Warm, max_tokens 24 | 2.78 s |
| Warm, max_tokens 64 | 5.14 s |
| Warm, max_tokens 128 requested | 5.22 s (server caps at 64) |
| Warm 64-token, n = 5 | min 5.11 / p50 5.14 / max 5.18 s |
| Chat, 32 tokens | 3.49 s |
| Session complete, 8 tokens | 1.88 s |
| 3 parallel 64-token requests | 16.9 / 17.9 / 19.2 s, wall 19.2 s |

Warm slope ≈ 17 tok/s after the ~1.5 s floor, matching the 4-thread bench, not the 8-thread peak. The three parallel requests are three 4-thread `llama-cli` processes contending for 8 cores. At enrollment (20:32 – 20:34 PST) a completion took ~2.8 s at ~17.8 tok/s. Known gaps: the response `perf` and `usage` fields come back empty (the parser does not match this `llama-cli` build's output); moving to 8 threads would lift decode ~1.6× (27.98 vs 17.42) at the cost of desktop headroom; a persistent `llama-server` would remove the ~1.5 s floor. Neither change has been made.

## 6. GPU: probe facts, no benchmark

Read-only probe, 11 Nov 2026, 5:43 – 5:46 AM PST. Verdict: GPU compute is reachable through Vulkan (RADV). **GPU tok/s is UNMEASURED [U].**

| Item | Probe result [R] |
|---|---|
| PCI | VGA `[1002:9924]` AMD Gladius rev 11, driver `amdgpu` (built in); Liverpool HDMI audio function alongside |
| Kernel cmdline | includes `radeon.dpm=0 amdgpu.dpm=0` |
| amdgpu init | CIK IP blocks `gmc_v7`, `gfx_v7`, `cik_sdma`, `dce_v8` (GCN2); VBIOS read from ROM BAR, ATOM `113-Roma-012`; 4 shader engines × 9 CU, `active_cu_number` 32; DRM 3.63 |
| Memory | VRAM carve-out 1024 MB (BAR 1024 MB), GTT 3450 MB, same physical GDDR5 as the CPU |
| Firmware | `gladius_{ce,me,mec,mec2,pfp,rlc,sdma,sdma1}` loaded; ME/PFP/CE/MEC/MEC2 v21, fw 0x10; MEC compute rings present |
| Device nodes | `/dev/dri/card0`, `/dev/dri/renderD128`; `/dev/kfd` absent (no ROCm/HSA path; gfx7 is outside ROCm support anyway) |
| OpenCL | no ICD installed (no clinfo, rusticl or clover) |
| Vulkan | `vulkan-radeon` (Mesa 26.2.6) works: "AMD DG1301SML87HY (RADV KAVERI)", API 1.3.354, integrated, subgroup 64, 64 KB shared memory, shaderInt8 yes, 16-bit storage yes, shaderFloat16 **no**, `VK_KHR_shader_integer_dot_product` present |
| OpenGL | radeonsi (kaveri, ACO), GL 4.5; the same GPU drives Xorg/XFCE on HDMI |
| Power management | dpm off: no `pp_dpm_sclk` or `gpu_busy_percent`; clocks stay wherever the loader left them; fan/thermal handled outside amdgpu |

Published figure: 36 CU at 911 MHz [R/U]. The probe shows 36 physical, 32 active; unresolved. For scale only, 32 CU × 64 lanes × 2 FLOP × 911 MHz ≈ 3.7 TFLOPS FP32 theoretical. That is arithmetic, not a measurement, and the real clock is unknown with dpm off.

Vulkan build attempt: same llama.cpp commit, separate build directory, `-DGGML_VULKAN=ON`, `nice 19`, `-j6`, `llama-bench` and `llama-cli` targets only, Vulkan-Headers `6802bb4` and SPIRV-Headers installed locally in user space. Attempts 1 and 2 failed on missing SPIRV-Headers (configure, then include path) and were fixed. Attempt 3 started at 5:49 AM PST; only CPU-side compilation (cmake / gcc / glslc) had run when the node stopped responding about nine minutes later. No Vulkan compute dispatch was ever issued. Cause unconfirmed (no console); the candidate explanations on record are a thermal or power trip, a kernel hang under a 6-job compile on a warm package (67.2 °C at build start), or memory pressure from parallel ggml-vulkan C++ jobs. The build directory was left resumable. Rerun at low parallelism (`-j2`).

The probe notes include a back-of-envelope band (tg ~45 – 90 tok/s, pp512 ~400 – 1000 tok/s). It is an estimate, tagged UNMEASURED, and must not be quoted as a result.

## 7. Not measured

- GPU tok/s (no Vulkan bench ran).
- Same-night JUPI rerun; 11.77 / 32.17 are a record.
- CPU-visible memory bandwidth (no STREAM / mbw).
- All-core CPU clock under load (only an inventory snapshot).
- Per-repeat raw samples (the JSON dump was started and killed), so ± cannot be recomputed.
- Original CPU build flags (not recorded).
- Pooled JUPI + JUPI 2 throughput and failover (not built).
- The $60 purchase price (in no receipt).

## 8. Reproduce

```
git clone https://github.com/ggml-org/llama.cpp && cd llama.cpp
git checkout 3b4d6ab3f
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j2          # keep it low: a -j6 build hung a warm Pro
B=./build/bin/llama-bench ; M=qwen3-0.6b-q4_k_m.gguf

$B -m $M -t 1,2,3,4,5,6,7,8 -p 512 -n 128 -r 3 -o md        # A thread sweep
$B -m $M -t 8 -p 64,256,1024,2048 -n 32,256,512 -r 3 -o md  # B size sweep
$B -m $M -t 4,8 -pg 512,128 -p 0 -n 0 -r 3 -o md            # C combined
$B -m $M -t 8 -fa on,off -p 512 -n 128 -r 3 -o md           # D flash-attn
$B -m $M -t 8 -p 0 -n 1024 -r 1 -o md                       # E soak

openssl speed -seconds 3 -evp aes-256-gcm                   # F crypto
openssl speed -seconds 3 sha256

dd if=/dev/zero of=dd.tmp bs=1M count=1024 oflag=direct conv=fsync   # G disk
dd if=dd.tmp of=/dev/null bs=1M iflag=direct ; rm dd.tmp
```

Post results with commit, model hash, thread count, r and package temperature, and tag them [M].
