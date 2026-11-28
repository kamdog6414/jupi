# FC-NODS128: Mesa ACO without ds_read/write_b128 on PS4 GPUs, 2026-11-22

```
VERDICT   JUPI 2 (PS4 Pro, RADV GLADIUS): PASS.
          JUPI 1 (PS4, RADV LIVERPOOL): output and speed PASS. The full MUL_MAT
          op sweep hung the GPU with the patch (08:35) AND without it (stock
          control, 13:38): the same first ring timeout and the same failed reset.
          Patch cleared of a patch-exclusive hang attribution only. Root cause and
          general patch safety are UNKNOWN. Both JUPI 1 sweeps are incomplete.
          Stable run on real workloads (16:29): PASS. 60-min patched -ub 64 soak
          1380/1380 byte-identical to JUPI 2, 60-min stock control 1180/1180,
          0 ring faults, swap 0 MiB. (See "Stable run on real workloads".)

patch     2 hunks in src/amd/compiler/aco_instruction_selection.cpp,
          on mesa-ps4 21.3.2. On CHIP_LIVERPOOL and CHIP_GLADIUS, ACO no
          longer emits ds_read_b128/b96 or ds_write_b128/b96. It splits them
          into ds_read2_b64 / ds_write2_b64 / b64.
effect    llama.cpp's batched mul_mm path becomes correct on these GPUs.
          JUPI 2 pp512 goes from 72.87 to 854.71 tok/s at -ub 512. tg is unchanged.
status    test-only. Loaded per process with VK_ICD_FILENAMES. No system
          library was replaced and no live service was switched.
```

Times are PST (UTC-8). Tags: [M] measured, [R] lab record, [S] suspected.
Idea credit: Leonardo Alegria, Garlic LLM (garlic-llm#10, `-enable-ds128` stays off
on this GPU in LLVM). He found that the PS4 GPU's 128-bit LDS loads return wrong
data. This patch carries that finding into Mesa's ACO compiler. Garlic's code was studied, and none was copied.

## Why

On both PS4 GPUs (GFX7), llama.cpp's matrix-matrix shader (mul_mm) gave wrong
results. That is why the 2026-11-19 full-offload setup forced `-ub 1`, which sends
every product down the matrix-vector path. A shader-ISA count showed stock ACO turning
the mul_mm LDS tile loads into `ds_read_b128`. With the patch, every one of those
becomes a `ds_read2_b64`, and mul_mm passes. [M]

```
ISA, 11 representative MUL_MAT shaders (JUPI 2, final ACO IR)   data/jupi2/isa-SUMMARY.txt
build      ds_read_b128  ds_read2_b64  ds_write2_b64  ds_write_b64  cases OK
stock          320           320            48            104        0/11
patched          0           640            48            104       11/11
```

## Results

### JUPI 2 (PS4 Pro), 2026-11-22 06:15-07:45 [M]

```
test-backend-ops on Vulkan0 (chunk crashes re-run alone; SKIP = no CPU reference)
op                     stock OK/FAIL           patched OK/FAIL
MUL_MAT     (2754)     1421 / 1067 (234 skip)  2488 / 0 (234 skip)
MUL_MAT_ID  (1109)      500 / 593              1093 / 0
(2754 / 1109 = nominal enumerations. The retained per-case files hold 2722 distinct
 MUL_MAT entries (2488 OK + 234 SKIP_CPU, no CPU reference) and 1093 MUL_MAT_ID.
 The reason for that gap was not established. "Passes" means every case with a
 CPU reference that was retained.)
amdgpu ring timeouts / resets in dmesg: 0 on all four sweeps

llama-bench qwen3-0.6b Q4_K_M, -ngl 99 -fa 0 -t 6 -r 3
path                                  pp512     tg128
accepted live, forced -ub 1 -b 2      72.87     86.92
patched  -ub 1  -b 2                  72.55     86.76
patched  -ub 16                      194.67     87.04
patched  -ub 64                      713.66     86.55
patched  -ub 512                     854.71     86.70

20-prompt byte-match vs the accepted live outputs (temp 0, seed 1)
config                         identical   deep-2048 answer
stock self-built -ub 1 (ctrl)    20/20      same
patched -ub 1                    20/20      same
patched -ub 16 / 64 / 512        19/20      same   (short-3 differs, see logit check)
stock -ub 16 (negative ctrl)      0/20      -      (garbage)

server deep-2048 prompt: pp 78 -> 640 tok/s, wall 28.1 s -> 7.3 s
soak: 100 loops of llama-bench -ub 512 + the 11-case op test over 15 min,
      100/100 passed, 0 new amdgpu faults
```

### JUPI 1 (PS4), 2026-11-22 08:15-08:37 [M]

The same patched `libvulkan_radeon.so` (built on JUPI 2) was loaded on JUPI 1. JUPI 1's
system RADV is byte-identical to JUPI 2's side-installed live RADV, and glibc is the same.

```
llama-bench qwen3-0.6b, -ngl 99 -fa 0 -t 6 -r 3 (desktop + services up)
path                                  pp512     tg128
stock  -ub 64   (wrong output)       526.90     74.82
stock  -ub 512  (wrong output)       760.23     74.85
patched -ub 1  -b 2                   55.41     74.78
patched -ub 64                       552.73     75.01
patched -ub 512                      795.68     74.62
(stock -ub 1 bench excluded: a second copy ran at the same time by mistake.)

20-prompt byte-match vs the JUPI 2 accepted live outputs
config                   identical  tg med  pp med   deep-2048
stock  -ub 1 (control)     20/20    65.73    79.53   same, 33.19 s
patched -ub 1              20/20    65.72    80.26   same, 33.01 s
patched -ub 64             19/20    61.36   214.70   same,  9.27 s (pp 437)
patched -ub 512            19/20    56.68   232.45   same,  8.47 s (pp 597)
stock  -ub 64 (negative)    0/20    61.36   235.12   -    (garbage)
cross-node: JUPI 1 patched == JUPI 2 patched, 20/20 in each of the 3 configs
```

**Crash 1, JUPI 1, patched (morning).** At 08:35:29, during the full MUL_MAT sweep under the patched driver,
compute ring comp_1.1.0 timed out in the test process. The kernel's GPU reset failed
("asic atom init failed", "GPU Recovery Failed"). The gfx (desktop compositor) and both
sdma rings then timed out in turn. The watchdog stopped the run at 08:35:30.
MUL_MAT_ID, both stock op sweeps and the soak were not run on JUPI 1.
data/jupi1/crash-kernel-lines.txt has the kernel lines. [M]

As of the morning report (08:43), no stock sweep had been run. That was settled
later the same day:

**Reboot and stock control, JUPI 1 (afternoon).** [M]

```
13:28:49  reboot sent (operator GO); PlayStation-side boot done by the operator
13:34:10  SSH back; 0 ring timeouts in dmesg, display up, swap 0 MiB
13:34:39  stock MUL_MAT sweep starts: system RADV (mesa-ps4 21.3.2, libvulkan_radeon.so
          sha256 acf91948...a34ae5), VK_ICD_FILENAMES removed in tools/stockdrv.py.
          Chunks of 40; CURRENT.txt (the in-flight case list) and the log are fsynced
          per chunk.
13:38:38  chunk 7 = cases [179:219] hangs compute ring comp_1.1.0 (test-backend-op);
          GPU reset fails ("asic atom init failed", "GPU Recovery Failed: 1"); gfx
          (Xorg, xfwm4) and sdma0 timeouts follow. Guard stops the run at 13:38:40,
          swap 0 MiB.
14:03:42  second reboot (operator GO); 14:06 back, no timeouts, GPU left idle since. [R]
```

Chunk 7 candidates (data/jupi1/stock-control/HUNG-CHUNK7-cases.txt, sha256
7cc937ab3fb02f08bd169d9837526f4c3065ca2529a728d5f04e6be98812bd4c), all MUL_MAT,
type_b f32, m=16: q3_K n1/n8 k4096; q4_K, q5_K, q6_K n1..9 k256 and n1/n8 k4096;
tq2_0 n1..5 k256. Which of the 40 was executing is UNKNOWN.
Chunks 1-6 returned rc 1, 1, 1, -6, -6, -11 (failures and process faults, no new
ring fault). That does NOT mean cases 0-208 passed.
Kernel lines: data/jupi1/stock-control/kernel-lines.txt (sha256 7c386bd1...0cf1).

**Comparison (independent review, review/).**

```
                         patched (08:35)             stock control (13:38)
first timeout            comp_1.1.0                  comp_1.1.0
reset                    asic atom init failed, GPU Recovery Failed (both)
then                     gfx, sdma1, sdma0, xfwm4    gfx, sdma0, Xorg, xfwm4
hung chunk               UNKNOWN (log buffered)      chunk 7 [179:219]
```

Verdict (independent review, NIKOLAI-2): **PATCH CLEARED of a patch-exclusive hang
attribution under the recorded stock-control setup; exact root cause and general
patch safety remain UNKNOWN.** Both runs hang in the same MUL_MAT op family. Same
chunk or same case is NOT established, because the patched run's log was buffered and
lost. A matching timeout signature is not proof of the same initiating instruction or
of defective silicon.

Both JUPI 1 sweeps are incomplete. There is no successful JUPI 1 op aggregate
(data/jupi1/ops/COUNTS.json stays empty; see data/jupi1/ops/STATUS.json), no JUPI 1
ISA count. (A valid stock ub1 timing was taken later, in the stable run.) Full op sweeps stay unsafe on JUPI 1 with
either driver. The same full sweep ran on JUPI 2 with 0 faults. JUPI 1 had also frozen
under Vulkan op testing on 2026-11-10, before this patch existed [R].

### JUPI 1 stable run on real workloads, 2026-11-22 14:25-16:29 [M]

Why: the hang above comes from the op stress sweep, with either driver. The
question that matters for using the patch is whether real inference stays stable
on JUPI 1. No test-backend-ops was run in this window.

```
llama-bench qwen3-0.6b Q4_K_M, -ngl 99 -fa 0 -t 6 -r 3 (tok/s, +- sd)
config    stock pp512      patched pp512    stock tg128     patched tg128
-ub 1      56.18 +-0.05     56.15 +-0.05    75.14 +-0.08    74.73 +-0.06
-ub 64    527.24 +-0.32    552.84 +-0.16    75.25 +-0.28    74.92 +-0.19   (+4.9% pp)
-ub 512   760.14 +-0.15    796.57 +-0.23    74.56 +-0.10    74.98 +-0.09   (+4.8% pp)
(-ub 1 runs with -b 2. Stock at -ub 64/512 is fast but gives WRONG output; it is
 a speed reference only. The stock -ub 1 row replaces the morning's contaminated one.)

soak: llama-server, the 20 prompts on repeat, temp 0, seed 1, prompt cache off
                       patched -ub 64 -b 2048     stock -ub 1 -b 2 (control)
window (PST)           14:27:56-15:28:10          15:28:14-16:29:15
rounds                 69                         59
byte-identical         1380/1380                  1180/1180
  reference            JUPI 2 patched -ub 64      JUPI 2 accepted live (2026-11-19)
tg med (min-max)       61.92 (61.45-62.21)        65.89 (65.57-66.05)
pp med (min-max)       236.19 (234.86-236.58)     80.57 (80.20-80.74)
tg drift, 2nd vs 1st half  -0.10%                 +0.13%
round wall med         52.15 s                    61.81 s
server RSS             329 -> 364 MB, flat        364 -> 400 MB, flat
MemAvailable min       5461 MiB                   5473 MiB
swap peak              0 MiB                      0 MiB
new amdgpu faults      0                          0
```

The driver each soak server loaded was read from /proc/<pid>/maps
(data/jupi1/stable/LOADED-DRIVER.txt): patched libvulkan_radeon.so 117805de...ff0d5
with VK_ICD_FILENAMES set, and the system acf91948...a34ae5 with no VK_ variable.
Guards: tools/guard4.sh (pidfile root; kills the run tree on any new amdgpu ring
timeout/reset line, swap above start + 256 MiB, or MemAvailable under 1000 MiB;
5 s checks, 60 s dmesg heartbeat) and per-round dmesg/swap checks in
tools/stable.py. All logs are fsynced per line. Data: data/jupi1/stable/.
Short-3 matches here because the reference for the patched soak is JUPI 2's own
patched -ub 64 output (it holds the near-tie token covered below).

What this shows: the patched batched path ran 60 minutes of real inference on
JUPI 1 with no fault, no drift and exact cross-node output. What it does not show:
that the op stress sweep is safe, or what causes its hang.

### Logit check on the one difference (JUPI 2) [M]

short-3 diverges at generated token 53 ("...speak to her in the"):

```
           top-1                 top-2                 margin
-ub 1      " next"    -1.4169    " village" -1.4188    0.0019 nats
-ub 64     " village" -1.4157    " next"    -1.4181    0.0024 nats
-ub 512    same as -ub 64
max |d logprob| over the 53 identical earlier tokens: 0.0012 nats
```

The two tokens are a near tie (p 0.2425 vs 0.2420). A change in float summation order
(batched mul_mm vs mat-vec) swaps them. The top-5 set and its order are otherwise
unchanged. This is consistent with a near-tie flip under numerical order sensitivity.
It does not prove corruption is absent everywhere, or isolate summation order as the
only cause. data/jupi2/logit/

## Method

```
llama.cpp  3b4d6ab3f79651935fba1dd93732f29022a7f5f5
model      qwen3-0.6b Q4_K_M (Ollama blob), sha256 7f4030143c1c477224c5434f8272c662a8b042079a0a584f0a27a1684fe2e1fa
mesa       mesa-ps4 21.3.2 + this patch, ACO only (no LLVM in the self-built lib)
prompts    the 2026-11-19 packet's prompts20.json and deep-prompt-2048.json, unchanged
op test    tools/opdriver.py runs test-backend-ops case lists in chunks of 40
           and records OK/FAIL/CRASH per case. tools/rerun.py re-runs CRASH cases
           alone. It stops on any amdgpu ring timeout/reset.
loading    VK_ICD_FILENAMES=<dir>/radeon_icd.json (per process); system ICD untouched
```

Data: data/jupi2/ and data/jupi1/ (bench JSON, 20-prompt JSONL, deep-2048, op counts
plus per-case results as .json.xz, soak/chain logs, ISA summary, logit tops).
Stock control: data/jupi1/stock-control/ and tools/stockdrv.py.
Stable run: data/jupi1/stable/ and tools/stable.py, tools/guard4.sh, tools/finish.py.
Hang receipts as filed in the lab: receipts/ (morning patched hang, afternoon stock hang). Independent review:
review/ (public copy, lab paths replaced; original sha256 in RECEIPTS.txt).
Log times in data/jupi1/stock-control/*.log are UTC (13:38 PST = 21:38 UTC).

## Limits

- One model, one seat grading. No second key yet.
- The ISA count covers 11 shaders. The JUPI 2 op sweeps are the behavioral proof.
- Both JUPI 1 MUL_MAT sweeps (patched, stock) hung the GPU. MUL_MAT_ID and the ISA
  count were never run on JUPI 1. The op-test soak was replaced on JUPI 1 by the
  real-workload soak above (60 + 60 min), which is not an op-coverage test. The single hanging case was not isolated,
  because that needs a deliberate hang plus a recovery reboot and owner approval.
- During the JUPI 2 windows an earlier worker stopped the live service for about 15
  minutes to free VRAM. It was restored each time. [R]
- Upstream form not done: gate on a device quirk, check current Mesa main.
