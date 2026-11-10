# JUPI life timeline

> Public edition, generated from the JUPI as-built scan of 2026-11-10 8:10 AM PST (sha256 `3559b934…`). LAN/tailnet addresses, key paths and full fingerprints are redacted to role placeholders. Times are PST. Full typeset version: [`field-manual/JUPI-Field-Manual.pdf`](field-manual/JUPI-Field-Manual.pdf).

## 9. Life timeline

All times PST. **Source key:** `D` = Roach diagnostics `~/ps4-linux/diagnostics`, `R` = JUPI
receipts/backups (file times read in GMT and converted), `J` = JUPI journal (holds Nov 9 7:54 AM
onward only), `G` = groku-wire records, `H` = git history, `C` = rescue checkpoints.

### Thu Nov 5: from a dark console to a desktop

| Time | Event | Src |
|---|---|---|
| 3:46 PM | Sony UFS2 top-level directories created on the internal HDD (console storage initialized) | R |
| ~6:01–6:50 PM | USB stick prepared on real clock (`/root/.ssh`, `initramfs.original`, 2.2 GB `psxitarch-live.tar.gz`) | R |
| (1970 clock) | `fc.sh` boot, `/ps4hss` typo plus the 4 s device race → **rescue shell**. CP01–CP03 written by hand | C |
| 7:46 PM | Roach diagnosis: Ethernet `NO-CARRIER`, PS4 not reached | D |
| 11:32 PM | First payload send refused (port not listening yet) | D |
| **11:45:46 PM** | `linux-1024mb.bin` (329,088 B) accepted by the PS4 payload port | D |
| 11:46–11:47 PM | Ethernet carrier drops and returns; OpenSSH 10.6 answers; host key `awkaTxgG…` first seen | D |
| **11:55 PM** | Kam confirms the XFCE desktop on the PS4 screen | D |

### Fri Nov 6: three roots in one day

| Time | Event | Src |
|---|---|---|
| 12:29 AM | SSH preflight: `psxita` and `root` refused (keys only); `pi` is the working account | D |
| **12:34 AM** | Root verified: `loop0` ← `/ps4hdd/home/linux.img` (stock 50 GiB) on UFS2 | D |
| 12:41 AM | Autostart + Wi-Fi configured: kernel/initramfs/payload copied to `/data`, payload AutoRun | D |
| ≤ 1:02 PM | USB selector fails on `[ -x /newroot/sbin/init }`. Manual `switch_root` to USB `sda2` (reported) | C |
| 1:02 PM | **CP04**: first desktop on the USB root; Roach SSH as `pi` passes | R |
| 1:06–1:25 PM | **CP05**: one-byte selector repair (`}` → `]`), 10/10 tests, three rollback copies, restart test | R |
| ~1:21 PM | Boot `b00c61e1`: USB root comes up on its own | R |
| 1:33–2:37 PM | "Computer gates": GPU compat libs (LLVM 13), Firefox 159, official ChatGPT/Codex desktop app | R |
| 2:01 PM | Handoff: Roach seat → NIKOLAI seat | R |
| 5:15 PM | JUPI platform installed on the USB root (units, firewall, sshd hardening, `installation.json`) | R |
| **~8:48 PM** | Boot `54f4c94e`: **first boot on the JUPI image** (40 GiB, UUID `70dbf870…`) | R |
| 9:02 PM | Disk-only boot bundle backed up (bzImage, both initramfs, selector `usbroot.after.sh`) | R |
| 9:13 PM | Disk-only selector activated (`initramfs` `cdeaefdb…` on the HDD copy) | R |
| 9:16 PM | Root grown online **40 → 355 GiB** | R |
| 9:17 PM | USB swap retired. 2 GiB `jupi-zram` takes over | R |
| 9:19–9:53 PM | Toolbox, rootless containers, OpenCL (clang/libclc 13) installed with receipts | R |
| 10:35 PM | Cluster enrollment by Ghostie: FC-Link, xchain, Agape, CastorLTE (first authored row #281) | R |

### Sat Nov 7: qualification day

| Time | Event | Src |
|---|---|---|
| 5:49–8:53 AM | Observability, science, creative and instrument config, each with a checkpoint pushed to Roach | R |
| 11:42 AM | Native warm-boot (kexec) candidate staged, later **held** for missing early GPU firmware | R |
| 11:56 AM | Supervised userspace soft-reboot: SoftRebootsCount 0 → 1, same kernel, state preserved | R |
| 4:35–4:51 PM | Benchmark suite; commit `6641144` claims 2.86 TFLOPS | H |
| **11:15:16 PM** | Kernel reboot → boot **`5c74d073`** (current). Cause not recorded | R |
| 11:49–11:51 PM | `jupi-pipeline-bench` replaces the inflated figure; Ghostie display keeper and no-DPMS installed | R |

### Sun Nov 8 – Mon Nov 9

| Time | Event | Src |
|---|---|---|
| Nov 8 7:15–8:02 AM | Host watch, UMA bench, rover quality, mission runner added | R |
| Nov 9 7:54 AM | Oldest entry still in the journal (rotation at 128 MiB) | J |
| Nov 9 8:39–9:25 AM | Computing lab + knowledge archive (`jupi-knowledge` timer) | R |
| Nov 9 9:52 AM | Display keeper reordered: zero timeouts first, `-dpms` last | R |
| Nov 9 9:32 PM | Commit `38277a9`: "JUPI caught its own lie" (perf gates) | H |

### Tue Nov 10: the freeze

| Time | Event | Src |
|---|---|---|
| 5:28–5:49 AM | Groku read-only probes 1–3 | G |
| 5:53 AM | Backups taken; step 1a: zram1, sysctl 90-groku, OOM drop-ins (daemon-reload times out under pressure) | G |
| 6:15 AM | Step 1b: zram1 actually started (4 GiB swap total) | G |
| 6:25 AM | Step 1c: earlyoom 1.9.0 installed and armed | G J |
| ~6:2x AM | MemAvailable ~190 MB, swap 4024/4095, **GTT 3,615,711,232 / 3,618,242,560** | G |
| 7:02–7:17 AM | 37 fresh SSH attempts from Roach fail (timeouts, resets in key exchange); ping OK | G |
| 7:31–7:36 AM | Grok Bot app killed. No relief (107 MB available) | G |
| 7:46 AM | A login gets through | J |
| **7:47:03 AM** | `sudo systemctl restart lightdm` (pi, Ghostie's session) | J |
| 7:47:28 / 7:47:46 | lightdm stopped ("3.4G memory swap peak") / started | J |
| 7:49:27 AM | Autologin session for pi | G |
| 7:50:01 AM | MemAvailable 4343 MB, swap 183 MB. GTT 31 MiB at 7:50:18 | G |
| 7:50:17–7:51:11 AM | Kernel: `amdgpu: GPU reset(20/21) failed`, `asic atom init failed`, DP link training failures (uptime-derived times) | R |
| 7:51:09 AM | HDMI re-handshake: `HANDSHAKE_OK`, 1920×1080@60 primary | G |
| 8:09 AM | Watch: `.xsession-errors` +5.49 MB / 30 s from ChatGPT GPU process | G |
| 8:10 AM | As-built scan `JUPI-ASBUILT-SCAN-20261110T1610Z` | G |
| 8:24 AM | Spot check for this manual: 3111 MB available, GTT 30 MiB, `.xsession-errors` 357.6 MB | — |

Boots not listed above (e.g. after the 12:41 AM autostart work) have **UNKNOWN** IDs. The journal
that would have named them has rotated.
