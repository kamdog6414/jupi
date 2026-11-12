studies/2026-11-12
=================

Public, additive study packets from 2026-11-12 on JUPI (PS4) and
JUPI 2 (PS4 Pro). Times are America/Los_Angeles (PST). This folder
is a public edition: local endpoints, ssh aliases, home paths,
radio-interface operational notes, private photographs and the
private contour challenge packet are omitted or redacted.

  translation-gate/   JUPI Translation Gate v0
  condor-sar/         Condor-lineage synthetic SAR v0
  native-contour/     Native contour uncertainty, v1 + R2 (tables and code only)

Hashes named as "frozen" are the laboratory originals used as
reproducibility anchors. Where a published file was sanitized, that
is stated next to the file, and its bytes no longer match the frozen
hash. See SANITIZATION.txt.


translation-gate/
----------------
A 0.6B local model (qwen3-0.6b, CPU) proposed structured answers for
50 frozen synthetic items. A stdlib verifier on both nodes accepted
or held each answer. Raw T0 accuracy was 17/50 (34%). The full gate
(schema + recompute) passed 0 silent wrong answers out of 150 outputs
on both seats, with 0 false holds. A schema-only gate would have
passed 82 of those 150 as wrong answers, including 12 wrong home
actions. Unanimous agreement among three prompt framings was wrong
for 3 of 14 unanimous items (precision 0.79).

  REPORT.md
  TRANSLATION-GATE-FIGURE.png
  protocol/   PROTOCOL.json (sanitized public copy), FROZEN-AT.txt,
              FROZEN-HASHES.txt, make_protocol.py (sanitized)
  code/       keys.py and verify.py unchanged; translate.py and
              make_protocol.py comments/strings sanitized
  raw/        outputs.jsonl  (150 prompts and verbatim model outputs;
              synthetic items only)
  failed-attempts/ATTEMPTS.txt

Limits: small model, one family, k = 3 framings rather than sampled
k = 5, 50 synthetic items. For numeric items the recompute and the
key share keys.py, so the numeric half of the zero-silent-wrong result
mostly shows the gate is wired correctly and is identical on two
machines. Open-ended translation has no oracle; there the HOLD rate,
not the silent-error rate, is the honest number. Physical actuation
was not performed. The published PROTOCOL.json endpoint is a
placeholder; the frozen hash is of the lab original.


condor-sar/
-----------
Two console-Linux nodes split one synthetic X-band aperture
(256 pulses), formed a time-domain backprojection image, and audited
each other's halves with an independent stdlib implementation. AFRL's
2010 Condor cluster is architectural inspiration only: no AFRL code,
data, or benchmark numbers are used or compared. Data are synthetic
(33 point targets, ideal motion, no noise or clutter). JUPI and
JUPI 2 full images were bit-identical despite different numpy
(2.3.5 vs 2.5.4) and Python (3.12 vs 3.14). Isolated-target IRW was
within 1.5% of theory. The frozen alias metric failed as written
(coherent sidelobes, not a radar fault) and is unscored; a post-hoc
probe at the frozen ghost sites is reported as such. A single-pixel
corruption was missed by the K=512 witness (~0.5% catch probability).

  REPORT.md
  CONDOR-SAR-FIGURE.png
  protocol/   PROTOCOL.json and condor_sar.py are published
              unchanged (frozen hashes still match)
  code/       condor_sar.py, analyze.py, figure.py, make_protocol.py,
              posthoc_alias.py
  failed-attempts/ATTEMPTS.txt

Limits: synthetic data, slant-plane 2-D, no weighting, linear
interpolation on 16x-oversampled range data. Both nodes are x86-64
Jaguar-class CPUs, so bit identity shows determinism across
numpy/Python versions, not across ISAs. This is not a real radar
collection and not a comparison to AFRL numbers. Node image binaries
are omitted from this packet.


native-contour/
---------------
A retrospective pixel-shape study (Ghosting vs cylinder) run on both
nodes. v1 was HOLD_UNSUPPORTED_TEST_ROWS on 18/18 variants (no
ranking). R2 added a span-coverage admissibility rule, frozen before
any R2 fit, and resolved that limitation on the first try: 0
unsupported TEST rows, Ghosting 17 / indeterminate 1 / cylinder 0 on
width (1 px margin). Results were byte-identical across nodes.

  REPORT.md
  VARIANT-TABLES.txt
  code/  r2_native_contour.py, compare_nodes.py, run_wrap.py
         (published unchanged; hashes in the report)

Limits: not flight validation, world scale, or calibrated uncertainty.
Camera calibration: UNKNOWN. Physical validation: NOT_RUN. Founder
acceptance: false. The reference photograph and challenge packet are
private and are not in this repository, so a third party cannot
reproduce the numeric tables from this packet alone. The published
code still expects those local inputs. Decoder diversity was not
obtained (same Pillow/libjpeg-turbo on both nodes). The R2 constraint
binds: the cylinder sits at the minimum admissible scale in 18/18
variants. Adjacent rows are correlated; the margins are abstention
margins, not confidence bounds. SpaceX / launch photographs used as
private reference evidence are not included and must not be added.
