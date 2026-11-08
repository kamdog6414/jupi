#!/bin/bash
# JUPI FINAL decisive consolidated benchmark — TUNED lane only.
# Reuses hash-verified harnesses from /tmp/jupi-suite; writes OUT/ sections.
S=/tmp/jupi-final
SRC=/tmp/jupi-suite
OUT=$S/OUT
mkdir -p $OUT
cd $S
echo "FINAL START $(date -Is)" > $OUT/suite.log
( while :; do echo "$(date +%s) $(cat /sys/class/hwmon/hwmon1/temp1_input 2>/dev/null)"; sleep 2; done > $OUT/thermal.log 2>/dev/null & echo $! > $OUT/thermal.pid )
sec(){ echo "=== $1 $(date -Is) ===" >> $OUT/suite.log; }

sec SYSINFO
{
  date -Is; uname -a; cat /proc/sys/kernel/random/boot_id
  grep -m1 "model name" /proc/cpuinfo; nproc; free -m
  vulkaninfo --summary 2>/dev/null | grep -E "deviceName|driverName|driverInfo|apiVersion" | head -4
  curl -s http://127.0.0.1:11434/api/tags | head -c 400; echo
  sensors 2>/dev/null | head -10
  echo "--- MANIFEST INPUTS ---"
  sha256sum /usr/lib/libopenblas.so.0.3 /usr/lib/dri/radeonsi_dri.so \
    /home/pi/ChatGPT/JUPI/config/performance-profile.json \
    /usr/local/lib/jupi-agent/performance_profile.py \
    /etc/systemd/system/ollama.service.d/50-jupi.conf \
    /etc/systemd/system/ollama.service.d/70-jupi-affinity.conf
  grep -E '"profile_id"|"name"' /home/pi/ChatGPT/JUPI/config/performance-profile.json
  sha256sum vkprobe2.c vkprobe5.c gpubench.c cpu_bench.py infer_final.py *.comp
} > $OUT/sysinfo.txt 2>&1

sec BUILD
{
  for f in fma32_wg64 fma32_wg128 fma32_wg256 fma32_wg512 fma32_ilp fma32_ilp3 fma32_ilp8 fma64 fma64x2 copy; do
    glslc $f.comp -o $f.spv && echo "glslc $f OK"
  done
  gcc -O2 -o vkprobe2 vkprobe2.c -ldl && echo "gcc vkprobe2 OK"
  gcc -O2 -o vkprobe5 vkprobe5.c -ldl && echo "gcc vkprobe5 OK"
  gcc -O2 -o gpubench gpubench.c -lOpenCL && echo "gcc gpubench OK"
} > $OUT/build.txt 2>&1

sec WARMUP-LEGACY-OPENCL
./gpubench > $OUT/gpu-opencl.txt 2>&1

sec GPU-RADV
./vkprobe2 /tmp/jupi-final > $OUT/gpu-radv.txt 2>&1

sec GPU-ANOMALY
./vkprobe5 /tmp/jupi-final > $OUT/gpu-anomaly.txt 2>&1

sec CPU-TUNED
{
  echo "--- scoped batch: LD_PRELOAD profile OpenBLAS, threads=4 ---"
  LD_PRELOAD=/usr/lib/libopenblas.so.0.3 OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 python3 cpu_bench.py gemm
  echo "--- scoped interactive: taskset 0,2, threads=2 ---"
  taskset -c 0,2 env LD_PRELOAD=/usr/lib/libopenblas.so.0.3 OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 python3 cpu_bench.py gemm
  echo "--- misc (lane-independent) ---"
  python3 cpu_bench.py misc
  echo "--- STOCK comparison cell: distro BLAS, threads=4, single pass ---"
  OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 python3 cpu_bench.py gemm
} > $OUT/cpu.txt 2>&1

sec CRYPTO
{
  openssl version
  openssl speed -elapsed -seconds 3 sha256 2>&1 | tail -4
  openssl speed -elapsed -seconds 3 -evp aes-256-gcm 2>&1 | tail -4
  openssl speed -elapsed -seconds 3 aes-256-cbc 2>&1 | tail -4
} > $OUT/crypto.txt 2>&1

sec STORAGE
{
  df -h $HOME/ChatGPT/JUPI | tail -1
  mkdir -p $HOME/ChatGPT/JUPI/fio-bench
  fio --name=seqw --directory=$HOME/ChatGPT/JUPI/fio-bench --rw=write --bs=1M --size=1G --direct=1 --ioengine=libaio --iodepth=8 --group_reporting 2>&1 | grep -E "WRITE|bw="
  fio --name=seqr --directory=$HOME/ChatGPT/JUPI/fio-bench --rw=read --bs=1M --size=1G --direct=1 --ioengine=libaio --iodepth=8 --group_reporting 2>&1 | grep -E "READ|bw="
  fio --name=randr --directory=$HOME/ChatGPT/JUPI/fio-bench --rw=randread --bs=4k --size=256M --direct=1 --ioengine=libaio --iodepth=32 --group_reporting 2>&1 | grep -E "READ|iops|IOPS"
  rm -rf $HOME/ChatGPT/JUPI/fio-bench
} > $OUT/storage.txt 2>&1

sec INFERENCE
python3 infer_final.py > $OUT/inference.txt 2>&1

kill $(cat $OUT/thermal.pid) 2>/dev/null
sensors 2>/dev/null | head -6 > $OUT/thermal-end.txt
echo "FINAL DONE $(date -Is)" >> $OUT/suite.log
ls -la $OUT >> $OUT/suite.log
cd $OUT && sha256sum * > SHA256SUMS.txt 2>/dev/null; cd $S
tar -cf /tmp/jupi-final-out.tar -C /tmp/jupi-final OUT
sha256sum /tmp/jupi-final-out.tar > $OUT/tarball.txt
