# Rebuilding jupi-1.0 outside the lab

`../kernel/build-jupi-kernel.sh` is the lab script as it ran on Nov 24. It expects lab folders
(`build/`, `baseline/`, a local toolchain and firmware copy) that are not in this repo, so it will not
run as-is. These are the same inputs in portable form.

1. Source: feeRnt/ps4-linux-12xx at v6.15.4__crashnt-4.7, commit 2dbf2bb3 (git tree d5a8c543).
2. Apply `../kernel/patches/0000` to `0003` in order.
3. Use `../kernel/jupi-1.0.config` as `.config` (sha256 7e3c1e64f56203c08e6383898feb0804d64e5136fc664799deeda8f6c29ee001).
4. Put the ten MediaTek MT7668 files named in `CONFIG_EXTRA_FIRMWARE` under your firmware directory
   and pass it as `CONFIG_EXTRA_FIRMWARE_DIR`. They are not in this repo.
5. Toolchain: clang/LLD 18.1.8 (`LLVM=-18`), pahole 1.31, GNU make 4.4.1,
   `KCFLAGS="-march=btver2 -mtune=btver2 -O3"`,
   `KBUILD_BUILD_USER=jupi KBUILD_BUILD_HOST=nikolai KBUILD_BUILD_VERSION=jupi-1.0 LOCALVERSION=`.
6. `make LLVM=-18 bzImage`, then check `uname -r` is `6.15.4-crashnt-4.7_no-built-in-fw`.

A build from steps 1 to 6 has the same source, patches and config. Its sha256 will differ unless you
also reproduce the build paths and the three separate timestamps in [repro/RECIPE.md](repro/RECIPE.md).
Bit-identical rebuilds of a06fdd7a... are CONFIRMED only on the lab host with that recipe.
This portable list was written from the lab script and recipe. It has not been run on another host as
written. UNTESTED.

- groku
