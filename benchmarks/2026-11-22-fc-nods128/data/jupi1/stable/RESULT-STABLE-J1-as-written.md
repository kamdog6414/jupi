# RESULT-STABLE-J1: JUPI 1 stable run on real workloads, 2026-11-22
Groku.2 (executor), on Kam's 2:23 PM PST order. No test-backend-ops was run. Times PST (logs are UTC).

VERDICT: PASS. 0 amdgpu ring timeouts/resets, swap 0 MiB peak, both soaks byte-identical every round.

## llama-bench qwen3-0.6b Q4_K_M, -ngl 99 -fa 0 -t 6 -r 3, pp512 / tg128 (tok/s +- sd)
```
config        stock pp512       patched pp512     stock tg128     patched tg128
-ub1        56.18 +-0.05     56.15 +-0.05   75.14 +-0.08   74.73 +-0.06   (-0.1% pp)
-ub64      527.24 +-0.32    552.84 +-0.16   75.25 +-0.28   74.92 +-0.19   (+4.9% pp)
-ub512     760.14 +-0.15    796.57 +-0.23   74.56 +-0.10   74.98 +-0.09   (+4.8% pp)
(-ub1 uses -b 2; -ub64/-ub512 use -b 2048. Stock at ub64/ub512 is fast but its OUTPUT is wrong, see the morning packet.)
```

## Soaks (llama-server, 20 prompts per round, temp 0, seed 1, cache_prompt off)
```
patched -ub 64 -b 2048 (FC-NODS128 ICD)
  window 14:29:01-15:28:10 PST (first/last round end), 69 rounds
  byte-match vs JUPI 2 patched -ub 64 outputs: 1380/1380
  tg med 61.92 (min 61.45, max 62.21); pp med 236.19 (min 234.86, max 236.58)
  tg drift 2nd half vs 1st half -0.10%; round wall med 52.15 s
  server RSS 329 -> peak 364 MB (flat after round 2); MemAvailable min 5461 MiB; swap peak 0 MiB; new amdgpu faults 0

stock -ub 1 -b 2 (system RADV, control)
  window 15:29:29-16:29:15 PST (first/last round end), 59 rounds
  byte-match vs JUPI 2 accepted live outputs (2026-11-19): 1180/1180
  tg med 65.89 (min 65.57, max 66.05); pp med 80.57 (min 80.20, max 80.74)
  tg drift 2nd half vs 1st half +0.13%; round wall med 61.81 s
  server RSS 364 -> peak 400 MB (flat after round 2); MemAvailable min 5473 MiB; swap peak 0 MiB; new amdgpu faults 0

```
Loaded driver, read from /proc/<pid>/maps of each soak server: LOADED-DRIVER.txt
(patched = 117805de...ff0d5 with VK_ICD_FILENAMES set; stock = acf91948...a34ae5 with no VK_ env).

Guards: guard4.sh (pidfile root, kills the tree on any new amdgpu ring timeout/reset line, swap > +256 MiB or MemAvailable < 1000 MiB; 5 s checks, 60 s dmesg heartbeat in guard.log). stable.py also checks dmesg and swap each round. Every log line is fsynced.

## Files (sha256)
```
c3b22c68e422fb8a7531bc1b574e9ac2193781f89d26bfda223079ea6d9c9b5c  B-patched-ub1.bench.err
aa3bfed8e3f4846f01a2b08a1d0295d7211560b27d3e86f7e5b28b9f0bd57d30  B-patched-ub1.bench.json
c3b22c68e422fb8a7531bc1b574e9ac2193781f89d26bfda223079ea6d9c9b5c  B-patched-ub512.bench.err
6dcf1b3774e3977cd4d416c9035cbb247ef530d106fb2d95192250e30965803e  B-patched-ub512.bench.json
c3b22c68e422fb8a7531bc1b574e9ac2193781f89d26bfda223079ea6d9c9b5c  B-patched-ub64.bench.err
0cd231ce02c3dc91406bcde84eb5447c370960f3d170a9755f86a3899ad9d11e  B-patched-ub64.bench.json
c3b22c68e422fb8a7531bc1b574e9ac2193781f89d26bfda223079ea6d9c9b5c  B-stock-ub1.bench.err
e5d17179350e192ccb2ee463365fd7197948f052dac994fa07096f8e6d11ad0c  B-stock-ub1.bench.json
c3b22c68e422fb8a7531bc1b574e9ac2193781f89d26bfda223079ea6d9c9b5c  B-stock-ub512.bench.err
fb1efe859b07a80a6c82ec009a5fcfc48eacef9e3859636415c144cad4740f9e  B-stock-ub512.bench.json
c3b22c68e422fb8a7531bc1b574e9ac2193781f89d26bfda223079ea6d9c9b5c  B-stock-ub64.bench.err
a576fcebcb58742129060994dd4a942358077431c82294809abce4d54ace9b58  B-stock-ub64.bench.json
2abd22ae4fc7667375f33f32852399b3b5994037c308480b1238812d4bc44339  LOADED-DRIVER.txt
e7fdc43eb0d9c017a1604008a199cf1516244fa07a5b7e35743120dbb8431eaa  STATS.json
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  drv.out
d9c8531172e1ed709914b4989f9876003e2a9f366d52c3a279695b4026490123  finish.py
d3a5ab1c4a59937ebeb25cc7dbe2d533ed2732314a94741731c7b98adf9c3a52  guard.log
809ca5698cf14af006ab247d2de5f27c0e09849da7604dea92bb44474ba6bf1b  guard4.sh
6b40b18ecadd94a1330c81b5dedf2ac7c13a16f96929901a77f09e89b5a7505c  run.log
8f7400b0b9aa4f964d597ef41c4711f9186efa024149a0d8304e1ae3ebdd83fd  server-patched-ub64.log
19c56b478f05fa45d4fceefd5624addcab4a6b31283156a2c806a309d2a9a8e0  server-stock-ub1.log
f3ffbeea4a4a61cbfd5b0553ef8a06146bafa29cc70fceca1d445a7146e35080  soak-patched-ub64.jsonl
965b2974ca97f931af132ef70b881f8287a8e349abca2fdecd1b37e2e8d191b5  soak-stock-ub1.jsonl
457a6534b2776c1c0ca43b419340ced0521d0a2ad74378a1a6b8ea322ff7d340  stable.py
0cb8b9088809671771319df493fed4353b08cbb48542a513fe03e52e01f7506b  summary-patched-ub64.json
e7844837492c8fc33fc863a5ba91950545ecae65806067e7e02ac6cf2aa80f29  summary-stock-ub1.json
```
