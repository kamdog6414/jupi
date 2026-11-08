#!/bin/bash
# JUPI CPU supplement: scoped (taskset) GEMM sweep + 1024^3 comparability point.
# Runs after the main suite. Writes /tmp/jupi-suite/OUT/cpu-supplement.txt
set -u
cd /tmp/jupi-suite
OUT=/tmp/jupi-suite/OUT/cpu-supplement.txt
{
echo "CPU SUPPLEMENT $(date -Is)"
echo "-- shell affinity --"
grep -i cpus_allowed /proc/self/status
echo "-- taskset sweep (2048^3, best of 3, warmup 1) --"
for spec in "0 1" "0,2 2" "0-3 4" "0-7 8"; do
  set -- $spec
  echo "--- taskset -c $1 threads=$2 ---"
  taskset -c "$1" env OPENBLAS_NUM_THREADS=$2 OMP_NUM_THREADS=$2 MKL_NUM_THREADS=$2 \
    python3 cpu_bench.py gemm
done
echo "-- 1024^3 comparability (morning survey used 1024^3) --"
python3 - <<'PY'
import os, time
import numpy as np
for n in (1024,):
    for dt, name in ((np.float32, "SGEMM"), (np.float64, "DGEMM")):
        a = np.random.rand(n, n).astype(dt); b = np.random.rand(n, n).astype(dt)
        a @ b
        best = 1e9
        for _ in range(3):
            t = time.perf_counter(); a @ b; best = min(best, time.perf_counter() - t)
        print(f"{name} {n} default-threads {2.0*n**3/best/1e9:.1f} GFLOPS (best {best:.3f} s)")
PY
echo "SUPPLEMENT DONE"
} > "$OUT" 2>&1
echo "supplement written: $OUT"
