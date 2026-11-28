# JUPI kernel and system maintenance — 2026-11-25

Both JUPI computers have the verified maintenance fixes installed. The selected
15,733,760-byte kernel was reconstructed from two independently extracted
source trees with the exact original SHA-256. Both chains used recorded resource
holds and linking continuations; this is not a claim of two uninterrupted builds.
The physical machines retain their running kernel, boot selection and recovery
media. Their model-specific graphics stacks remain accelerated and protected.

| Work | Result |
|---|---|
| Kernel reconstruction | Two final images exactly match `a06fdd7ac62a84d6481962d8dafa615ef1914605890e0bf520fc26af2dd72b8e` |
| Actual FAT recovery transactions | 48/48 cases pass; all read-only fsck checks clean |
| Archive inspection | 18 synthetic cases pass, strict private supplement writer unchanged |
| Native health policy | 13 cases pass; JUPI1 scheduled timer reran successfully |
| Rollback helper | 27 owned-file fault/metadata/resume cases pass; six live batch inspections pass |
| Portable source checks | 33/33 on NIKOLAI and JUPI2; 40 guard invocations on each |
| Canonical cross-host output | 21,933 bytes match exactly, SHA `fd12932ba1093d8c3f8d79048e8cd9b8cbd3f72b01ac03fe99606c34dbe13612` |
| Selected-image VM regressions | 5/5 generic core-path checks pass |
| Physical native regression | Both machines pass the one-owned-child PIDFS probe and retain accelerated OpenGL 4.5 |
| Live deployment | Eight managed targets match receipts; both machines report zero failed service units |
| Offline witness | NIK maintenance runner and descendants: zero network syscalls under strace |

The installed repairs reconcile JUPI1's effective boot assets and concatenated
archive inspection, remove the health service's self-failure latch, replace the
unsafe v3 trial guard on both computers, and protect each model's tested graphics
packages. Exact backups and rollback steps are in HANDOFF.md and
ROLLBACK.md (lab packet, not published). Guard downgrade has a state prerequisite: resolve any
actual v4 pending trial before restoringv3; absent media leaves that state unknown.

The rebuild mismatch came from original source/output path inputs and distinct
timestamps. The weak version timestamp must be empty, the built-in cpio uses
1795561733, and the final strong banner uses Tue Nov24 15:26:06 PST2026. With those
inputs reproduced, the corrected primary objects, BTF and final image match.
The source, compiler, four patches, ten firmware entries and configuration were
preserved. [RECIPE.md](RECIPE.md) records the recipe.

Every failed candidate, resource stop, review finding and the initial observer's
202.025-second gap remain in the packet. Whole-host accumulated swap was cleared
through the existing swap file with ample RAM, preserving applications and
services. The final temporary preference was restored to60, and all owned build
process groups exited. No different candidate kernel was installed.

The local Git worktree has eight staged source/test/documentation files on
`maintenance/20261125-stability`; it has no commit or public push. Publication
source is sanitized and has its own distinct guard hash and portable qualification.
No live configuration, private recovery archive or key is included in that patch.

Physical cold boot, USB-absent boot, kexec, abrupt power-loss survival and
hardware-rooted execution attestation remain UNFLOWN. CPU bandwidth quotas remain
unsupported by the kernel. The earlier base-model GPU timestamp anomaly remains
held. These results establish the named build, transaction and live-runtime checks;
they do not claim those unflown capabilities or new FPS improvements.

The user goal continues with the actual SOV/Astra inference inventory and the
quality-first local-model engine on NIKOLAI. Model recommendations from the incoming
paste are unverified until checked against actual files, primary sources and tests.
