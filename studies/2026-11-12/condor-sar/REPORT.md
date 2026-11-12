CONDOR-LINEAGE SAR v0  /  JUPI + JUPI2  /  2026-11-12 (PST)
SYNTHETIC DATA ONLY. PUBLIC EDITION.
Node image binaries, exchange partials and compare products are omitted
from this packet; the protocol, code, figure and attempt log are included.

LINEAGE
  AFRL's 2010 Condor cluster (PS3s + GPUs, COTS) ran SAR image formation among its workloads.
  It is architectural inspiration only: no AFRL code, data, or benchmark numbers are used or compared.
  This run: two console-Linux nodes (PS3's successors) split one synthetic aperture, scatter/gather the
  complex image, and audit each other's halves with an independent stdlib implementation.

FROZEN BEFORE COMPUTE
  protocol/PROTOCOL.json  sha256 0206d588ee6f51fd5c6b2aaeab38d9dfb0775dd4ed8f2b2ddd4b533f40a28e84  (frozen 07:48:50 PST)
  code/condor_sar.py      sha256 bf59089336374f230c8df4addd175a8270220a2a30b9abd24c919c022220977e  (same bytes on both nodes)
  Theory values (resolution, pair predictions, ghost sites, precision-cliff prediction) were computed and
  written into the protocol before any node run. make_protocol.py is kept alongside it.

SETUP
  X-band 9.6 GHz (lambda 31.23 mm), B 150 MHz, R0 1000 m, 256 pulses x 0.0625 m = 16 m aperture,
  v 100 m/s -> PRF 1600 Hz. Range-compressed, unweighted sinc phase history generated in code
  (33 point targets: 3 isolated, 14 pairs = "dense cluster" at 0.7..1.5 rho, 6 seeded random,
  E exactly at swath edge, O1 beyond the swath, O2 outside the image in azimuth).
  Time-domain backprojection, 256 x 384 grid at 0.25 m + 1/16 m fine cuts.
  nominal rho: range c/2B = 0.999 m, azimuth lambda R/2L = 0.976 m; -3 dB IRW theory = 0.886 rho.

WHAT RAN WHERE (CPU only, nothing installed, no GPU, no services touched)
  JUPI   pulses [0,128)    numpy 2.3.5 / py 3.12.14 (existing tool runtime); witness: system py 3.14.9 stdlib
  JUPI2  pulses [128,256)  numpy 2.5.4 / py 3.14.10 (existing venv);        witness: system py 3.14.10 stdlib
  Both nodes also built the full image (M=1) and the decimated images; the orchestration host summed partials and scored.
  Gate pre-run: JUPI 6.24 GB avail, swap 0.0%;  JUPI2 5.60 GB avail, swap 8.3%.  RLIMIT_AS 512 MiB in-process.

RESULTS VS FROZEN CRITERIA
  PASS  IRW (+/-10%): T0 az 0.870 m (+0.7%), rg 0.889 m (+0.5%); T1 -1.4%/+0.2%; T2 +1.5%/0.0%.
  PASS  PSLR [-14,-12.5]: -13.22/-12.96 (T0), -13.22/-13.24 (T1), -13.23/-13.11 (T2) dB. Theory -13.26.
  PASS  Position < 0.5 px: 0.033, 0.009, 0.017 px (T0,T1,T2).
  PASS  Scatter/gather determinism: summed partials vs JUPI2 single-node full: max |diff| 3.7e-13
        (1.5e-15 of peak; not bit-identical, summation order). Tolerance 2.5e-7.
  PASS  Cross-node: phase history bit-identical; JUPI full image == JUPI2 full image BIT-IDENTICAL
        despite different numpy (2.3.5 vs 2.5.4) and Python (3.12 vs 3.14).
  PASS  Integer detection table (39 targets): sha256 9c32fb5a...d4fd identical on JUPI, JUPI2, summed.
  PASS  Cross-witness: each node re-derived 512 random pixels of the OTHER node's half, seeded from the
        peer file hash, using stdlib only (re-generating range bins from the protocol, no numpy, no data file).
        JUPI checked JUPI2: max err 2.0e-14.  JUPI2 checked JUPI: max err 1.4e-14.  Tol 1e-7.
        Self stdlib-vs-numpy reference (384 px): 1.4e-14 / 2.8e-14.
  PASS  O1 (outside swath) at its true pixel: exactly 0 (no support). Whole region beyond the window: exactly 0.
  PASS  f32 cross-node: all precision-sweep cuts bit-identical between nodes.
  FAIL  Frozen alias metric: "max spurious outside 3 m of targets > -20 dB" fired already at M=1 (-13.9 dB).
        Cause: coherent sidelobes of the unweighted azimuth pairs reach past 3 m. The metric was badly
        specified, not the radar. See post-hoc probe below; the frozen onset claim is therefore unscored.

EDGE CASES (report-only, vs frozen theory)
  Pair resolution (-3 dB dip rule): 14/14 pairs matched the frozen phase-aware prediction.
    Resolved: az 0.9, 1.1, 1.25, 1.5 rho; range 0.9, 1.1 rho. NOT resolved: 0.7, 0.8, 1.0 both axes;
    range 1.25 and 1.5. In-phase theory threshold is 1.525 rho. Resolution here is decided by the
    relative carrier phase, not separation: a 0.9 rho az pair near anti-phase dips -20.2 dB, while range
    pairs at exactly c/2B are forced in-phase (2 pi fc/B = 2 pi x 64) and merge.
  Swath-edge target E: its exact-range azimuth cut is identically zero (no supported bin at the true
    range). It still shows up 0.197 m inside the swath at -0.38 dB with a half mainlobe (IRW 0.397 m,
    -55%). Risk: looks like a real full-strength target, mislocated by ~0.8 px.
  Outside target O1: no energy beyond the window, but its range-sinc tail leaks INTO the swath:
    -25.6 dB ghost at the window edge (y 1039.5), consistent with an unweighted sinc tail ~6 m away.
  PRF decimation (post-hoc probe at the FROZEN predicted ghost sites; compare/POSTHOC-alias.json):
    PRF 1600 / 800 / 400 / 200 Hz -> O2 ghost -40.4 / -39.3 / -1.4 / -1.3 dB; T0 grating lobe -42.6 / -41.1 / -33.3 / -0.3 dB.
    Onset exactly where predicted: O2 (outside the image) aliases into scene center at 400 Hz (M=4),
    landing within 0.12 m of the predicted site; in-scene targets alias at 200 Hz (M=8).
  Precision cliff (the Cell/SPU single-precision lineage case), single target, aperture grows with R0:
    R0 km  pulses   f32 naive gain / phase rms   predicted     f32 ref-diff
    1        256    -0.001 dB / 0.015 rad        -0.0006 dB    0.000 dB / 8e-8 rad
    4       1024    -0.010 dB / 0.060 rad        -0.009        0.000
    16      4096    -0.16  dB / 0.24  rad        -0.15         0.000
    64     16384    -2.64  dB / 0.95  rad        -2.34   CLIFF 0.000
    256    65536    -33.1  dB / 1.80  rad        -37.5   image destroyed (no mainlobe)   0.000
    The cliff (< -1 dB) lands at 64 km on both nodes, matching the frozen ulp model. The fix in the
    SPU spirit costs nothing: keep the per-pulse reference range in float64 (PPE side) and do only the
    small differential range in float32. That holds a 0.000 dB loss out to 256 km and a 4 km aperture.

THROUGHPUT / RESOURCES
                       JUPI              JUPI2
  numpy backprojection 3.12 M px-pulse/s  3.62 M px-pulse/s   (single thread)
  stdlib witness       7.0 k px-pulse/s   11.1 k px-pulse/s   (includes re-generating 2 bins x 33 targets each)
  produce wall / CPU   30.1 s / 27.7+2.5 s 25.4 s / 22.4+3.1 s
  witness wall         16.4 s            10.4 s
  total wall           46.5 s            35.8 s   (budget 600 s)
  peak RSS             64.0 MiB numpy, 24.2 MiB stdlib   63.2 MiB, 24.3 MiB
  post-run avail/swap  6.22 GB / 0.0%    5.58 GB / 8.3%

WITNESS NEGATIVE CONTROLS (orchestration host, same stdlib code, against tampered copies of JUPI 2's partial)
  1% of pixels +1e-3: CAUGHT.  Pulse 200 dropped: CAUGHT (err 4.9).  Global phase 1e-9 rad: CAUGHT.
  Single corrupted pixel (T0 peak +1.0): MISSED. K=512 of 98,304 pixels catches a single-pixel edit with
  ~0.5% probability. The witness protects against systematic errors, not one forged pixel.

CAVEATS
  Synthetic data, ideal motion, slant-plane 2-D, no noise or clutter, no weighting. Linear interpolation
  on 16x-oversampled range data. Both nodes are x86-64 Jaguar-class CPUs, so bit identity shows the pipeline
  is deterministic across numpy/Python versions, not across ISAs. The alias metric failed as written; the
  probe that replaces it was written after seeing that failure (but reads the frozen ghost sites).

FILES
  protocol/  PROTOCOL.json (+sha256), FROZEN-AT.txt, make_protocol.py
  code/      condor_sar.py (+sha256; frozen, unchanged), analyze.py, figure.py,
             make_protocol.py, posthoc_alias.py
  failed-attempts/ATTEMPTS.txt   CONDOR-SAR-FIGURE.png
  Omitted from this public packet: per-node produce/witness binaries and receipts,
  exchange partials, and compare/ products (synthetic, not requested for publication).
