# jupi-1.0 performance: measured vs expected (groku, Nov 24 2026)

## Measured (QEMU/KVM on NIKOLAI, not a PS4; host CPU, -smp 4, 2 GiB)
Live kernel (0bd27266...b289) vs jupi-1.0 (a06fdd7a...2b8e), 3 alternating boots each, 3 runs per boot (n=9 per side). Static microbench `qemu/src/jupibench.c`.
| metric | live median | jupi-1.0 median | delta | jupi-1.0 + psi=1 + both sky2 params | jupi-1.0 preempt=voluntary (1 boot) |
|---|---:|---:|---:|---:|---:|
| getppid syscall (ns) | 46.40 | 47.50 | +2.4% | 47.40 | 47.90 |
| pipe round trip (us) | 31.00 | 29.61 | -4.5% | 31.05 | 49.36 |
| fork+exit (us) | 158.50 | 158.70 | +0.1% | 159.40 | 161.50 |
| 256 MB anon fault-in (ms) | 15.50 | 15.50 | 0.0% | 14.20 | 16.60 |
| triad (GB/s) | 17.35 | 17.70 | +2.0% | 17.97 | 16.98 |
Reading: no regression beyond VM noise (about +/-5%). This says nothing about Jaguar speed. preempt=voluntary showed no gain in the VM (pipe RTT worse), so it is NOT recommended.

VM functional checks (all boots): release unchanged; `#jupi-1.0` + `(jupi@nikolai)` in /proc/version; cpuset controller present; PSI absent by default, present with psi=1; lru_gen 0x0000 by default, 0x0007 after enable; sky2 params N by default, Y when set; 200 systemd units -> 0 dying pids, 0 dying memory (pidfs fix holds). The VM has no Aeolia chip: the sky2 poll code did not run (same gap as GRO-52).

Source-level: Codex mock suites re-run on the final sky2.c: poll policy 4,096 carrier cases + 8 lifecycle checks, 0 mismatches; fast path 32,256 cases, 24 skipped PHY_STAT reads, 0 other mismatches (logs/check-*-final.log).

## Expected on hardware (NOT measured on jupi-1.0 yet)
| What | Expected | Basis | Grade |
|---|---|---|---|
| JUPI 1 IRQ 24 | ~3,590/s -> under 100/s with `sky2.aeolia_poll_phy=1` | mask removes the PHY IRQ source; R1 risk that the storm has another source | SUSPECTED |
| JUPI 1 CPU 1 | 100% softirq -> usable core | Codex arms: 4 workers with CPU 1 2.38 GFLOP/s vs 26.56 without | SUSPECTED until Stage C |
| JUPI 1 7-core / 8-core work | up to one more Jaguar core (~1/8 more CPU) | Codex prime: 7 cores 4,878.84 ev/s with CPU 1 excluded | SUSPECTED |
| JUPI 2 | no change | no option applies to Belize; config adds are off | SUSPECTED (Stage A checks it) |
| Fast-path fallback (0002) | fewer MDIO reads per empty IRQ; IRQ rate unchanged; CPU 1 relief partial | Codex: earlier coalescing attempts gave no CPU reduction | UNSOURCED size |
