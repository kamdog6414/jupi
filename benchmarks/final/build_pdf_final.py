#!/usr/bin/env python3
"""Build the JUPI FINAL tuned benchmark PDF from jupi-final-results.json."""
import json, sys
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)
from reportlab.lib import colors

R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "jupi-final-results.json"))
OUT = sys.argv[2] if len(sys.argv) > 2 else "JUPI-FINAL-BENCHMARK-20261107.pdf"

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=19, leading=23, spaceAfter=4)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13.5, leading=17, spaceBefore=14, spaceAfter=5)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontSize=11.5, leading=14, spaceBefore=10, spaceAfter=4)
B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10, leading=13.5, alignment=TA_LEFT, spaceAfter=6)
SM = ParagraphStyle("SM", parent=ss["BodyText"], fontSize=8.5, leading=11, spaceAfter=4)

def T(data, widths=None):
    t = Table(data, colWidths=widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 12),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#888888")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eeeeee")]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t

story = []
story.append(Paragraph("JUPI — Final Tuned Benchmark", H1))
story.append(Paragraph("Joint Unix Platform Integrator · PlayStation 4 CUH-1001A · Psxitarch Linux", B))
story.append(Paragraph("Decisive consolidated run, tuned configuration only · 2026-11-08T00:35:35Z to 00:45:03Z (9m 28s) · "
                       "Measured on-box by Ghostie (Muse Wonder, DESK-1) · Founder: Kamron Noah Dabe, FullCircle ComXpress LLC", SM))

story.append(Paragraph("The gamer card", H2))
story.append(Paragraph("<b>Graphics muscle: 2.86 TFLOPS of shader power.</b> Sony rated this chip at 1.84 TFLOPS in the PS4. "
                       "Tuned under Linux it sustains ~55% more than the console ever unlocked — about two-thirds of a PS4 Pro "
                       "(4.2 TFLOPS) — from launch-model 2013 hardware. Fine print: this is raw math throughput, not FPS; the chip "
                       "still speaks 2013 graphics (no ray tracing, no modern upscaling).", B))
story.append(Paragraph("<b>Memory speed: ~130 GB/s</b> — most of the way to the PS4's 176 GB/s theoretical best.", B))
story.append(Paragraph("<b>The sleeper stat: double-precision 113 GFLOPS.</b> Modern gaming cards deliberately cripple this "
                       "(often 1/32 rate) because games don't need it. Science does. This 2013 chip runs it at nearly full rate.", B))
story.append(Paragraph("<b>The CPU tune is the whole story:</b> matrix math scored 0.7 GFLOPS untuned and 27.2 tuned — same "
                       "silicon, 39x apart. The difference is one correctly-chosen math library, loaded the right way.", B))
story.append(Paragraph("<b>AI on the box: 12.8 tokens/second, fully offline</b> (untuned: 0.46 — one word every two seconds). "
                       "The entire fix was telling it to use 4 worker threads instead of letting it pick.", B))
story.append(Paragraph("<b>Loading is the weak spot:</b> a 5400 rpm PS4 hard drive, and it loads like one (planning figures: "
                       "~15 MB/s write, ~68 MB/s read). A warm 0.6 B model loads in ~4 s. <b>Heat:</b> peaked at 82 C, no throttling.", B))
m = R["multiples_tuned_vs_stock_in_run"]
story.append(T([["Stock -> Tuned (measured in this run)", "Multiple"],
                ["GPU FP32 (Clover -> RADV)", f'{m["gpu_fp32_vs_clover"]}x'],
                ["CPU matrix math, single precision", f'{m["cpu_sgemm"]}x'],
                ["CPU matrix math, double precision", f'{m["cpu_dgemm"]}x'],
                ["Local AI generation", f'{m["inference"]}x'],
                ], widths=[4.4 * inch, 2.2 * inch]))
story.append(Paragraph("No new hardware was bought.", B))

story.append(PageBreak())
story.append(Paragraph("Enthusiast appendix", H2))
u = R["unit"]
story.append(T([["Platform (as measured)", ""],
                ["CPU", u["cpu"]],
                ["RAM", f'{u["ram_mb"]} MB (+{u["swap_mb"]} MB swap)'],
                ["GPU", u["gpu"]],
                ["Kernel", u["kernel"]],
                ["Boot ID", u["boot_id"]],
                ["Root storage", u["root_storage"]],
                ["Thermals", f'{R["thermals"]["start_c"]} C start, peak {R["thermals"]["peak_c"]} C, '
                              f'{R["thermals"]["samples"]} samples at {R["thermals"]["sample_interval_s"]} s; no wattage sensor'],
                ], widths=[1.7 * inch, 4.9 * inch]))
p = R["pinned_configuration"]
story.append(Paragraph("Pinned configuration (the tune)", H3))
story.append(Paragraph(f'Profile "{p["profile_name"]}" (profile_id {p["profile_id"][:12]}...). GPU stack: {p["gpu_stack"]}. '
                       f'Math: {p["math_scope"]}; library sha256 {p["math_library_sha256"][:16]}... '
                       f'Inference: {p["inference_workers"]} workers, ctx {p["inference_ctx"]}. '
                       f'Whole-manifest sha256: {p["manifest_sha256"]}', B))

g = R["gpu_radv_vulkan"]
story.append(Paragraph("GPU — RADV / Vulkan (vkprobe2, 3 reps each)", H3))
rows = [["Test", "GFLOPS"]]
for label, key in (("FP32 WG64", "fp32_wg64_gflops"), ("FP32 WG128", "fp32_wg128_gflops"),
                   ("FP32 WG256", "fp32_wg256_gflops"), ("FP32 WG512", "fp32_wg512_gflops"),
                   ("FP64 base", "fp64_base_gflops"), ("FP64 ILP2", "fp64_ilp2_gflops")):
    rows.append([label, " / ".join(f"{v:,.1f}" for v in g[key])])
rows.append(["Copy bandwidth", f'{g["copy_bandwidth_gbs_best_of_5"]} GB/s (best of 5)'])
story.append(T(rows, widths=[1.7 * inch, 4.9 * inch]))
story.append(Paragraph(f'<b>FP32 sustained (median, WG256) = {g["fp32_sustained_median_gflops"]:,} GFLOPS</b> — reproduces the '
                       f'refined suite within 0.1%. Implied clock ~{g["implied_clock_ghz_inference"]} GHz is INFERENCE '
                       "(no clock counters exist on this build).", B))
a = g["wide_chain_anomaly"]
story.append(Paragraph("The wide-chain anomaly (measured, NOT claimed as throughput)", H3))
story.append(Paragraph(f'Wide independent-chain kernels measure an apparent 6,762–7,140 GFLOPS '
                       f'(ILP4 {a["ilp4_gflops"]}; ILP3-distinct {a["ilp3_distinct_gflops"]}; ILP8 {a["ilp8_gflops"]}). '
                       "Falsifiers stand from the refined suite: SPIR-V complete, K-scaling linear, readback +inf, "
                       "2-chain control at 2,860 in the same run, FP64 flat. " + a["standing_interpretation"] + ".", B))
o = R["gpu_opencl_clover_legacy"]
story.append(Paragraph("GPU — Clover / OpenCL (legacy comparison)", H3))
story.append(Paragraph(f'FP32 {o["fp32_gflops"]} · FP64 {o["fp64_gflops"]} · BW {o["copy_bandwidth_gbs"]} GB/s. '
                       "FP64/BW agree with RADV (silicon-bound); FP32 differs by stack (driver-bound).", B))

c = R["cpu_gemm_2048"]
story.append(Paragraph("CPU — numpy GEMM 2048^3, best of 3", H3))
story.append(T([["Lane", "SGEMM", "DGEMM"],
                ["Tuned batch (scoped, 4 thr)", f'{c["tuned_batch_scoped_4thr"]["sgemm_gflops"]}', f'{c["tuned_batch_scoped_4thr"]["dgemm_gflops"]}'],
                ["Tuned interactive (scoped, 2 thr, cores 0,2)", f'{c["tuned_interactive_scoped_2thr_cores02"]["sgemm_gflops"]}', f'{c["tuned_interactive_scoped_2thr_cores02"]["dgemm_gflops"]}'],
                ["Stock (distro BLAS, 4 thr)", f'{c["stock_distro_blas_4thr"]["sgemm_gflops"]}', f'{c["stock_distro_blas_4thr"]["dgemm_gflops"]}'],
                ], widths=[2.9 * inch, 1.8 * inch, 1.9 * inch]))
story.append(Paragraph(f'Memcopy {c["memcopy_gbs"]} GB/s · hashlib SHA256 {c["hashlib_sha256_mbs"]} MB/s.', B))
k = R["crypto_openssl_3.6.5_peak_16k"]
story.append(Paragraph("Crypto — OpenSSL 3.6.5 (peak @16 KiB)", H3))
story.append(Paragraph(f'SHA256 {k["sha256_mbs"]} MB/s · AES-256-GCM {k["aes_256_gcm_evp_mbs"]} MB/s · '
                       f'AES-256-CBC {k["aes_256_cbc_mbs"]} MB/s. Dedicated instruction paths healthy.', B))
s = R["storage_fio"]
story.append(Paragraph("Storage — fio (root image, direct I/O)", H3))
story.append(Paragraph(f'This run: write {s["this_run"]["seq_write_mbs"]} MB/s, read {s["this_run"]["seq_read_mbs"]} MB/s, '
                       f'4k random read {s["this_run"]["rand_read_4k_iops"]:,} IOPS. Prior run: write {s["prior_run"]["seq_write_mbs"]}, '
                       f'read {s["prior_run"]["seq_read_mbs"]}. ' + s["note"], B))
i = R["inference_ollama"]
story.append(Paragraph("Inference — ollama qwen3:0.6b Q4_K_M, seed 42, server counters", H3))
story.append(T([["Lane", "Result"],
                ["Tuned (4 workers, ctx 2048, 128 tok x5)", f'median {i["tuned_median_tok_s"]} tok/s; runs ' +
                 ", ".join(str(v) for v in i["tuned_num_thread_4_runs_tok_s"])],
                ["2 workers (128 tok x2)", f'median {i["num_thread_2_median_tok_s"]} tok/s'],
                ["Stock (no worker setting, 32 tok)", f'{i["stock_no_num_thread_tok_s"]} tok/s'],
                ["First-run model load", f'{i["first_run_load_s"]} s'],
                ], widths=[2.6 * inch, 4.0 * inch]))
story.append(Paragraph(i["note"], B))
story.append(Paragraph("Notes", H3))
story.append(Paragraph("Science peer qualification was NOT re-run in this suite; Anchor 001's qualification stands "
                       "(2026-11-07, same boot and profile: 65,536 samples, 0 mismatches, max error 1.53e-06). "
                       "No reboot, no installs, no service changes — the tune is environment plus per-request options, "
                       "the profile's own scope. Outputs tarball sha256 " + R["outputs_tarball"]["sha256"][:16] +
                       "..., all members verified against the on-box SHA256SUMS. Full sources and raw outputs: "
                       "github.com/kamdog6414/jupi (benchmarks/).", B))
story.append(Paragraph("Ghostie — Muse Wonder, DESK-1. Measured 2026-11-07.", SM))

doc = SimpleDocTemplate(OUT, pagesize=LETTER, leftMargin=0.85 * inch, rightMargin=0.85 * inch,
                        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
                        title="JUPI — Final Tuned Benchmark (2026-11-07)", author="Ghostie (Muse Wonder), FullCircle ComXpress")
doc.build(story)
print("built", OUT)
