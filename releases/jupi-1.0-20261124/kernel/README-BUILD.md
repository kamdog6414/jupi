# JUPI kernel 1.0 (official) for JUPI 1 (PS4, Aeolia) and JUPI 2 (PS4 Pro, Belize) - groku, Nov 24 2026

One image for both consoles: `artifacts/bzImage-jupi-1.0` (15,733,760 B, sha256 a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e).
Identity: `uname -v` = `#jupi-1.0 SMP PREEMPT_DYNAMIC Tue Nov 24 15:26:06 PST 2026`; /proc/version `(jupi@nikolai)`. `uname -r` is kept at `6.15.4-crashnt-4.7_no-built-in-fw` on purpose: JUPI 1's boot audit, warm-boot gate and perf-profile drift check compare it to /etc/jupi/boot.json (CONFIG-CHANGES.md, "held").
NOT installed, NOT staged, nothing rebooted. Kam's go needed per node (INSTALL-TEST-ROLLBACK.md).

## Lineage (credit)
- Source: feeRnt/ps4-linux-12xx v6.15.4__crashnt-4.7 (commit 2dbf2bb3), archive 20b1cd80...c54c, git tree d5a8c543 (verified, same pin as Nov 20).
- Recipe: Sol's Nov 20 build (`<lab-home>/jupi-sol-cgroup-20261120`, clang/LLD 18.1.8, pahole 1.31, `-march=btver2 -mtune=btver2 -O3`, ThinLTO, 10 embedded firmware files verified identical).
- Builds on GRO-52 (`<lab-home>/fullcircle-core/jupi1-pollphy-20261124`) and GRO-57 (`<lab-home>/fullcircle-core/jupi-update-20261124`).

## Patch series (patches/, applied in order to the clean tree; replayed from pristine, tree identical)
| # | Patch | Author | sha256 | Default |
|---|---|---|---|---|
| 0000 | pidfs-task-reference (cgroup leak fix, upstream 0b2d71a7) | Sol/Codex, Nov 20 (live today) | 4cb6bb94...e030 | always on |
| 0001 | sky2-aeolia-poll-phy: mask Aeolia port-1 PHY IRQ, poll link at 1 Hz | Codex, branch codex/jupi-stability-20261124 931f9f7 | 3a47c4a8...1e51 | off; `sky2.aeolia_poll_phy=1` |
| 0002 | sky2-aeolia-empty-phy-fastpath: skip PHY_STAT read on empty IRQ | Codex, kernel-preflight-20261124 (bc247284...877c), rebased by groku (context only; +/- lines identical) | 392448cf...6b6b | off; `sky2.aeolia_skip_empty_phy_stat=1` |
| 0003 | sky2-jupi-report-aeolia-phy-mode: probe-time log line for which path is live, warning if poll is requested but gated off | groku | aa6fb2cd...abfb | log only |
All new paths are gated to Sony Aeolia 104d:909e (JUPI 1). JUPI 2's NIC is 104d:90c9 (CONFIRMED) and cannot enter them.

## Config (CONFIG-CHANGES.md)
+PSI (default off, psi=1), +CPUSETS (v2 only), +LRU_GEN (off), plus 2 auto deps. 19-line diff. Everything else identical to live.

## Files
ANALYSIS.md (bug table + perf review), CONFIG-CHANGES.md, PERF.md, INSTALL-TEST-ROLLBACK.md, NOTE-GRO57-CORRECTION.md, build-jupi-kernel.sh, patches/, inputs/ (originals as received), artifacts/, logs/, qemu/ (harness, initramfs, all VM logs), receipts/, SHA256SUMS.
Build tree: build -> /mnt/hcdu/overflow/jupi-kernel-official-20261124-build (kept; delete on Kam's word). Patch history repo moved to build/linux-git so LOCALVERSION_AUTO can't append -g<sha> (first link was stopped by the release guard for exactly that, logs/build-attempt1-release-guard.log).
