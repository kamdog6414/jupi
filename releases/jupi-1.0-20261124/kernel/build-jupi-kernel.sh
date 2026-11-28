#!/bin/bash
# groku 2026-11-24 - JUPI official kernel 1.0. Mirrors the Nov 20 Sol recipe (jupi-sol-cgroup-20261120/build-image.sh)
# and the GRO-52 poll-phy build. Source tree d5a8c543 + patches/0000..0003 already applied in build/linux.
# Writes only inside this folder (build/ is a symlink to /mnt/hcdu/overflow/jupi-kernel-official-20261124-build).
set -euo pipefail
umask 077
R="$HOME/fullcircle-core/jupi-kernel-official-20261124"
d="$R/build"
cd "$d"
export PATH="$d/toolchain/unpacked/usr/bin:$PATH"
export LD_LIBRARY_PATH="$d/toolchain/unpacked/usr/lib/x86_64-linux-gnu"
# JUPI identity: uname -v = "#jupi-1.0 SMP PREEMPT_DYNAMIC <date>", /proc/version "(jupi@nikolai)".
# uname -r is kept = 6.15.4-crashnt-4.7_no-built-in-fw on purpose (JUPI 1 boot audit / perf profile pin it).
export KBUILD_BUILD_USER=jupi KBUILD_BUILD_HOST=nikolai KBUILD_BUILD_VERSION=jupi-1.0
export LOCALVERSION=
flags='-march=btver2 -mtune=btver2 -O3'
mkdir -p out
cp baseline/pidfs-embedded.config out/.config
# Config changes (all default-off at runtime; see CONFIG-CHANGES.md)
linux/scripts/config --file out/.config -e PSI -e PSI_DEFAULT_DISABLED -e CPUSETS -d CPUSETS_V1 -e LRU_GEN -d LRU_GEN_ENABLED -d LRU_GEN_STATS
make -C linux O="$d/out" LLVM=-18 KCFLAGS="$flags" olddefconfig
cp out/.config "$R/artifacts/jupi-1.0.config"
diff baseline/pidfs-embedded.config "$R/artifacts/jupi-1.0.config" > "$R/artifacts/config-diff-vs-live.txt" || true
echo "config diff lines: $(wc -l < "$R/artifacts/config-diff-vs-live.txt")"
hostdeps="$d/toolchain/roach-openssl"
date +%s > "$R/logs/build-start.epoch"
make HOSTCFLAGS="-Wno-error=incompatible-pointer-types-discards-qualifiers -I$hostdeps/include -I$hostdeps/include/x86_64-linux-gnu" HOSTLDFLAGS="-L$hostdeps/lib" CONFIG_EXTRA_FIRMWARE_DIR="$d/baseline/embedded-linux-firmware" -j6 -C linux O="$d/out" LLVM=-18 KCFLAGS="$flags" bzImage
date +%s > "$R/logs/build-end.epoch"
test "$(cat out/include/config/kernel.release)" = 6.15.4-crashnt-4.7_no-built-in-fw
cp out/arch/x86/boot/bzImage "$R/artifacts/bzImage-jupi-1.0"
bash linux/scripts/extract-vmlinux "$R/artifacts/bzImage-jupi-1.0" > baseline/candidate-vmlinux
python3 baseline/seal-firmware-inputs.py verify baseline/candidate-vmlinux > "$R/artifacts/candidate-firmware.json"
cmp baseline/embedded-linux-firmware.json "$R/artifacts/candidate-firmware.json"
linux/scripts/extract-ikconfig "$R/artifacts/bzImage-jupi-1.0" > "$R/artifacts/embedded.config"
cmp "$R/artifacts/jupi-1.0.config" "$R/artifacts/embedded.config"
strings "$R/artifacts/bzImage-jupi-1.0" | grep -m1 "Linux version" > "$R/artifacts/version-string.txt" || true
echo JUPI_1_0_READY
