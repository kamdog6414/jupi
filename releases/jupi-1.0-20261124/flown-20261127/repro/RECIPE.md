# JUPI 1.0 deterministic build recipe repair

This lane preserves the existing source patches, configuration, firmware and target optimization flags. The repair makes the original build path names and three distinct temporal inputs explicit. It recreates the paths inside a private mount namespace and freezes time independently for each generating target. Actual source/output directories can live elsewhere on the host.

## Why the paths matter

The retained Clang ThinLTO objects include an absolute `source_filename`, debug-file directories and a full recorded compiler command line. Merely adding file/debug prefix-map flags does not remove every path-bearing input. The independently rebuilt kernel therefore had an unresolved byte mismatch despite source/config/firmware agreement.

The bounded object experiments show:

- The original source/header tree and the independent source/header tree both reproduce the original `fs/pidfs.o` bytes when the original compiler argument vector and path names are restored.
- A separate portable canonical namespace yields identical bitcode and disassembled IR from both trees and a repeated compile.
- The full canonical make recipe separately regenerated the original `fs/pidfs.o` hash.

See `PATH-CAUSE-PHASE1.json`, `experiments/ORIGINAL-PATH-RESULT.json`, and `experiments/CANONICAL-OBJECT-RESULT.json`. These object checks alone are not whole-image evidence; the full-build result files record that outcome separately.

## Build contract

Canonical physical prefix:

`<lab-store>/overflow/jupi-kernel-official-20261124-build`

Canonical legacy alias:

`<lab-home>/fullcircle-core/jupi-kernel-official-20261124/build`

Neither must refer to original host data inside the build namespace. The runner first binds the explicitly supplied fresh source/output, read-only toolchain/OpenSSL/firmware, and owned log/temp directories to private handles. It then overlays `/tmp`, `/mnt` and `/home` only in that namespace, recreates the canonical names, and drops to the invoking UID/GID before running make. Host mounts and original source/output bytes remain unchanged.

The corrected `code/canonical_release_namespace_temporal.py` accepts one JSON request containing absolute host paths for `linux`, `out`, `toolchain`, `openssl`, `firmware`, `logs`, `tmp` and `rules`, plus numeric invoking `uid` and `gid`. All mutable paths must be fresh, task-owned directories. Source must be the reviewed four-patch tree; `.config` must match SHA-256 `7e3c1e64f56203c08e6383898feb0804d64e5136fc664799deeda8f6c29ee001`. The runner checks that config again after `olddefconfig`. The original path-only helper and failed attempts remain available as evidence.

The original build user, host, version and timestamp are fixed:

```text
KBUILD_BUILD_USER=jupi
KBUILD_BUILD_HOST=nikolai
KBUILD_BUILD_VERSION=jupi-1.0
KBUILD_BUILD_TIMESTAMP=Tue Nov 24 15:26:06 PST 2026
LOCALVERSION=
KCFLAGS=-march=btver2 -mtune=btver2 -O3
```

Compiler/LLD are the retained Ubuntu 18.1.8 toolchain; pahole is 1.31 and GNU make is 4.4.1. The tool/library closure is a separate pinned input. This lane does not claim reproducibility after arbitrary toolchain or dependency upgrades.

## Distinct temporal inputs

A single global `KBUILD_BUILD_TIMESTAMP` is insufficient to reproduce this selected release. It changes both the temporary weak version banner and the embedded default cpio, even if the final strong banner is correct. The selected release has three separate time inputs:

| Generator | Exact selected value |
| --- | --- |
| `init/utsversion-tmp.h`, consumed by weak `init/version.o` | Empty timestamp |
| `usr/initramfs_data.cpio` default entries | Epoch `1795561733`, Tue Nov 24 15:08:53 PST 2026 |
| `include/generated/utsversion.h`, consumed by strong `init/version-timestamp.o` | Epoch `1795562766`, Tue Nov 24 15:26:06 PST 2026 |

The read-only `rules/temporal-inputs.mk` is included through GNU make's `MAKEFILES` environment variable at `/tmp/fc-jupi-rules/temporal-inputs.mk`. Target-specific variable assignments isolate these generators. No kernel source is modified. The producer-only correction regenerated both primary mismatched objects at their exact original hashes; see `experiments/TEMPORAL-CAUSE.json` and `build-a-producer-fix/monitor/RESULT.json`.

The corrected recipe retains make `-j4` and adds `JOBS=1`. The source search in `experiments/JOBS-USAGES.txt` finds its consumers in BTF generation and the separate perf tool Makefile. Actual runtime `pahole -j1` arguments are captured with all original BTF feature flags intact. Worker count is a resource control; this lane does not attribute the earlier image mismatch to pahole concurrency.

## Actual independent builds

`build-a` and `build-b` came from independent full archive extractions. A pure Git blob/tree hash of each actual extracted filesystem matches pristine tree `d5a8c543909b61100dc5870697e141d5ebe932f9`, covering 89,019 regular files and 79 symbolic links. The original archive's one normalized safe symlink spelling is restored exactly before hashing. The four patches apply with error checks; all touched sources match the selected release. All ten embedded firmware inputs match their pins.

The parent authorized build A first. Build B is authorized only if A completes and matches the selected image SHA-256 `a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e`. Each build starts from its independent fresh output tree and a fresh flat three-cycle swap preflight. CPU affinity is 2-5, make parallelism is four, and niceness is 10. Exact guards and execution arguments are retained in the per-build `monitor/` and `logs/` directories.

The original A attempt stopped at its frozen swap-growth guard during BTF generation. A controlled jobs1 continuation built an image but did not match. The leaf-object diagnostic isolated the two primary temporal differences, and the targeted correction proved both producer hashes. The corrected A relink and B finalization both matched the selected image exactly. Read `build-a-resume-temporal/monitor/RESULT.json` and `build-b-finalize-temporal/monitor/RESULT.json` for completed image outcomes. B's initial clean-source compile and two resource holds remain separately recorded. These are two independently extracted source chains with controlled continuations, rather than two uninterrupted clean builds. A missing result is not a pass. The parent owns VM checks, overall maintenance promotion and any public push.

## Long-running supervision

Use `code/monitor_canonical_recipe_v4.py` under an owned transient user systemd service, with an explicit wall limit and bounded stop. A tool-session process alone did not reliably own build A: its original supervisor received SIGTERM (tool exit 143), while the separately grouped build continued. The exact signal sender is unknown. The original observation stream and a 202.025-second unsampled gap are retained, followed by an independently attached service observer. No uninterrupted-safety claim is made for the original A attempt. See `experiments/TOOLING-FALSIFIER.json`.

For the already prepared and conditionally authorized build B, the actual launch form is:

```sh
systemd-run --user --unit=fc-jupi-kernel-build-b-20261125 \
  --property=RuntimeMaxSec=2460 --property=TimeoutStopSec=30 \
  --property=KillMode=control-group \
  /usr/bin/python3 -B /ABSOLUTE/LANE/code/monitor_canonical_recipe_v4.py build-b
```

The v4 supervisor checks the corrected A image identity before starting B, requires B's independently prepared output to contain only its config before launch, records a fresh three-cycle flat swap preflight, pins its own/helper/rule SHA-256 values, checks the entire owned process group, and performs bounded TERM/KILL cleanup even if the group leader has exited. It writes structured error evidence on exceptions. The transient user service survives the short tool-session lifecycle and disappears without enabling any persistent service. Save the unit's final status alongside the build result before systemd garbage-collects it.

## Boundaries

This recipe changes build-path handling. It does not change the kernel's configuration, source patches, drivers, radio/controller state, voltage, frequency or cooling controls. It never installs a kernel or touches a console or boot medium. No cold-boot, power-loss or hardware-attestation claim follows. The original differently pathed rebuild and its sealed mismatch evidence remain preserved.

The namespace normalizes a trusted, source-pinned build; it is not a whole-filesystem sandbox for untrusted code. Unrelated host locations such as `/var` and `/run` remain inherited. Build-command writes are confined by the fixed reviewed recipe to the owned output/log/temp targets; the external supervisor additionally writes its owned monitor metadata and artifact copies.
