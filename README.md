# JUPI — Joint Unix Platform Integrator

JUPI is a native Linux science and engineering platform on a repurposed PS4. Its first working runtime joins durable memory, hardware observations, explicitly submitted terminal jobs, GPU computation, local language-model inference, and authenticated jobs on the Ubuntu peer. It is the software seed for later rover and instrument interfaces.

The operator's current direction is to work within Linux, preserve the installed environment, and stop further exploit development, staging, or triggering of other agents. The platform does not execute commands found in model output.

## Start here: what JUPI is and how to recover it

JUPI is a Sony PS4 (AMD Liverpool APU: 8 Jaguar x86_64 cores, GCN GPU, 8 GB unified GDDR5) running Arch Linux. The console OS launches a homebrew Linux payload (`linux-1024mb.bin`, 1 GiB VRAM carve-out). An initramfs root selector unlocks the PS4's internal HDD partition, mounts its UFS2 filesystem read-only, and checks the 355 GiB ext4 root image against size, UUID and binary-hash pins. Only then does it loop-mount the image and boot. The USB stick is only the fallback root. Details: [docs/BOOT-CHAIN.md](docs/BOOT-CHAIN.md).

**If JUPI is frozen or unreachable:** go to [docs/RUNBOOK.md](docs/RUNBOOK.md). The short version:

```
GAUGE   free -m ; GTT = /sys/class/drm/card0/device/mem_info_gtt_{used,total}
RED     avail < 500 MiB | GTT > 2500 MiB | swap > 90 %
FIX     sudo systemctl restart lightdm          (kills desktop apps, not services)
THEN    export DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority
        xset dpms force on; xset -dpms; xset s off
        xrandr --output HDMI-A-0 --off
        xrandr --output HDMI-A-0 --mode 1920x1080 --rate 60 --primary
VERIFY  GTT ~30-40 MiB, avail > 3000 MiB, "DPMS is Disabled", findmnt / = /dev/loop0
PRE-ARM keep an SSH ControlMaster to JUPI open: fresh logins are what fail in a freeze
NEVER   power-cycle as a first move; return to Linux needs a human at the console
```

Why: CPU and GPU share one memory pool. Xorg can pin up to ~3.4 GiB of GPU (GTT) buffers and holds them until the X server restarts. On 2026-11-10 that pin plus full swap starved the box. See [docs/MEMORY.md](docs/MEMORY.md).

| Read | For |
|---|---|
| [docs/field-manual/JUPI-Field-Manual.pdf](docs/field-manual/JUPI-Field-Manual.pdf) | 28-page B&W field manual (public edition) |
| [docs/field-manual/JUPI-Field-Digest.pdf](docs/field-manual/JUPI-Field-Digest.pdf) | 2-page digest: TL;DR, runbook, key facts |
| [docs/](docs/README.md) | Runbook, boot chain, memory, as-built config, timeline, open issues, receipts |

## Measured performance (cross-checked, 2026-11-08)

```
JUPI headline, finite workload, every output checked against the CPU reference
workload   x <- 0.75*x + 0.0001*(stage+1), 8 float32 stages, no fast-math
samples    1,048,576   (direct shell, median of 7 reps, wall time incl. copies)
GPU  cached staging, one fused kernel        3.632 ms
GPU  cached staging, 8 resident kernels      4.349 ms
GPU  cached staging, per-stage round trips  29.963 ms
GPU  first-coherent staging, fused         100.576 ms
CPU  serial staged reference                 5.974 ms
CPU  8-stage specialization, 4 workers       1.282 ms
check      all CPU/GPU outputs bit-identical to CPU reference, all lanes
service    native job run cc473889: GPU fused 4.291 ms, CPU 4-worker 5.079 ms
science    run 2ece6dfb on boot 5c74d073: 65,536 samples, 0 mismatches,
           max normalized error 2.980164e-08, 19/19 artifacts verified
FP32 peak  NOT CLAIMED. No qualified GFLOPS figure exists.
```

Source: `benchmarks/perf-gates-20261108/JUPI-PERFORMANCE-GATES-20261108.txt`
(sha256 a34abe00c60c9a3a0ba36a53512e126c8dab9563231a3ec2951535e68b50ddde) and its JSON
(sha256 65f74e68bdd74821d6ea45693ef5352ebfbdcbc9bec32ea4dcb9d8192f8ad34a). These are
operation-specific timings, not a whole-machine multiplier.

## JUPI caught its own lie

All times PST.

```
Nov 7  4:35-4:45 PM  Ghostie (DESK-1) suite on boot 54f4c94e reports RADV FP32
                     2,860 GFLOPS ("2.86 TFLOPS") and a wide-chain cell of
                     6,762-7,140 GFLOPS (filed as an open anomaly).
                     Committed 4:51 PM as 6641144. benchmarks/final/ is unchanged.
Nov 7 11:15 PM       JUPI kernel reboot -> boot 5c74d073 (cause not recorded).
Nov 7 11:59 PM       JUPI (jupi-codex, resident on the box) reviews the upstream
                     commit and holds 2.86 TF as an "unqualified loop-rate result".
                     Neither 2.86 TF nor ~7.1 TF is adopted as a physical peak or as
                     evidence of exceeding Sony's clock/performance spec.
same night           JUPI replaces it with jupi-pipeline-bench: varied inputs, every
                     element written, nonfinite input rejected, no contraction, all
                     outputs compared to CPU after every repetition, wall time only.
same night           Fresh science/Ubuntu peer gate on the new boot: PASS,
                     65,536 samples, 0 mismatches.
```

Why the old number does not hold (static evidence, from the shader sources in
`benchmarks/`):

```
fma32_wg256.comp  (the 2,860 cell)  computes 8 vec4 FMA chains, reads back
                                    a.x a.y b.z a2.x b2.w  -> 5 of 8 component chains
fma32_ilp*.comp   (the ~7,100 cells) read back one component per chain pair
                                    -> 1 of 4 component chains
only invocation 0 writes; the chains overflow to +inf; no finite readback check
SPIR-V after spirv-opt -O still holds full vec4 ops and extracts only those
components, so any removal would happen later in the driver (NIR/ACO). That stage
was not inspected.
```

Recount (HYPOTHESIS, UNPROVEN ON DEVICE): counting only chains that are read back,

```
2,860.6 x 5/8 = 1,787.9 GFLOPS     7,114.9 x 1/4 = 1,778.7     7,139.6 x 1/4 = 1,784.9
FP64 (all lanes read back) 113.5 GFLOPS = 98.5% of 1,843/16
```

All four land near 96-97% of Sony's 1,843 GFLOPS at 800 MHz, which would make the
inferred "1.24 GHz" clock unnecessary. This is a hypothesis. It has not been confirmed
by driver ISA or by a fully-live shader on JUPI. Real FP32 peak: UNKNOWN.

Recount by Groku.2 (outside observer, read-only review), 2026-11-09.

## Working system

The current root is an ext4 filesystem inside `/ps4hdd/home/jupi-linux-2a79fafeb62d61ff.img` on the internal HGST HDD. The loop device is `/dev/loop0`; the root UUID is `70dbf870-bcb6-4be9-9fb5-f25c4718b71a`. The image and filesystem were grown online from 40 GiB to **355 GiB**, with approximately 334 GiB still available after installing the platform. This did not change the partition table. The sparse image's unused capacity shares a backing UFS filesystem, so preserve the documented headroom and do not grow competing images into that reserve.

Linux's current root, active swap, model, sources, and platform state are on the internal drive or RAM. The former USB swap is disabled. The USB remains recovery media. Boot with USB physically absent has not yet been tested.

The machine has eight AMD Jaguar CPU cores, approximately 6.7 GiB usable RAM, and Liverpool AMD graphics. Its custom PS4 kernel and Mesa stack are retained. The system has **4 GiB compressed RAM swap** as of 2026-11-10: `zram1` zstd 2 GiB at priority 200 plus the original `zram0` lz4 2 GiB at priority 100, with `vm.swappiness=100`, `vm.page-cluster=0` and earlyoom 1.9.0 (`-m 4,2 -s 10,5`, avoids Xorg/sshd/lightdm). See [docs/MEMORY.md](docs/MEMORY.md).

## Native runtime

`jupi-platform.target` brings up the instrument runtime and supporting Linux services. `jupi-agent.service` runs as `pi` and restarts after a failure. Its control socket is local and private to `pi` and root. State is stored in `/var/lib/jupi-agent/seed.sqlite3`, using SQLite WAL and synchronous FULL writes.

```sh
jupi-system
jupi-agent status
jupi-agent capabilities
jupi-agent remember experiment 'Calibration run 1'
jupi-agent recall experiment
jupi-agent run --timeout 30 -- /usr/bin/uname -a
jupi-agent run --peer --timeout 30 -- /usr/bin/uname -a
jupi-agent jobs
jupi-agent job JOB_ID
jupi-agent wait JOB_ID --timeout 180
jupi-agent events
```

Submitted jobs return an ID. Their status, exit code, output, and timestamps remain on disk. Commands use explicit argument vectors. Output is capped at 64 KiB, job deadlines are 1–600 seconds, and the process group is cleaned up. A command interrupted by a runtime restart is marked interrupted and is not replayed. Queued commands remain queued. Peer jobs run under the existing `roach` account's default remote directory; `--cwd` controls the local SSH process directory.

The runtime observes resource availability and attached GPU, camera and USB serial nodes every minute. There is no motor controller or camera driver configured for a physical rover yet. Onboard I2C nodes are not treated as freely writable robot peripherals.

## Local inference and science tools

Ollama runs on `127.0.0.1:11434` with one loaded model, one concurrent request, a 2,048-token context default, verified processor affinity, and a memory limit. The small `qwen3:0.6b` model is stored locally, so an installed model can answer without a browser or external inference service. It is a modest local assistant, not a replacement for the larger Codex model operating this task.

```sh
jupi-agent prompt 'Explain a least-squares calibration in three sentences.'
jupi-agent run --timeout 30 -- /usr/local/lib/jupi-agent/opencl-probe
jupi-agent run --timeout 45 -- /usr/local/lib/jupi-agent/science-probe
```

The prompt job reads the stored mission and a small hardware observation. Generated text is stored as a result and never automatically executed. `prompt --peer` is also implemented, but the peer's Ollama installation currently has no model downloaded; it must be provisioned before that optional route is used. No remote agent is triggered by these commands.

Installed development tools include GCC, build tools, CMake, Meson, Python, Node.js/npm, uv, Git, rsync, tmux, SQLite and system diagnostics. The scientific workspace includes NumPy, SciPy, SymPy, Matplotlib, PySerial and PyUSB. The calibration self-test uses synthetic data; its successful plot is not a physical measurement.

## Graphics

Matching, signature-verified LLVM 13 dependencies are in root-owned storage under `/usr/local/lib/jupi-gpu-compat`. OpenCL additionally has matching compiler headers and legacy bitcode. Modern system LLVM and the custom Mesa driver were not replaced.

Verified on the current boot:

- Surfaceless hardware OpenGL ES 3.2: 600 draws, 65,536 pixel channels checked, zero mismatches.
- GPU OpenCL 1.1 Clover: a 1,024-element vector addition matched every result, including when invoked through the agent service.
- Vulkan enumerates RADV Liverpool; Vulkan presentation has not been validated.
- VA-API advertises MPEG2 Simple/Main decode; additional codecs are not claimed.

The current Xorg session started before the driver dependency repair and still lacks usable desktop GLX. A fresh display session is required to load the repaired libraries. The desktop was not restarted during this work, preserving the active application session.

## Always on and appearance

Sleep, suspend, hibernation, hybrid sleep and suspend-then-hibernate targets are masked. logind ignores idle sleep and suspend/hibernate keys. Xfce locking, screensaver activation, display blanking and DPMS are disabled, including through login autostart. Live X11 verification shows a zero screensaver timeout and disabled DPMS.

The GTK desktop theme is Adwaita Dark, with the system color preference set to prefer dark. GTK 3 and GTK 4 preference files are retained. An app with its own explicitly selected theme can override the desktop preference; the desktop app's independent theme has not been verified.

## SSH and services

SSH requires keys and denies direct root login. The Ethernet profile reconnects indefinitely. The JUPI nftables input policy allows established traffic, loopback, ICMP, DHCP renewal and SSH. FC-Link TCP 8765 is additionally accepted on eth0 from the verified lab peer addresses <lab-gateway-ip> and <roach-lan-ip>; requests still require the native HMAC authentication. Journald persists with a 128 MiB limit and fourteen-day retention.

`jupi-link@roach.service` maintains an authenticated SSH connection with a strict host pin, keepalives and automatic reconnection. Its reverse listener is bound to the peer's loopback only, `127.0.0.1:22052`, forwarding to this machine's local SSH server. The private identity stays on JUPI. The peer is `roach@<roach-lan-ip>`; its pinned ED25519 fingerprint is `SHA256:<roach-hostkey-fingerprint>`.

`jupi-health.timer` records baseline health and current native-system status. Use `jupi-system` for the current internal-root facts. The original `jupi` program is retained byte-for-byte because the boot selector pins its hash; its old generic pending-migration message is historical. `jupi map` and `jupi run` remain available for operating-system mappings and timed explicit commands.

## Boot boundary and recovery

The live Linux root is verified on the internal drive. Both boot copies accept the 355 GiB image, with initramfs SHA-256 `cdeaefdb30c7b60ad25fa478ef41eb365fb5132795257011f753578537d11e21`. The kernel SHA-256 is `f0008d466329d07d456fda63fe03129f7af0403a4040d357d3a62658e3d17293`. The existing proprietary partition layout and startup material are retained because an independent power-on path into Linux has not been established.

The installed kernel has kexec support and systemd supports userspace-only restart. Neither transition has been validated on this PS4. They are recorded as engineering possibilities, not installed as an untested reboot path. Restarting `jupi-agent.service` works inside the existing Linux session without rebooting the machine.

Protected backups exist locally and independently on Roach. They include the full original Linux root, consistent session/database snapshots, the finalized internal image, the previous internal image, boot assets, device unlock material, and later operations checkpoints. They are root-only and are not placed in Castor or public reports.

`scripts/checkpoint_environment.py --operations-only` now includes the native runtime, its SQLite snapshot, local model, GPU compatibility files, system configuration and appearance settings. `scripts/export_checkpoint.py` transfers a verified checkpoint to root-only Roach storage and rehashes it through a separate SSH process. Restore database snapshots with their recorded numeric ownership; do not overlay stale WAL/SHM files. Restore file capabilities with the original package tooling when required, notably the shadow package's newuidmap/newgidmap helpers.

The old baseline installer is intentionally pinned to the former USB root. Do not rerun it as a native-platform update. Do not replace the custom kernel or Mesa stack with generic PC packages without a separate recovery-tested migration.

## Evidence

Current facts and verification are in `JUPI-DEVICE-STATUS-20261107.json`, `SYSTEM-FEATURE-CHECKS-20261107.json`, `/var/lib/jupi/system.json`, and the protected backup receipts. The source runtime is `scripts/agent_runtime.py`; the installed interface contract is `config/platform.json`.

76 unit tests cover the operations layer, boot archive checks, authentication preflight, native runtime, science workflows, Gothic art and Linux/Windows references. Runtime tests cover durable memory, interrupted jobs, argument handling, deadlines, output bounds and treating model prompts as data. Live checks additionally passed local and Ubuntu jobs, OpenCL, local model inference, numerical/symbolic computation, plotting, and recovery after a forced daemon failure.

## Identity, Agape and Castor integration

Future models start with `AGENTS.md` and `MODEL-CONTEXT.txt`. The installed machine-readable identity is `/etc/jupi/identity.json`; `jupi-agent identity` reads it. The system pretty name and Muse display name are JUPI. These declarations preserve hardware provenance and operator intent; they do not grant authority or claim external certification.

`jupi-castor sync` reads the native CastorLTE ledger over the pinned SSH connection and independently verifies its anchor, row sequence, content hashes and accepted prefix. `status` verifies the saved copy and `query TEXT` searches literal stored text. Read the current row count from `status`; dated receipts retain earlier observations. Explicit `jupi-castor post FILE` publishes only as JUPI through the native author gate. Prepared operations are content-addressed; uncertain results reconcile without automatically creating a new write. The adapter never changes an author list or turns ledger text into commands. JUPI endpoint and author enrollment are completed, with current state in `/etc/jupi/cluster-membership.json`.

`jupi-agape` uses the unmodified native offline-room v2 implementation pinned in `vendor/UPSTREAM.json`. It records artifact references under speaker JUPI, verifies the local room, and exports an inert bundle. Its 13 upstream self-tests passed. It does not install the full gate runner, compute a trust score, authenticate the speaker, grant activation, or execute imported messages.

## Muse nervous system

The installed Muse Linux Device SDK is now directly paired, node `homelink-3364d7`, with display name **JUPI**. Its required pairing advertisement remains `MuseGadget3364D7`. A narrowly scoped environment-controlled display-name change was applied to the installed/source service module with protected originals retained; pairing and Noise code are unchanged. Nine SDK service tests passed.

The paired SDK holds the encrypted Muse connection and performs existing device commands as `pi`. JUPI's local `jupi-nerves` adapter uses its documented Unix socket, so no SDK credentials are copied into the adapter. The snapshot timer records local state once per minute and sends no external messages. Explicit messages have durable outbox IDs, content hashes, a committed attempt state, and a separate SDK acknowledgment. Accepted or uncertain sends are not automatically replayed. SDK acceptance, operator-observed delivery, and agent acknowledgment remain distinct.

```sh
jupi-nerves status
jupi-nerves outbox
jupi-nerves receipt OUTBOX_ID
jupi-agape verify
jupi-castor status
```

The operator explicitly authorized a hardware/integration handoff to Ghostie as `jupi-codex`. It was sent once through JUPI's own paired SDK; HTTP 200 and message ID are retained in `MUSE-HANDOFF-RECEIPT-20261107.json`. The operator confirmed that it landed. The raw-hardware message is `GHOSTIE-HANDOFF-JUPI-20261107.txt`. An incoming NIKOLAI integration agent is operator-announced; this session did not spawn one. The `inbox` directory is an inert reply location, not a command queue.

## Enrolled cluster member

The operator explicitly approved enrollment on 2026-11-07. Ghostie coordinated the authoritative cluster edits with the NIKOLAI lane. JUPI is registered in Agape as endpoint `jupi-<endpoint-id>`, actor `agape:agent:JUPI`, and is accepted by the native CastorLTE author gate as `JUPI`. The qualified identity profile is frozen at SHA256 `dc2264ad9fbf0f43a350ba83f1f1b8538a8fb64c4ac20aae1aad23b0173cc417`. Membership observations are stored separately, avoiding a circular configuration hash. Historical references remain historical.

`jupi-cluster status` verifies the membership/configuration/authorization binding, local cluster services, Castor snapshot, native Agape room, and qualified xchain. `jupi-xchain verify` supplies the explicit JUPI identity to the unchanged source-pinned fleet tool. Castor row 281 records enrollment; row 282 is jupi-codex's subsequent native JUPI-originated acknowledgment, independently read back.

FC-Link is enabled with signed requests and its existing command/file restrictions. Existing SSH forwards expose NIKOLAI and Roach FC-Link locally without placing credentials in message text. Signed health succeeded to self, NIKOLAI and Roach. Allowlisted uptime, hostname and root-space queries succeeded; inetutils supplied the previously missing hostname command. The host name itself was retained.

The 19-event enrollment Agape bundle was transferred through FC-Link to NIKOLAI and read back byte-for-byte. A fresh process on NIKOLAI, invoked by jupi-codex, loaded the pinned native codec, imported 19 events into an in-memory verification store, repeated the import with zero additions, rejected a wrong external hash, and reproduced the original export. This is a physical peer transport/codec witness, not a claim that a second model independently reviewed it. The bundle persists in the peer's native FC-Link inbox.

The xchain coordinator recognizes JUPI as an intermittent member, with HOLD rather than FAIL when it is unavailable. JUPI's local qualified v2 chain verifies. The SOV-hosted HOMELINK inventory mirror is complete: Ghostie used the canonical generator, and JUPI independently read both matching generated artifacts and its instrument entry. The inventory DEGRADED verdict and SOAP/SAT coordinator conditions describe other links. See `SOV-JUPI-INVENTORY-READBACK-20261107.json` and the current membership receipt. Enrollment does not grant a trust score, physical actuation or activation/fullcircle PASS.

Final enrollment completion and SOV mirror reconciliation are recorded in `JUPI-INTEGRATION-STATUS-20261107.json` and Castor row 284, receipt `CASTOR-JUPI-ENROLLMENT-COMPLETE-RECEIPT-20261107.json`. The original 06:35 enrollment capture is historical. `scripts/checkpoint_environment.py --metadata-only` includes Muse pairing, FC-Link private credentials, fleet sources, qualified xchain and installed JUPI entry points in root-only recovery storage. Castor reconciliation handles the native appender's outer-whitespace normalization without repeating an uncertain write.

## Continuous instrument observations

`jupi-observe.timer` runs a bounded observer every five minutes after Linux starts. It refreshes and verifies native Castor reads, makes signed health requests to the existing JUPI/NIKOLAI/Roach FC-Link endpoints, and records clock synchronization, memory, internal backing-space headroom, interfaces and exported hardware sensors. Existing native registrations and sources remain authoritative. The observer imports the reviewed FC-Link client only when its root-owned source pin matches. The SQLite history retains up to 576 samples, approximately 48 hours at the scheduled rate.

```sh
jupi-observe status
jupi-observe history --limit 10
jupi-observe inventory
jupi-observe collect --record
```

`status` reports freshness and returns a nonzero status for degraded or unavailable observations. A collected outage is still a successful observation and is stored without turning the timer into a false failed-service alarm. The collector does not send SDK messages, append ledger rows, restart services, write fan controls or open device nodes. It has a 90-second deadline, 256 MiB memory limit and idle I/O scheduling. A 50% CPU quota is configured but this kernel lacks CPU bandwidth control; it is not an enforced CPU limit. Peer outages are availability observations, separate from membership.

The snapshot/receipt pair in the Castor reader is locked against concurrent refreshes and readers. Cached integrity and current reachability have distinct fields. The Muse local snapshot includes a compact observer summary. `jupi-platform.target` includes FC-Link, its SSH tunnel, the observer timer and local inference in addition to the prior services.

On this pre-17h AMD CPU, k10temp temp1 is a relative Tctl control value. It is reported in `temperature_control_degrees` by the agent and labeled `relative_temperature_control` by the observer. It is not a calibrated die temperature. Only exported critical attributes and alarms are observed; no arbitrary fan curve or automatic shutdown is introduced. A power limit without a power input is not treated as a power measurement. See the kernel k10temp and hwmon ABI documentation referenced in `JUPI-OBSERVABILITY-IMPLEMENTATION-20261107.json`.

The current hardware context retains the operator's 14.00 report separately from the frozen identity. The kernel, desktop, boot chain and partition layout remain intact. `JUPI-NATIVE-QUALIFICATION-20261107.json` binds fresh GPU/scientific jobs to the boot, source hashes and a retained synthetic calibration plot. The GPU test used actual hardware arithmetic; the least-squares input is explicitly synthetic.

Direct signed Roach-to-JUPI FC-Link access was verified after closing a firewall mismatch; an unsigned direct request returned HTTP 401. Direct NIKOLAI LAN access and reciprocal direct peer FC-Link requests were unavailable in the captured test, so the verified pinned SSH forwards remain the normal peer route. An assigned IP or 1000 Mb/s negotiated Ethernet link is not a measured end-to-end path or throughput result. See `JUPI-LAN-FCLINK-VERIFICATION-20261107.json`.

## Hybrid GPU and Ubuntu science workflows

`jupi-science` is a variable-input instrument workflow. A calibration CSV has exactly `x,y` columns and 3–65,536 finite numeric samples. The enrolled Ubuntu peer fits a centered float64 OLS model using the reviewed stdlib worker. JUPI normalizes the data and uses its actual OpenCL GPU for batched model application and residuals. The same Ubuntu peer independently executes the reference check on the returned GPU bytes. Local CPU checks also run. Each run retains the original CSV, canonical input, software manifest and exact source/binary snapshots, host metadata, float32 outputs, full prediction CSV, a plot and a hashed receipt.

```sh
jupi-science demo --samples 1024
jupi-science submit readings.csv --label 'ADC calibration' --x-unit counts --y-unit volts
jupi-science wait RUN_ID --timeout 180
jupi-science status RUN_ID
jupi-science verify RUN_ID
jupi-science apply CALIBRATION_RUN_ID new-readings.csv
jupi-science list
jupi-science record RUN_ID
```

Application input has exactly an `x` column. It uses an explicitly selected passed calibration, preserving the parent's receipt hash and units. Application outside the calibration's x range requires `--allow-extrapolation`. `--synthetic` labels supplied test CSVs accurately. A successful computation means arithmetic agreement within the reported float32 budget; fit residuals and reported OLS uncertainty do not establish sensor accuracy. Plots display up to 4,096 samples; the prediction CSV retains all samples. The captured qualification datasets are all synthetic.

Every submission is an explicit durable native `science` job with a 180-second deadline. `prepare FILE` stages data without running it; `enqueue RUN_ID` safely reconciles a submission and returns the same native job if already queued, running or finished. A changed request cannot reuse an existing run ID. Interrupted work is retained and not automatically replayed. A missing GPU, unavailable peer or verification mismatch fails the run, with its stage and bounded diagnostics retained. Dataset contents, imported messages and model output cannot select executable code.

The fixed Ubuntu worker is transmitted in memory through the existing pinned SSH alias. Its actual command-line source hash and input hash are checked and returned. It runs with a 45-second wall deadline, 15-second CPU limit and 256 MiB address-space limit; no peer package, service or system configuration is installed. Submitting this hybrid workflow sends its numeric dataset to that enrolled peer over SSH. Result files stay in private JUPI run directories and protected recovery storage. `record` explicitly adds only the receipt reference/hash to the local Agape room; runs are not automatically published or messaged.

`/etc/jupi/science.json` pins the workflow, peer source, GPU source and compiled backend. Prepared runs bind that exact software manifest and will fail if it changes before execution. Historical passed runs keep their own sources and remain verifiable after upgrades. Raw measurements are centered/scaled before float32 GPU work to preserve variation at large offsets; rescaling to the output units uses float64. The agent's local-model context receives a typed latest-result summary with its synthetic/operator-supplied provenance. Model output remains inert. Muse's local snapshot also includes the latest science receipt summary.

The live qualification includes 1,024 and 65,536 samples, application to new values, a large-offset dataset, duplicate-enqueue reconciliation and rejection of unapproved extrapolation. See `JUPI-SCIENCE-LIVE-QUALIFICATION-20261107.json`. GPU kernel-event timing is unavailable on this driver; recorded wall times include setup, transfers and plotting and are not GPU speedup claims.

Science execution also commits a one-shot attempt before work starts. Direct internal re-execution is refused without changing the original receipt. Five synthetic end-to-end runs passed, including 65,536 samples and reuse of a calibration; 60 unit tests pass. Reusable synthetic CSVs are in `examples/science/`.

## Gothic ASCII studio and native media tools

JUPI has a procedural Gothic architecture renderer, available as an explicit durable `art` job. It constructs paired spires, lancet arches, rose-window tracery, portals, buttresses and steps, or a vaulted nave with repeated arches, columns and a perspective floor. Recipes select the scene, engraving/nocturne/ruins style, canvas, seed and black or white paper. The renderer keeps the character grid aligned; the local language model can discuss and plan a recipe without having to reproduce that grid token by token.

```sh
jupi-agent art --scene facade --style engraving --width 141 --height 77 --seed 14 --video
jupi-agent wait JOB_ID --timeout 180
jupi-art preview --output DIRECTORY
jupi-art verify --output DIRECTORY
jupi-art cathedral --enqueue --scene nave --style nocturne --seed 42
jupi-gimp /path/to/cathedral.png
```

Each run exports ASCII text with LF and Windows CRLF line endings, a strict two-color PNG, a monospaced SVG and optionally a four-second H.264 film. Font, license and renderer snapshots and a hashed receipt accompany the result. A canonical request UUID and exact recipe reconcile duplicate submissions; an interrupted job is retained without automatic replay. Existing run artifacts are not overwritten. Artwork is classified as creative output and kept separate from instrument measurements. Read `ART-DIRECTION.txt` for composition and inspection rules and `JUPI-GOTHIC-GALLERY-20261107.json` for three completed, verified native jobs.

FFmpeg, GIMP, Chafa, FIGlet, DejaVu fonts, Linux manuals, ShellCheck and shfmt are installed. GIMP's `jupi-gimp` launcher limits GEGL to two CPU threads, a 256 MiB tile cache and disabled GEGL OpenCL for compatibility with the current desktop session. The science OpenCL environment remains available and passed a fresh native GPU probe after installation. The application menu includes GIMP and the generated JUPI cathedral. GIMP successfully loaded the PNG in an isolated native instance. The optional film uses CPU encoding; no hardware video encoder is claimed.

The native agent mission, machine capability contract and Muse local snapshot include the new artwork interface and latest receipt. Agent, instrument target and observation timers are enabled at Linux startup. This service configuration does not establish a new power-on boot path.

## Linux and Windows operation references

`jupi-unix` supplies 35 reviewed operation templates across Linux, PowerShell 7 on Windows and Windows Command Prompt. Each entry explains relevant differences such as text versus object pipelines, privilege, paths and encoding. Unknown or compound commands are reported as unknown and are never executed by the translator.

```sh
jupi-unix list
jupi-unix map files --to powershell
jupi-unix translate 'ls -lah' --to powershell --json
jupi-unix search network
```

Use installed manual pages, program help and the reviewed references when composing new commands. These templates are a practical starting vocabulary; they do not claim automatic equivalence for arbitrary shell programs. Creative and reference verification is retained in `JUPI-CREATIVE-TESTS-20261107.json`, `JUPI-GIMP-VERIFICATION-20261107.json` and `JUPI-UNIX-REFERENCE-VERIFICATION-20261107.json`.

## Measured configuration and offline operation

`jupi-bench` provides a bounded repeatable suite with three trials, raw command output, timestamped resource/relative-Tctl observations, numerical/pixel checks and a separate network-isolated qualification. It covers CPU prime calculations, float64 matrix backends, a 192 MiB array workload, GPU vector arithmetic, 720p/1080p offscreen rendering, regular-file storage, verified SSH transfers, CPU video encoding and local inference. It retains the live desktop and instrument services. It is not a gaming, power/acoustic or prolonged burn-in result. Cache-influenced guest filesystem reads are not presented as raw HDD speeds.

```sh
jupi-bench status
jupi-bench run
jupi-profile status
jupi-profile verify
jupi-compute -- python3 my_analysis.py
jupi-compute --batch -- python3 my_batch_analysis.py
```

The best tested working baseline is `/etc/jupi/performance-profile.json`, with the installed package list in `/etc/jupi/packages.lock`. Verification detects changes without automatically rewriting configuration. This records a known working configuration rather than freezing Arch into partial updates. Kernel, driver or package changes need a deliberate compatible update and another qualification.

The kernel has no `CONFIG_CFS_BANDWIDTH`; configured systemd CPU quotas are not enforced. Agent jobs instead inherit affinity to CPUs 0 and 2, the best tested two-core pair for the matrix workload. Two scoped OpenBLAS threads were fastest within that mask. Four threads are available for explicitly requested batch work outside the agent's inherited mask. This is process placement, not an exclusive CPU reservation or security boundary. Reference system BLAS is unchanged. Ollama uses four explicit inference workers, all-core scheduling, nice 10 and its existing enforced memory limit. A restricted inference mask caused a large regression and was reverted, then the restored configuration was retested. No overclock, voltage or fan changes were made.

The local inference service no longer waits for `network-online.target` at startup; its native vendor unit was copied with that dependency removed, retaining its existing command and security drop-in. The agent and instrument target already start after local filesystems and `network.target`. Optional peer transports reconnect separately. This Linux startup behavior does not establish a new console power-on path.

In a separate `PrivateNetwork=yes` instance, the installed native agent and local model performed inference, Linux/Windows reference lookup, GPU arithmetic, Gothic art and rover encoder analysis with no external route. Durable memory and completed job records survived an agent restart. The test found and fixed graceful-shutdown reporting and connection retry before request delivery; already-sent requests are never blindly replayed. The live SDK, SSH, desktop and Ollama service were not restarted. The unit suite now passes 76 tests. The initial failed qualification and the successful retests are both retained.

The durable mission was condensed below the runtime's 2,000-character mission context limit; its prior full text remains under a separate durable memory key. The current mission introduces the native creative, Linux/Windows, science, math, rover and diagnostic tools. Model-generated text remains inert. Local computation, art, references, inference and durable jobs work offline. Hybrid GPU/Ubuntu calibration, cluster refreshes and Muse communication require their existing connections.

## Offline rover encoder analysis

`jupi-rover` is an offline differential-drive odometry analyzer. It reads strictly increasing timestamps and cumulative left/right wheel distances in metres, using an explicitly supplied wheel separation. It integrates exact circular increments into a relative planar pose, exports the full pose/velocity CSV and trajectory SVG, and retains input/source hashes and assumptions in a receipt. Input is bounded to 8 MiB and 100,000 frames. It opens no device nodes and sends no actuator commands.

```sh
jupi-rover status
jupi-rover demo
jupi-rover integrate encoders.csv --wheelbase-m 0.4
jupi-rover verify RUN_DIRECTORY
jupi-agent run --timeout 30 -- /usr/local/bin/jupi-rover demo
```

CSV schema: `time_s,left_m,right_m`. Wheel distances must already be calibrated. The initial pose is `(0,0,0)`; positive yaw is counterclockwise. Encoder-only odometry assumes no wheel slip and supplies no absolute localization, gyro fusion or uncertainty certificate. A 501-frame synthetic curved path passed both a native agent job and the network-isolated qualification. Tests also cover a straight path with nonzero encoder origins, in-place rotation, a known quarter circle, invalid frames and tampered artifacts. No physical rover, camera, IMU or encoder is attached yet.
