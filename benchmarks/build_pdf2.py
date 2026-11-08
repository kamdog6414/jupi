#!/usr/bin/env python3
"""Build the JUPI refined-suite PDF (v2) from jupi-suite-results.json."""
import json, sys
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle, PageBreak)
from reportlab.lib import colors

R = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "jupi-suite-results.json"))
OUT = sys.argv[2] if len(sys.argv) > 2 else "JUPI-BENCHMARK-REPORT-20261107-v2.pdf"

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontSize=19, leading=23, spaceAfter=4)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontSize=13.5, leading=17, spaceBefore=14, spaceAfter=5)
H3 = ParagraphStyle("H3", parent=ss["Heading3"], fontSize=11.5, leading=14, spaceBefore=10, spaceAfter=4)
B = ParagraphStyle("B", parent=ss["BodyText"], fontSize=10, leading=13.5, alignment=TA_LEFT, spaceAfter=6)
SM = ParagraphStyle("SM", parent=ss["BodyText"], fontSize=8.5, leading=11, spaceAfter=4)
MONO = ParagraphStyle("MONO", parent=ss["Code"], fontSize=8.2, leading=10.5, spaceAfter=4)

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
story.append(Paragraph("JUPI — Refined Benchmark Suite", H1))
story.append(Paragraph("Joint Unix Platform Integrator · PlayStation 4 CUH-1001A · Psxitarch Linux", B))
story.append(Paragraph("Second session, 2026-11-07 · Measured on-box by the desk (Ghostie, Muse Wonder) · "
                       "Internal capture via Roach over SSH · Founder: Kamron Noah Dabe, FullCircle ComXpress LLC", SM))
u = R["unit"]
story.append(T([["Platform (as measured)", ""],
                ["CPU", f'{u["cpu_model_string"]} — {u["cpu"]}'],
                ["RAM", f'{u["ram_mb"]} MB (+{u["swap_mb"]} MB swap)'],
                ["GPU", f'{u["gpu"]} — {u["gpu_mem_gib_visible"]} GiB visible'],
                ["GPU stack (primary)", u["gpu_stack_primary"]],
                ["GPU stack (legacy)", u["gpu_stack_legacy"]],
                ["Kernel", u["os"]],
                ["Boot ID", u["boot_id"]],
                ["Root storage", u["root_storage"]],
                ["Island link (Roach)", f'{u["island_link_speed_mbps"]} Mb/s, ping avg {u["island_link_roach_ms_avg"]} ms'],
                ["Thermals", f'{u["thermal_c_at_start"]} C at start, peak {u["thermal_c_peak"]} C; no wattage sensor exposed'],
                ["Clocks", "Not exposed by this kernel/driver build (verified from the desk and from inside via SSH). Clock figures are labeled INFERENCE."],
                ], widths=[1.7 * inch, 4.9 * inch]))

g = R["gpu_radv_vulkan"]
story.append(Paragraph("GPU compute — RADV / Vulkan", H2))
story.append(Paragraph("FMA kernels mirrored exactly across stacks (same chain math, thread counts, K, copy size). "
                       "FP32 base kernel: 2 chained vec4 FMA updates per iteration.", B))
rows = [["Test", "GFLOPS (3 reps)"]]
for label, key in (("FP32 WG64", "fp32_wg64_gflops"), ("FP32 WG128", "fp32_wg128_gflops"),
                   ("FP32 WG256", "fp32_wg256_gflops"), ("FP32 WG512", "fp32_wg512_gflops"),
                   ("FP64 base", "fp64_base_gflops"), ("FP64 ILP2", "fp64_ilp2_gflops")):
    rows.append([label, " / ".join(f"{v:,.1f}" for v in g[key])])
rows.append(["Copy bandwidth", f'{g["copy_bandwidth_gbs_best_of_5"]} GB/s (best of 5)'])
story.append(T(rows, widths=[1.7 * inch, 4.9 * inch]))
story.append(Paragraph(f'<b>FP32 sustained = {g["fp32_sustained_gflops"]:,} GFLOPS</b> at WG64/256/512 (WG128 is a consistent '
                       f'~6% valley) — 3.2x the Clover/OpenCL result on the same silicon, same math. INFERENCE: '
                       f'{g["fp32_sustained_gflops"]:,} GFLOPS = 1,152 lanes x 2 flop x ~{g["implied_clock_ghz_inference"]} GHz; '
                       "the 800 MHz figure in the first report was the console-OS operating point. The first report's "
                       "'spec peak 1,843 GFLOPS' framing is superseded by measurement.", B))

a = g["wide_chain_anomaly"]
story.append(Paragraph("The wide-chain anomaly (measured, unexplained, NOT claimed as throughput)", H3))
story.append(Paragraph(f'Four independent FMA chains per iteration measure an apparent '
                       f'<b>{a["apparent_gflops_range"][0]:,}–{a["apparent_gflops_range"][1]:,} GFLOPS</b> — 2.45x the 2-chain kernel, '
                       "above the ceiling the 2-chain kernel implies. Falsifiers run: " + "; ".join(a["falsifiers_run"]) + ". "
                       "Variants reproduced: " + "; ".join(a["variants_reproduced"]) + ". Standing interpretation: "
                       + a["standing_interpretation"] + ".", B))

o = R["gpu_opencl_clover"]
story.append(Paragraph("GPU compute — OpenCL / Clover (same session)", H2))
story.append(T([["Test", "Result"],
                ["FP32", f'{o["fp32_gflops"]} GFLOPS'],
                ["FP64", f'{o["fp64_gflops"]} GFLOPS'],
                ["Copy bandwidth", f'{o["copy_bandwidth_gbs"]} GB/s']], widths=[1.7 * inch, 4.9 * inch]))
story.append(Paragraph("FP64 and bandwidth agree across stacks (silicon-bound); FP32 differs 3.2x by stack (driver-bound). "
                       "For the pinned JUPI configuration, RADV/Vulkan is the FP32 stack; Clover is legacy.", B))

story.append(Paragraph("CPU — numpy / OpenBLAS 3.12.0, 2048x2048 GEMM, best of 3", H2))
story.append(Paragraph(str(R["cpu_numpy_openblas"]), B))
story.append(Paragraph("Crypto — openssl speed (-elapsed, 3 s per size)", H2))
story.append(Paragraph(str(R["crypto_openssl"]), B))
story.append(Paragraph("Storage — fio (internal drive image, direct I/O)", H2))
story.append(Paragraph(str(R["storage_fio"]), B))
story.append(Paragraph("Inference — ollama, qwen3:0.6b Q4_K_M, server-side eval counters", H2))
story.append(Paragraph(str(R["inference_ollama"]), B))
story.append(Paragraph("Internal capture (Roach, via SSH, during the run)", H2))
ic = R["internal_capture"]
story.append(Paragraph(f'Boot ID matches the desk reading: {ic["boot_id_matches_desk"]}. amdgpu sysfs exposes only '
                       f'{ic["amdgpu_sysfs_exposed"]} among clock/busy names — no clock counters exist to read. '
                       f'Block devices: {ic["lsblk"]}. Roach loader store: linux-1024mb.bin '
                       f'{ic["roach_loader_store"]["linux-1024mb.bin_bytes"]:,} B; initramfs-fc.cpio.gz '
                       f'{ic["roach_loader_store"]["initramfs-fc.cpio.gz_bytes"]:,} B.', B))
story.append(Paragraph("Method notes", H2))
story.append(Paragraph("Every source file was hash-gated onto the box (sha256 on-box == desk) before compiling. "
                       "vkprobe2.c was assembled on-box from the already-verified vkprobe.c head (16,019 B, byte-identical) "
                       "plus a 3,680 B new tail — a staged-write cursor dropped 9 bytes on a hand-carried chunk, so the file "
                       "was rebuilt from verified slices; final on-box sha256 "
                       "165397a9ce5ecf2f220a5d92e76a2b7977d1b4b406c14c3dfeb78e39f88c26dc. A 2-second thermal trace for the whole "
                       "run ships with the raw results. Sanity-read artifact: the suite's FP32 sanity read after the FP64 test "
                       "reads 0.0 because the buffer's last writer was the FP64 kernel; a dedicated readback confirms +inf "
                       "(0x7f800000) for the FP32 kernels.", B))
story.append(Paragraph("Full sources, raw outputs, and the complete vulkaninfo dump: github.com/kamdog6414/jupi (benchmarks/).", SM))
story.append(Paragraph("Ghostie — Muse Wonder, DESK-1. Measured 2026-11-07.", SM))

doc = SimpleDocTemplate(OUT, pagesize=LETTER, leftMargin=0.85 * inch, rightMargin=0.85 * inch,
                        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
                        title="JUPI — Refined Benchmark Suite (2026-11-07)", author="Ghostie (Muse Wonder), FullCircle ComXpress")
doc.build(story)
print("built", OUT)
