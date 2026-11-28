# RESULT: stock MUL_MAT sweep on JUPI 1, Nov 22 2026 (PST). CRASH WITH EVIDENCE.
Kam GO for the reboot: 1:28 PM. Seat: Groku.2 (executor). Patched sweep NOT re-run.

## Reboot: LANDED
- reboot command sent 1:28:49 PM; Kam started the loader; SSH back 1:34:10 PM
- old boot_id d3b30481…; new boot is clean
- 0 ring timeouts in dmesg; Xorg and xfwm4 up; swap 0 MiB; MemAvailable 6110 MiB
- system ICD is stock: /usr/lib/libvulkan_radeon.so, sha acf91948…

## Stock sweep: HUNG (same failure as the patched 8:35 AM hang)
- System RADV, no VK_ICD_FILENAMES. 1:34:39 PM start. Chunks of 40. Log fsynced after every chunk; CURRENT.txt holds the case list of the chunk in flight.
- Chunks 1-6 (cases 0-208) finished. Their DeviceLost/core-dump aborts did not touch the kernel rings.
- At 1:38:38 PM, chunk 7 (cases 179-218) hung compute ring comp_1.1.0 in test-backend-op pid 3866. The GPU reset failed ("asic atom init failed", "GPU Recovery Failed: 1"). The gfx ring (Xorg), sdma0 and the rest then timed out in turn.
- This is the same ring and the same failed-reset pattern as the patched sweep at 8:35 AM.
- Hung chunk = HUNG-CHUNK7-cases.txt. In order: q3_K m16 n1/n8 k4096; q4_K, q5_K and q6_K at n1..9 k256 and n1/n8 k4096; tq2_0 n1..5 k256. The single case was not isolated, because isolating it needs another hang and another reboot.
- The guard (root pid read from root.pid; no pkill -f) stopped at 1:38:40 PM on bad_new=2. Swap stayed 0 MiB.
- No reboot was done. The GPU is down again until Kam decides.

## Verdict
The hang is NOT caused by FC-NODS128. Stock gfx7 RADV 21.3.2 on JUPI 1 hangs a compute ring inside this MUL_MAT sweep, and the kernel cannot reset the Liverpool GPU after that. The patch is cleared of this crash. A full op sweep is unsafe on JUPI 1 with either driver.
Not run: the stock ub1 llama-bench re-run. It was gated on the stock sweep passing, and the GPU is hung.
