# JUPI 2 full GPU offload, 2026-11-19

```
VERDICT   JUPI 2 (Sony PS4 Pro, Arch Linux, kernel 6.15.4-crashnt) now serves
          Qwen3-0.6B with every layer and the KV cache on the GPU.
          llama.cpp Vulkan backend, RADV from a patched Mesa (mesa-ps4 21.3.2,
          LLVM 13), installed side by side with the system Mesa.

          flags     -ngl 99 -fa off -ub 1 -b 2
          generate  median 75.88 tok/s   (was 29.15 with -nkvo -ub 8 -b 8)
          output    19/20 prompts byte-identical to the old live service
          2048 ctx  54.22 tok/s vs 14.65, same answer, correct
          faults    none (dmesg clean through the run)
```

Times are PST (UTC-8). Tags: [M] measured on JUPI 2, [R] lab record, [S] suspected.

## What changed

```
before  -ngl 99 -nkvo -fa off -ub 8 -b 8   weights on GPU, attention + KV on CPU
after   -ngl 99       -fa off -ub 1 -b 2   everything on GPU
```

Why `-ub 1`. llama.cpp's batched matrix-matrix shader (mul_mm) gives wrong
results on this GPU. With a micro-batch of 1, llama.cpp sends every matrix
product down the matrix-vector path (mul_mat_vec), which is correct here. The
op test for that path passed 481 of 481. [M]

Why `-b 2` and not `-b 1`. llama-server decodes a 2-token batch while it loads
the model (common_context_can_seq_rm). With -b 1 that aborts at startup:
"get_sub_batch: failed to add token 0 at index 1". -b 2 with -ub 1 still runs
every micro-batch at n = 1. [M]

## Exact command (live service, public edition)

```
VK_ICD_FILENAMES=<side-mesa>/radeon_icd.x86_64.json \
LD_LIBRARY_PATH=<llama.cpp build>:<side-mesa>/lib \
LLAMA_ARG_OFFLINE=1 \
llama-server -m qwen3-0.6b.gguf --host <loopback> --port <port> -np 1 \
  -ngl 99 -fa off -ub 1 -b 2 -t 6 -c 2048 --temp 0 --seed 1 --no-webui --no-jinja
```

```
llama.cpp  commit 3b4d6ab3f79651935fba1dd93732f29022a7f5f5
model      Qwen3-0.6B GGUF (Ollama qwen3:0.6b blob), 522,640,096 bytes,
           sha256 7f4030143c1c477224c5434f8272c662a8b042079a0a584f0a27a1684fe2e1fa
applied    as a systemd drop-in that overrides ExecStart only; the base unit is
           unchanged. Rollback = delete the drop-in, daemon-reload, restart.
```

## Method

```
prompts   data/prompts20.json: 5 short, 4 long (183-219 tokens), 4 code, 3 math,
          4 multi-turn ChatML. n_predict 64.
sampling  POST /completion, temperature 0, seed 1, cache_prompt false.
deep      data/deep-prompt-2048.json: 82 rows of a synthetic weather log,
          1,888 prompt tokens, asks for Day 37 (truth: 10 degrees).
          n_predict 120.
runs      A  old live service (-nkvo -ub 8 -b 8)                 11:34 AM
          B  full offload test server, live stopped               12:18 PM
          C  CPU reference (-ngl 0 -dev none -ub 8 -b 8)          12:20 PM
          D  full offload as the live service                     12:34 PM
          E/F/G  2048-context runs for B, old live, and D
gates     test servers ran alone with live stopped, at oom_score_adj 1000,
          under hard timeouts, with a dmesg GPU-fault watch, a 300 MB memory
          floor and a load-average guard. One model process at a time.
tools     tools/client.py  tools/deep.py  tools/compare.py
```

## Results

Full table: [COMPARISON.txt](COMPARISON.txt). Reproduce it with
`python3 tools/compare.py`.

```
                          tg min   tg median   tg max   pp median
A old live (-nkvo)         22.41       29.15    31.29       74.73
B full offload, test       73.11       76.12    76.50       95.20
D full offload, live       73.40       75.88    76.74       94.94
C CPU reference            16.50       19.34    21.00       26.83

byte-identical   D vs A 19/20   D vs B 20/20   A vs C 3/20   D vs C 3/20

2048 ctx (1,888 prompt tokens)   tg      pp      answer
E full offload, test             54.29   76.77   10 degrees (correct)
F old live                       14.65   43.99   10 degrees (correct)
G full offload, live             54.22   77.79   10 degrees (correct)
E, F and G are byte-identical.
```

The one mismatch against the old live service is short-3, which splits at
character 245 ("in the next year" vs "in the village"). Both texts read
normally.

Memory with full offload as the live service [M]:
```
MemAvailable  672 MB after load, 542 MB after the 20 prompts, 525 MB after 8 min
VRAM          759 of 1024 MiB used (carve-out), GTT 112 MiB
server RSS    311 MB
```

## Limits

```
- One model only (0.6B). No 1B/3B result: loading a 1B next to the live
  service ran the node out of memory earlier the same day.
- The strict gate, an exact match with the CPU reference, fails 3/20. It
  fails the same way for the old live service. On every prompt the GPU text
  leaves the CPU text at the same character in both GPU setups. That points
  to GPU vs CPU rounding, not corruption. This is an inference. [S]
- -b 1 crashes llama-server at load. Use -b 2.
- The batched mul_mm path is still broken. -ub 1 routes around it and does
  not fix it, so prompt processing runs one token per micro-batch
  (about 95 tok/s).
- Root cause [S]: the GPU returns wrong LDS data for the 128-bit LDS
  instructions ds_read_b128 / ds_write_b128. Our mul_mm shader compiles to
  32 ds_read_b128 under both ACO and LLVM and fails its op test 8/8.
  Mesa 21.3.2 emits these for any GFX7+ chip. Not yet proven by a Mesa
  build with them turned off.
- Stability observed so far: minutes to hours, not days.
```

## Credit

The root-cause lead came from Leonardo Alegria's Garlic LLM:
https://github.com/leonardo-alegria/garlic-llm

Garlic runs LLMs on the PS4 GPU under the console's own OS, with hand-written
GCN kernels. Its `pc/gpu.py`, lines 181-183, turns off ds_read_b128 /
ds_write_b128 because they return wrong LDS data on the PS4 GPU. That note
explained the bug we had been chasing on Linux, and led to the -ub 1 route
above.

Garlic is GPL-3.0. We studied it and referenced it. No Garlic code is copied
into this repository.

## Related finding: kernel memory held by dead cgroups

See [memory/DEAD-CGROUPS.md](memory/DEAD-CGROUPS.md). Both consoles had about
5 GB of their 6.9 GB held by the kernel in about 100,000 dead memory cgroups.
That memory, not the GPU, is what stops larger models today.

## Files

```
README.md               this file
COMPARISON.txt          per-prompt table (output of tools/compare.py)
SANITIZATION.txt        what was removed for the public edition
SHA256SUMS.txt          hashes of every file in this folder
data/                   prompts, deep prompt, and runs A-G as JSONL
tools/                  client, deep-prompt builder, comparison script
memory/DEAD-CGROUPS.md  the memory finding
```
