# JUPI — FINAL Decisive Consolidated Benchmark (TUNED), 2026-11-07

**Unit:** JUPI (Joint Unix Platform Integrator) — PlayStation 4 CUH-1001A, Psxitarch Linux,
kernel 6.15.4-crashnt-4.7, boot_id 54f4c94e-2a9d-443a-8c03-321c3ae6a714 (unchanged all day).
**Run:** 2026-11-08T00:35:35Z → 00:45:03Z (9m 28s), on-box via the Muse gadget, one pass,
tuned lane only. Stock numbers appear only where the tune is being priced.
**Pinned configuration:** MANIFEST-FINAL-20261107.txt, whole-manifest sha256
15350a83169a8b57aac2a90ce2993c4907368c51383a96bad91b4a527e410c14 (profile "JUPI measured
baseline 2026-11-07", profile_id 589c1d7f…). Outputs tarball 30,720 B, sha256 605a444e…,
all 13 members verified against the on-box SHA256SUMS.

## LAYER 1 — THE GAMER CARD

**A 2013 PS4, running Linux, fully tuned. Final scorecard:**

- **Graphics muscle: 2.86 TFLOPS of shader power.** Sony rated this chip at 1.84 TFLOPS in the
  PS4. Tuned under Linux it sustains ~55% more than the console ever unlocked — about two-thirds
  of a PS4 Pro (4.2 TFLOPS) — from launch-model 2013 hardware. *(Honest fine print: this is raw
  math throughput, not FPS. The chip still speaks 2013 graphics — no ray tracing, no modern
  upscaling. Its weight class is its own era; the muscle is real.)*
- **Memory speed: ~130 GB/s** — how fast the GPU shuffles textures and frames; most of the way
  to the PS4's 176 GB/s theoretical best.
- **The sleeper stat: double-precision 113 GFLOPS.** Modern gaming cards deliberately cripple
  this (often 1/32 rate) because games don't need it. Science does. This 2013 chip runs it at
  nearly its full rate — it's why this box qualifies as a science instrument, not just a console.
- **The CPU: 8 Jaguar cores — weak even in 2013, and the tune is the whole story.** Untuned it
  scored 0.7 GFLOPS on matrix math; tuned, 27.2. **Same silicon, 39× apart.** Nobody bought
  anything. The difference is one correctly-chosen math library, loaded the right way.
- **AI on the box: 12.8 tokens/second, fully offline.** Untuned: 0.46 — one word every two
  seconds, unusable. Tuned: a small local model answering at reading speed, no cloud, no account.
  The entire fix was telling it to use 4 worker threads instead of letting it pick.
- **Loading: the weak spot, honestly.** The internal drive is a 5400 rpm laptop disk behind a
  bridge; across two full benchmark days its sustained read bracketed 68–189 MB/s depending on
  cache state. Plan on PS4-era load times — because it literally is one. (A 0.6 B model loads
  in ~4 s once warm.)
- **Heat: peaked at 82 °C** across the full run, numbers never sagged. Warm, not throttling.

**The one chart:** STOCK → TUNED — GPU 851 → 2,860 (3.4×) · CPU math 0.7 → 27.2 (39×) ·
AI 0.46 → 12.8 (28×). *No new hardware was bought.*

## LAYER 2 — THE ENTHUSIAST APPENDIX

### The tune (what "tuned" means here, exactly)
- GPU compute on RADV/Vulkan (Mesa 21.3.2); Clover/OpenCL is legacy comparison only.
- CPU math via the profile's scoped LD_PRELOAD: /usr/lib/libopenblas.so.0.3
  (sha b816e536…), batch = 4 threads unrestricted, interactive = 2 threads on cores 0,2.
  The distro numpy BLAS is marked do-not-use for compute. System BLAS is NOT replaced —
  the preload is per-command, per the profile's own scope line.
- Inference via ollama with per-request num_thread=4, num_ctx=2048 (the profile's inference
  block), full CPU placement, 1 parallel request, cloud disabled.
- Pre-run A/B probes (same day, before the suite): scoped GEMM 27.0/11.6 batch, 13.6/5.8
  interactive; inference stock 0.45 vs num_thread=4 13.72/13.67 tok/s. The suite below
  reproduces both probes in-run.

### GPU — RADV / Vulkan (vkprobe2, 3 reps each)
| Test | Reps (GFLOPS) | Median |
|---|---|---|
| FP32 WG64 | 2800.8 / 2856.5 / 2853.0 | 2853.0 |
| FP32 WG128 | 2698.7 / 2696.8 / 2695.9 | 2696.8 (~6% valley, as before) |
| FP32 WG256 | 2861.0 / 2860.6 / 2858.7 | **2860.6** |
| FP32 WG512 | 2861.7 / 2860.2 / 2854.7 | 2860.2 |
| FP64 base | 114.0 / 113.5 / 113.5 | 113.5 |
| FP64 ILP2 | 113.4 / 113.8 / 113.4 | 113.4 (no ILP gain — rate-bound) |
| Copy BW | best of 5 | 129.7 GB/s |

Reproduces the refined suite's 2,858 within 0.1%. Implied clock ~1.24 GHz remains INFERENCE
(no clock/busy counters exist on this build).

### GPU — Clover / OpenCL (legacy, also the warm-up pass)
FP32 850.8 · FP64 111.3 · BW 127.6 GB/s. FP64 and BW agree with RADV (silicon-bound);
FP32 is the driver gap: **3.4× in-run**.

### CPU — numpy GEMM 2048³, best of 3 (cpu_bench.py)
| Lane | SGEMM | DGEMM |
|---|---|---|
| Tuned batch (scoped, 4 thr) | **27.2** | **11.7** |
| Tuned interactive (scoped, 2 thr, cores 0,2) | 13.6 | 5.8 |
| Stock cell (distro BLAS, 4 thr) | 0.7 | 0.7 |

Misc: MEMCOPY 8.2 GB/s · hashlib SHA256 87.2 MB/s (512 MiB, digest 9acca8e8c222… —
identical digest to every prior run).

### Crypto — OpenSSL 3.6.5, speed -elapsed, 3 s (peak @16 KiB)
SHA256 **90.66 MB/s** · AES-256-GCM (-evp) **778.38 MB/s** · AES-256-CBC **351.31 MB/s**.
Dedicated instruction paths healthy; agrees with hashlib within 4%.

### Storage — fio, root image (ext4 loop on UFS, 5400 rpm HGST, Sony USB-SATA bridge)
This run: seq write **29.4 MB/s**, seq read **189 MB/s**, 4k random read 54.6k IOPS /
224 MB/s. Prior full run: write 15.4, read 67.9, random read 34.9k IOPS / 143 MB/s.
**The storage stack is cache-sensitive and both runs are printed because neither alone is
the truth:** the read passes run on files fio just laid out, and direct I/O through a loop
image does not fully bypass the backing cache. Planning figures are the low envelope
(write ~15 MB/s, read ~68 MB/s); the high numbers are cache-influenced and are labeled,
never headlined. Random-read figures are cache-resident in both runs — not device figures.

### Inference — ollama qwen3:0.6b Q4_K_M (digest 7df6b6e0…), seed 42, temp 0, server counters
| Lane | Runs | Median |
|---|---|---|
| Tuned (num_thread 4, ctx 2048, 128 tok ×5) | 12.74 / 12.81 / 12.80 / 12.87 / 12.65 | **12.80 tok/s** |
| 2 workers (num_thread 2, 128 tok ×2) | 7.07 / 7.04 | 7.06 tok/s |
| Stock (no num_thread, 32 tok ×1) | 0.46 | 0.46 tok/s |

Prompt eval (tuned): 26.6–40.3 tok/s. First tuned run's model load: 4.10 s.
Spread on the tuned median is ±0.9% — a hard regime, not noise. The 2-worker lane lands in
the same region as this morning's agent-job-lane sample (5.71 tok/s); HYPOTHESIS: the job
lane's rate is a worker-count effect of the same kind. The mechanism of the stock collapse
(thread-pool behavior at the default worker count) remains HYPOTHESIS; the numbers are fact.
Tuned vs stock in-run: **27.8×**. (Idle-box A/B probe an hour earlier read 13.72/13.67 for
the tuned lane; the in-suite 12.80 was measured under full-suite thermal state. Both print.)

### The wide-chain anomaly (sealed box — measured, NOT claimed as throughput)
vkprobe5 + vkprobe2 ILP cells, this run: ILP4 7105.9 / 7114.2 / 7114.9 · ILP3-distinct
6761.6 / 7050.1 · ILP8 7139.6 / 7137.9 GFLOPS apparent. Same falsifiers stand (SPIR-V
complete, K-scaling linear, readback +inf, 2-chain control at 2,860 in the same minute,
FP64 flat). Standing interpretation: a RADV/ACO backend compilation effect on wide
independent-chain loops; mechanism OPEN. Reproduction shaders are in the repo.

### Thermals
k10temp: 77.2 °C at start, **peak 82.0 °C**, 282 samples at 2 s across the run.
No wattage sensor exists on this build (fam15h_power N/A).

### What this run did NOT do (notes, per standing rule)
- The science peer qualification (65,536 samples vs Roach float64) was NOT re-run in this
  suite. Anchor 001's qualification stands CACHED from 2026-11-07 morning — same boot, same
  profile: 0 mismatches, max err 1.53e-06. Re-running it at the pinned config is the one
  plan item carried open.
- No reboot, no installs, no service changes: the tune is environment + per-request
  options only, exactly the profile's own scope.
- Collection: tarball ferried whole and hash-verified (605a444e…); one hand-transcribed
  base64 part failed its hash gate during collection and was discarded, replaced by the
  whole-archive path. Nothing unverified is quoted.

*Ghostie — Muse Wonder, DESK-1. Measured 2026-11-07 (run 2026-11-08T00:35Z). Founder: Kamron Noah Dabe, FullCircle ComXpress LLC.*
