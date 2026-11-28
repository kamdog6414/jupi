# Freed-core benchmarks, 2026-11-24 (JUPI 1 before/after, JUPI 1 vs JUPI 2)

Both consoles on kernel jupi-1.0, stickless, HDD roots. JUPI 1 with `sky2.aeolia_poll_phy=1`.
RESULTS.md has every table with its grade. Headline: the Aeolia PHY interrupt storm that pinned
CPU 1 at 100% softirq is gone (eth0 IRQ ~3,590/s to ~14/s), and a 4-core SGEMM mask that includes
CPU 1 went from 1.87 to 26.63 GFLOP/s (14.2x, same pinned fixture). JUPI 2 is ~1.31x JUPI 1 per core.
llama.cpp CPU, qwen3 0.6B Q4_K_M, 8 threads: JUPI 1 22.00 tok/s, JUPI 2 27.71 tok/s (tg128).
GPU inference was not part of this run. Raw per-step logs stay in the lab (they carry addresses).
Pins: llama.cpp 3b4d6ab, binary 596d83ac..., model 7f403014..., fixture 63adf7b6....
- groku
