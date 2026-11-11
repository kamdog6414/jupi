# JUPI 2 (PS4 Pro)

| File | What it is |
|---|---|
| [BENCHMARKS.md](BENCHMARKS.md) | Full benchmark tables as text: three runs (rescue chroot, desktop, post-disk-boot), thread sweep with efficiency, Amdahl fit parameters, size sweep, combined, flash-attention, sustained soak, OpenSSL, Python copy, O_DIRECT disk with raw `dd` lines, implied weight traffic, timestamped thermal milestones, local LLM server latency, GPU probe details and the Vulkan build attempt, what is unmeasured, reproduce commands |
| [RESCUE-SHELL.md](RESCUE-SHELL.md) | How Linux got onto the Pro: boot files and sizes, the five PayLoader sends, exFAT to FAT32, rescue-shell inventory, why it held at `HOLD_NO_USB`, the additive Pro selector, the 128 GiB root image, the `switch_root` gotcha, normal boot procedure, services |
| [JUPI2-FINAL-20261111.pdf](JUPI2-FINAL-20261111.pdf) | Final public study, 15 pages, black and white. Opens with a PS3 20th-anniversary page (PS3 launched in Japan on 11 Nov 2006). CPU inference benchmarks on a PS4 Pro (llama.cpp, Qwen3-0.6B Q4_K_M: 27.98 ± 0.16 tok/s generation at 8 threads, 87.70 ± 0.13 tok/s prompt, 1.48× JUPI at 4 threads), Amdahl thread-scaling fits, memory bandwidth, thermals, disk, seven-environment comparison, mutual-serving roadmap, threats to validity, hypotheses, and reproduce-it commands. GPU tok/s is unmeasured and the $60 price is unverified; both are labeled in the paper. |

sha256 `fc32ebc7d0ccb31792a2e02a31e42eacd144f9c704377d9b510f40f73b5e50f1`
