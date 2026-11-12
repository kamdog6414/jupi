GHOSTING NATIVE CONTOUR UNCERTAINTY CHALLENGE v1 + REVISION R2
JUPI / JUPI 2 pair run, 2026-11-12 (times PST)
PUBLIC EDITION. Results tables and measurement code only.
The reference photograph and the challenge packet are private evidence
and are NOT included. This is a retrospective pixel-shape study. It is
not flight validation, world scale, or calibrated uncertainty.
Founder acceptance: false.

1. INPUTS
  The v1/R2 runs were computed against a private reference photograph
  and a private challenge packet. Those files, their filenames as private
  evidence, their hashes, and any node-local paths to them are omitted
  from this public edition and must not be published.
  Both nodes checked the same inputs before compute. Node agreement is
  reported below from the public tables and from a same-code comparison
  that is not reproduced here as raw JSON (the raw RESULTS files are
  derived from the private photograph and are omitted).

2. INTERPRETER / DECODER
  Attempt 1, both nodes: system /usr/bin/python3 (3.14.9 JUPI, 3.14.10
  JUPI 2) has no Pillow.
    Output: {"status":"HOLD","reason":"ValueError:EXISTING_PILLOW_REQUIRED_NO_INSTALL"} rc=2.
    No output dir was created. The HOLD is retained as a finding.
  Attempt 2, using an already-installed Python with Pillow, which the
  run instructions allow. Nothing was installed.
    JUPI : an already-installed Python 3.12.14 tool runtime, Pillow 13.0.0
    JUPI 2: an existing local venv on /usr/bin/python3.14 (3.14.10), Pillow 13.0.0
    Both: PIL.features.version('jpg') = 6.2 (libjpeg API), libjpeg-turbo 3.2.0.
    Same Pillow/libjpeg-turbo build on both nodes, so this is implementation
    replication, NOT decoder diversity.
    Different CPython (3.12 vs 3.14), yet the outputs were byte-identical.
  djpeg was not used anywhere in the protocol.
  Neither node has /usr/bin/time. Resources come from the script's own
  rusage plus a stdlib wrapper (code/run_wrap.py) using RUSAGE_CHILDREN.

3. PREFLIGHT AND RESOURCES (256 MiB RLIMIT_AS set by the script, 600 s budget, CPU only, no GPU)
                    MemAvail      swap   load(1m)  wall s  cpu user+sys s  peak RSS
  v1 JUPI           6.26 GB       0.0%   1.09      44.85   44.04+0.08      81.2 MiB (85131264 B)
  v1 JUPI 2         5.61 GB       8.3%   0.10      38.89   38.66+0.08      83.9 MiB (87982080 B)
  R2 JUPI           6.26 GB       0.0%   1.11      57.76   57.85+0.06      81.4 MiB (85352448 B)
  R2 JUPI 2         5.61 GB       8.3%   0.39      45.47   45.57+0.08      84.3 MiB (88367104 B)
  Gates passed: >=256 MiB, JUPI gate >800 MB and swap <25%.
  Note on JUPI load ~1.0: ksoftirqd/1 was pinned near 100% (kernel softirq,
  ~3 h old). No user job was running; 8 CPUs. Left untouched.

4. ORIGINAL v1 RESULT FILES
  RESULTS were byte-identical on JUPI and JUPI 2. Receipt and progress
  files differed only in runtime fields, as expected. The raw JSON is
  omitted because it is derived from the private photograph.
  RESULTS holds every measured row, edge, TEST prediction, miss row
  (null prediction) and nuisance setting for all 18 variants. The public
  per-variant summary is compare-equivalent VARIANT-TABLES.txt.

5. NODE AGREEMENT (code/compare_nodes.py: ints/rows exact, floats 1e-7 px, IoU 1e-10)
  v1: 0 disagreements. Rank eligibility identical. Input/code/manifest
      hashes in the (omitted) receipts were identical across nodes.
  R2: 0 disagreements. Rank eligibility identical. RESULTS byte-identical.

6. MISS FINDING (Root's qualification): CONFIRMED
  18/18 variants are HOLD_UNSUPPORTED_TEST_ROWS. No v1 ranking is reportable.
  Cylinder has misses in 18/18 variants (3..145 rows). Ghosting has misses
  in 15/18 (0 only in the three energy_central_mass-0.8 variants). Total
  unsupported TEST rows: 1956 (Ghosting 633, cylinder 1323).
  Every miss is ABOVE the projected model top. None are below the base.
  Measured rows span y 238..1162 (925 px) in every variant.
  Cause: the FIT objective charges a flat 25 px per unsupported row. That
  is cheaper than width error, so the search shrinks the scale (cylinder
  down to 8.0-9.1 px/unit, model height 520-590 px) and abandons the top
  rows, which are near the fairing.
  The unsupported v1 numbers favored Ghosting on width in all 18 variants
  (dW -0.29..-2.64 px), but they are diagnostic only and are not a ranking.
  Full per-variant table: VARIANT-TABLES.txt (fit_n/test_n, MAE, IoU,
  misses, deltas, span status, winners, scale/base/centerline).

7. R2 PROTOCOL (frozen before any R2 fit)
  This is a single CAMERA/SUPPORT change. Measurement code, 18 variants,
  32-row even/odd split, grid, models, centerline fit and margins
  (1 px, 0.02 IoU) are all unchanged.
  Rule: a (scale, base_y) candidate is admissible only if every measured
  row's y position (FIT+TEST, y only, no TEST widths) falls inside the
  projected model support, using the exact v1 model_w test.
  The search minimizes the unchanged FIT width MAE over admissible
  candidates. If none are admissible, the variant is
  HOLD_NO_ADMISSIBLE_SUPPORT.
  Success = 0 unsupported TEST rows in both models across all 18 variants
  on both nodes, with node agreement. Only then are winners reported.
  Code: code/r2_native_contour.py
    sha256 acef3072c5ebdd2a0f6a6b3c71b98668bf7df0b69e43fd6a50e8a45b483986eb
  (derived from the v1 source; diff = admissibility filter, protocol pin
  and extra receipt fields). The published code still expects a local
  challenge packet and photograph, which are not in this repository.
  Disclosure: the rule was chosen after seeing v1 miss POSITIONS (and,
  unavoidably, v1 scores). It was frozen before any R2 fit and was not
  tuned. First try only.
  The frozen R2 protocol file itself pins hashes of the private packet
  and is omitted from this public edition.

8. R2 RESULT: RESOLVES THE LIMITATION (first try, no iteration)
  R2 RESULTS were byte-identical on both nodes. 0 unsupported TEST rows
  in both models across 18/18 variants. All COMPLETE.
  Width winner (1 px margin): GHOSTING 17, INDETERMINATE 1
    (energy_central_mass-0.8-roi120, dW -0.80), CYLINDER 0.
  IoU winner (0.02 margin):   GHOSTING 8 (all energy_central_mass except
    0.8-roi120), INDETERMINATE 10 (all 9 peak_contiguous variants with
    |dIoU|<=0.003, plus ecm-0.8-roi120 at +0.018), CYLINDER 0.
  Ghosting test width MAE 5.56..17.89 px vs cylinder 6.95..23.32.
  dW range -0.80..-5.45 px.
  Caveat: the constraint binds. The cylinder sits at the minimum
  admissible scale (14.3 px/unit, base 1163) in 18/18 variants, and
  Ghosting does in 14/18. The cylinder's free optimum lies outside full
  support, so R2 answers "which shape fits when both must span the
  measured body", which is a stronger support assumption than v1. The
  peak_contiguous methods give low IoU for both shapes (0.25..0.52), so
  overlap cannot discriminate there. Adjacent rows are correlated, and
  the margins are abstention margins, not confidence bounds.

9. LAYOUT (this public packet)
  REPORT.md
  VARIANT-TABLES.txt
  code/ r2_native_contour.py acef3072...
        compare_nodes.py     d9a22abc...
        run_wrap.py          b37ab08b...
  Omitted by design: the photograph, the challenge packet, per-node
  RESULTS/RECEIPT/PROGRESS/FROZEN-SPLIT JSON, the R2 protocol JSON
  (it pins private-file hashes), and any node-local paths.
  Nothing installed. No GPU. No services were changed.

LIMITS
  Not a flight validation. Camera calibration: UNKNOWN. World pose and
  timing: HOLD. Physical validation: NOT_RUN. The private reference
  photograph is not available in this repository, so a third party
  cannot reproduce the numeric tables from this packet alone. They can
  inspect the method (the published code) and the reported scores
  (VARIANT-TABLES.txt). Decoder diversity was not obtained: both nodes
  used the same Pillow/libjpeg-turbo build.
