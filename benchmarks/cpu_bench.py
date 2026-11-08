#!/usr/bin/env python3
"""JUPI CPU bench: numpy GEMM (thread count set by caller env), memory copy, SHA-256."""
import sys, time, hashlib
import numpy as np

def best_of(fn, reps):
    best = 1e18
    for _ in range(reps):
        t0 = time.perf_counter(); fn(); dt = time.perf_counter() - t0
        if dt < best: best = dt
    return best

mode = sys.argv[1] if len(sys.argv) > 1 else "all"
if mode in ("gemm", "all"):
    n = 2048
    rng = np.random.default_rng(20261107)
    A32 = rng.random((n, n), dtype=np.float32); B32 = rng.random((n, n), dtype=np.float32)
    A32 @ B32  # warmup
    dt = best_of(lambda: A32 @ B32, 3)
    print(f"SGEMM {n} {2*n**3/dt/1e9:.1f} GFLOPS (best {dt:.3f} s)")
    A64 = A32.astype(np.float64); B64 = B32.astype(np.float64)
    A64 @ B64
    dt = best_of(lambda: A64 @ B64, 3)
    print(f"DGEMM {n} {2*n**3/dt/1e9:.1f} GFLOPS (best {dt:.3f} s)")
if mode in ("misc", "all"):
    x = np.empty(33_554_432, dtype=np.float64)  # 256 MiB
    y = np.empty_like(x); x[:] = 1.5
    dt = best_of(lambda: y.__setitem__(slice(None), x), 5)
    print(f"MEMCOPY {2*x.nbytes/dt/1e9:.1f} GB/s (best {dt:.3f} s, {2*x.nbytes/1e9:.2f} GB moved)")
    chunk = bytes(1 << 20); h = hashlib.sha256(); total = 512
    t0 = time.perf_counter()
    for _ in range(total): h.update(chunk)
    dt = time.perf_counter() - t0
    print(f"SHA256 {total/dt:.1f} MB/s ({total} MiB in {dt:.3f} s, digest {h.hexdigest()[:12]}...)")
print("CPUBENCH DONE")
