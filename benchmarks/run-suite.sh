#!/bin/bash
# JUPI refined benchmark suite — runs on JUPI, writes raw sections to OUT/.
S=/tmp/jupi-suite
OUT=$S/OUT
mkdir -p $OUT
cd $S
echo "SUITE START $(date -Is)" > $OUT/suite.log
# thermal sampler for the whole run
( while :; do echo "$(date +%s) $(cat /sys/class/hwmon/hwmon1/temp1_input 2>/dev/null)"; sleep 2; done > $OUT/thermal.log 2>/dev/null & echo $! > $OUT/thermal.pid )
sec(){ echo "=== $1 $(date -Is) ===" >> $OUT/suite.log; }

sec SYSINFO
{
  date -Is; uname -a; cat /proc/sys/kernel/random/boot_id
  grep -m1 "model name" /proc/cpuinfo; nproc; free -m
  vulkaninfo --summary 2>/dev/null | grep -E "deviceName|driverName|driverInfo|apiVersion" | head -4
  curl -s http://127.0.0.1:11434/api/tags | head -c 400; echo
  sensors 2>/dev/null | head -10
} > $OUT/sysinfo.txt 2>&1
vulkaninfo > $OUT/vulkaninfo.txt 2>/dev/null

sec BUILD
{
  for f in fma32_wg64 fma32_wg128 fma32_wg256 fma32_wg512 fma32_ilp fma64 fma64x2 copy; do
    glslc $f.comp -o $f.spv && echo "glslc $f OK"
  done
  gcc -O2 -o vkprobe2 vkprobe2.c -ldl && echo "gcc vkprobe2 OK"
  gcc -O2 -o gpubench gpubench.c -lOpenCL && echo "gcc gpubench OK"
  sha256sum vkprobe2.c gpubench.c *.comp
} > $OUT/build.txt 2>&1

sec GPU-RADV
./vkprobe2 /tmp/jupi-suite > $OUT/gpu-radv.txt 2>&1

sec GPU-OPENCL
./gpubench > $OUT/gpu-opencl.txt 2>&1

sec CPU
{
  python3 -c "import numpy; numpy.show_config()" 2>&1 | head -12
  for t in 1 2 4 8; do
    echo "--- threads=$t ---"
    OPENBLAS_NUM_THREADS=$t OMP_NUM_THREADS=$t MKL_NUM_THREADS=$t python3 cpu_bench.py gemm
  done
  echo "--- misc ---"
  python3 cpu_bench.py misc
} > $OUT/cpu.txt 2>&1

sec CRYPTO
openssl speed -elapsed -seconds 3 sha256 aes-256-gcm > $OUT/crypto.txt 2>&1

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
python3 infer_bench.py > $OUT/inference.txt 2>&1

kill $(cat $OUT/thermal.pid) 2>/dev/null
sensors 2>/dev/null | head -6 > $OUT/thermal-end.txt
echo "SUITE DONE $(date -Is)" >> $OUT/suite.log
ls -la $OUT >> $OUT/suite.log
