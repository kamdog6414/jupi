GPT Codex - NIKOLAI-2

# JUPI 1 FC-NODS128 stock-hang review

Review date: 2026-11-22. Checks completed through 22:12:45 UTC (14:12:45 PST).
Requested output: <lab-home>/gaz/reviews/REVIEW-NODS128-STOCK-HANG-20261122.md
Scope: independent, read-only review of existing evidence. No GPU test, reboot,
service change, source edit, push, fetch or JUPI 2 contact was performed. Only
this new review and its external SHA256 sidecar are written.

## Decision and its exact scope

**PATCH CLEARED of a patch-exclusive hang attribution, under the recorded
stock-control provenance.** The stock-control run reproduced the initial compute-ring
fault and failed-reset pattern without the FC-NODS128 selection override.

This is a clearance of a patch-exclusive explanation, not a safety or release
qualification. The stronger literal assertion that the patch made no causal
contribution to its own failure is NOT established. The exact triggering case,
shared root cause and general patch safety remain UNKNOWN. A matching timeout
signature is not proof of identical initiating instructions or defective silicon.
No full JUPI 1 operation sweep passed, under either recorded configuration.

Evidence labels: CHECKED = the specified bytes, source behavior or recorded
sequence was inspected/recomputed; REPORTED = an attributed operator statement;
UNKNOWN = not established by the retained material. Hash matches establish byte
agreement, not independent authentication of the original measurement.

## A. Integrity and identity

All abbreviated pins supplied in the request match their recomputed full digest
prefix/suffix. The full artifact pins in the two local receipts also match:
10/10 non-self members in the morning receipt and 6/6 members in the stock
receipt. The morning receipt's embedded self-entry is ignored as instructed;
its actual external identity is f68d9782...141b2, not its obsolete self-entry
1b58af...41188. It is not an 11/11 self-verifying manifest.

The six prereboot members verify 6/6. After JUPI 1 became reachable again, the
original stock directory verifies 12/12 members against its manifest. The local
stock mirror contains only six of those twelve files; its absent members are
not corruption and were not silently counted as locally verified. Their bytes
were subsequently checked on JUPI 1 using the supplied nested SSH route.
The successful remote file-only verification was at 22:10:43 UTC.

Path aliases used below:

- R = <lab-home>/gaz/receipts/
- S = <lab-home>/gaz/staging/nods128-push/raw-jupi1-stock-20261122T134316/stock-sweep-20261122/
- P = <lab-home>/gaz/staging/nods128-push/raw-jupi1-stock-20261122T134316/prereboot-20261122/
- J = JUPI 1 <jupi1-home>/groku-infer/mesa-nods128-j1/
- D = <lab-home>/gaz/staging/nods128-push/PUSH-DRAFT.md
- C = <lab-home>/jupi-nods128-20261122/
- Packet = the added subtree ending in 2026-11-22-fc-nods128/ inside C.

### Requested artifacts: full recomputed SHA256

| Artifact | SHA256 | Result |
|---|---|---|
| R/RECEIPT-MESA-NODS128-J1-20261122T084315.md | f68d9782ce73b1a96a56138f8b3256d241d4351a93b76350ef41d56c7d8141b2 | MATCH |
| R/RECEIPT-MESA-NODS128-J1-STOCK-20261122T134316.md | d7fd1dbac8feddba970bb43ccbb94af758211f23cbc3f08e92802def75d6309c | MATCH |
| S/RESULT-STOCK-J1.md; also R/RESULT-MESA-NODS128-J1-STOCK-20261122T134316.md | 5d4bac9e5c297a33e9e4d6aae8e772f9da34c33300c53c4a193b41977a9158b3 | MATCH |
| S/HUNG-CHUNK7-cases.txt | 7cc937ab3fb02f08bd169d9837526f4c3065ca2529a728d5f04e6be98812bd4c | MATCH |
| S/kernel-lines.txt | 7c386bd1bef5f0078dfedb77dc1df034a89540975420ceb1f9488a59115c0cf1 | MATCH |
| S/amdgpu-devcoredump.txt | 8524c5f51553439a92d4aa41233c33d4a3686c19abf5dcc27bd66a8eaa2aaee9 | MATCH |
| P/SHA256SUMS; also R/J1-PREREBOOT-SHA256SUMS-20261122T134316.txt | d864818ae9f253569275e6d12b62ea3f4113581fd6eb0734688eeeb4e3cc2443 | MATCH; 6/6 members |
| D | 4ca379a7d9c30f8ff03eabfa4cec6fdcee8ea1a3a175a6d4f3c025eef62a2789 | MATCH |

The stock source manifest is
66c6f4b506f50a2d607d9bf6bbceb3ea50ba7a5f32cabea4a9601efd8d45f0da.
Its 12/12 remote matches include ABORTED, CURRENT.txt, drv.out, guard3.sh,
root.pid and stockdrv.py, which were absent from the local subset. CURRENT.txt
and HUNG-CHUNK7-cases.txt have identical content hashes. ABORTED and drv.out
are empty, matching SHA256 e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.

### Prereboot member verification

| P member | Recomputed SHA256 |
|---|---|
| dmesg-tail.txt | 41441d3c3e93088f9c32790c33264a7baed18e8b5ae6774b1a0b827736ff2afb |
| failed-units.txt | e8d2b1fba88c8b79ac4ea79a973d93a1d4b8946d7fd934ff43cc8e9f74adbed3 |
| free.txt | cef03d1709be5fa091c72400d6eddcc39295f59e35cd6ebb5d0b325de80972d4 |
| journal-k-since-hang.txt | b6bf184bcb9d246b627c6a5aa69c47f56df91d49e515ecc192adefb79c3ad29a |
| ps.txt | 7c3ffb9b76927f1f649263fdb0b9757e70d229b1bcba818f2da0bb46f39725ec |
| uptime.txt | fe917ff4730cdd9bbf5e4c70f7032d9d8d896abcf2415901bf365e16b309d08d |

### Additional comparison/provenance pins

| Artifact | SHA256 |
|---|---|
| R/RESULT-MESA-NODS128-J1-20261122T084315.md | 736f7b1bcc5a49781441dce809d0d9d9ec1cc2e044af75047073497e78b33cc1 |
| R/J1-NODS128-crash-kernel-lines-20261122T084315.txt | a9b994322fa99048812f4418de5ad1ea0ef61a817ebc29ae14b17fc5d6ed26ba |
| R/J1-NODS128-dmesg-crash-excerpt-20261122T084315.txt | 9019c8a6da94ba3462cfa1e15a7c2b2bba2dd17d098acc3f74ef189c13cf454d |
| R/J1-NODS128-amdgpu-devcoredump-20261122T084315.txt | 947327f99783811325008f093cce9bfd3988280dbd2ec9e8ed27c9b67187f81f |
| S/sweep.log | 084a57ef2aab6049b2c643d5e41fadb5613884aec257cf95041c3b62eb30cb2f |
| S/guard.log | 1813e1a3fa2efe786e1eef4b414a00bb7c9b2a3988d8d405f1410b802d474e0e |
| J/stock-sweep-20261122/stockdrv.py | 79d8b1973fb5d90b3a5f0a788183e1d3bac7bfd8c8d4d10551b63cb337f6e3a8 |
| J/stock-sweep-20261122/guard3.sh | 44fb0da30dc5152f88e8bc60c63a4be6bd0745821506ab8ddbbf6091aa5bce14 |
| JUPI 1 /usr/lib/libvulkan_radeon.so | acf91948754480ed906e0b90df2a908abe4cde446fe45e94d75a9ee408a34ae5 |
| JUPI 1 /usr/share/vulkan/icd.d/radeon_icd.x86_64.json | 0a6ffc467e6c1b38bb26f67f10a9a2359e11de7ccc4472602fd383e3b4a48658 |

The remaining morning receipt members also match: the saved format-patch,
both local JUPI 2 logit records, both progress records and the draft copy.
Those are local byte checks only, not new JUPI 2 execution or numerical replay.

## B. Did the control select stock Mesa without VK_ICD_FILENAMES?

CHECKED: the retained, manifest-pinned stockdrv.py at line 8 copies its parent
environment and explicitly removes VK_ICD_FILENAMES. Its support subprocess
(line 15) and every test subprocess (line 20) receive env=env. The source
therefore clears that variable even if the parent had it set. The guard log
identifies python3 stockdrv.py as the controlled parent; the retained sweep
banners identify AMD RADV LIVERPOOL (radv).

CHECKED by read-only access after the new boot: the system ICD JSON maps its
library_path to the absolute /usr/lib/libvulkan_radeon.so and declares API
1.2.195. The library is 8,518,120 bytes with the full acf91948...a34ae5 digest
above. The package database identifies mesa-ps4 21.3.2-1. These match the stock
identity reported for the control; the request supplied only an abbreviated
library pin, so the full digest here is a new independent recomputation.

REPORTED in the run result/progress: the reboot returned to a clean kernel
fault count, then the stock sweep started at 13:34:39 PST using that system
ICD. CHECKED in the recorded log: the stock parent and test process ran, and
the kernel/dump agree on PID 3866 for the first timeout at 13:38:38 PST.

Conclusion: stock selection has source-backed evidence, not just a prose
label. This is sufficient for the bounded stock-control interpretation above.
It is not a saved memory-map observation of the historical failing process:
no such mapping or loader trace was retained. The script copies all other
parent variables and clears only VK_ICD_FILENAMES. Consequently, absence of
every other possible loader override is not independently proven. The current
ICD/library check is also distinct from an attestation of every byte loaded
at the earlier run time.

The official loader documentation describes VK_DRIVER_FILES as another driver
override and the JSON library_path field as the selected library path. That is
why clearing one variable alone is not claimed as complete runtime provenance:
[Khronos Vulkan loader driver interface](https://github.com/KhronosGroup/Vulkan-Loader/blob/main/docs/LoaderDriverInterface.md).
This reference is explanatory; it is not a measurement of this run or proof
that a particular optional mechanism was supported by its installed loader.

## C. Kernel and dump comparison

Times below are Nov 22 PST, from the checked kernel excerpts.

| Event | Patched run | Stock-control run |
|---|---|---|
| First timeout | 08:35:29, comp_1.1.0 | 13:38:38, comp_1.1.0 |
| First named process | test-backend-op, PID 754337 | test-backend-op, PID 3866 |
| Reset begins; asic atom init fails; DP link/clock recovery errors | 08:35:29 | 13:38:38 |
| GPU reset(2) failed; GPU Recovery Failed: 1 | 08:35:31 | 13:38:40 |
| First following gfx timeout | 08:35:39 | 13:38:48 |
| First following DMA timeout | sdma1 at 08:35:49 | sdma0 at 13:38:58 |
| Further recorded graphics/DMA failure | sdma0 at 08:36:00; xfwm4 gfx at 08:36:11 | Xorg gfx at 13:39:10; xfwm4 gfx at 13:39:23 |

CHECKED: the initial ring and two-second failed-reset sequence match. Graphics
and DMA timeouts follow both failures. DisplayPort errors already occur during
the initial reset attempt; they do not first appear only after recovery fails.
The downstream DMA order/set is different. Call this the same observable
failure signature, not byte-identical logs or an identical downstream sequence.

Both saved dumps identify kernel 6.15.4-crashnt-4.7_no-built-in-fw, Liverpool,
the same initial ring and their respective test-process PID. Zero fault fields
in these dumps do not identify an initiating instruction or prove a physical
chip defect. The failed recovery path is observed; its underlying cause is not.

The stock guard trips at 13:38:40 with swapused=0 and bad_new=2. The morning
guard also trips on new fault counts, with 708 MiB swap used. High swap usage
is therefore not required for the recorded stock-control failure. This does
not isolate all other workload, memory, thermal or boot-history differences.

## D. Chunk and operation correspondence

CHECKED: stock CURRENT.txt and HUNG-CHUNK7-cases.txt identify chunk 7 as the
half-open case interval [179:219], i.e. zero-based cases 179-218 inclusive.
The list has 40 candidate operations, all MUL_MAT with type_b=f32 and m=16:

- q3_K: 2 cases, n=1/8, k=4096.
- q4_K, q5_K, q6_K: 11 cases each, n=1..9 at k=256 and n=1/8 at k=4096.
- tq2_0: 5 cases, n=1..5, k=256.

The retained list is a durable pre-dispatch candidate set. It does not prove
which one of those 40 operations was executing when the timeout occurred.
The guard stopped the run before that chunk's captured output was committed.

The morning chain source explicitly selects mm-patched, MUL_MAT, chunks of
40. Its opdriver.py captures a chunk's output and writes it after return;
it does not durably record the next chunk before dispatch. The morning result
explicitly says its exact hung chunk was lost when the driver was terminated.
Thus the patched run is in the SAME MUL_MAT FAMILY, but SAME CHUNK or SAME
QUANTIZATION CASE is UNKNOWN. Similar elapsed times cannot recover that fact.

Pins for that source inspection:

- <lab-home>/gaz/staging/nods128-push/raw-jupi1/tests/chain.sh:
  1c6160619772c79028064f9767c03b276324bb50d84a77a9841ae0f146fb2a2e
- <lab-home>/gaz/staging/nods128-push/raw-jupi1/opdriver.py:
  89c1381682a8d2e8fcbf365858a34b6266e96cd209de1e6c587744003c619067

Coverage correction: the stock result's phrase 'chunks 1-6 finished' must not
become 'cases 0-208 passed'. The actual return codes are 1, 1, 1, -6, -6, -11.
The faulted chunks overlap: [120:160], [157:197], [168:208]. They returned
partial output, failures or process faults; bad_new=0 at those checkpoints
means no counted new kernel-ring fault then, not full numerical correctness.
There is no completed JUPI 1 operation aggregate in the staged packet.

## E. Causal interpretation and present state

The control removes the need for a patch-specific explanation of this failure
class. Reproduction under the recorded stock setup is positive evidence; it
should not be hidden behind the morning report's now-obsolete statement that
no stock sweep had been attempted. That is the basis for the scoped clearance.

It does not establish that stock and patched runs failed on one instruction,
that their exact root cause is the same, that the patch never worsens a failure,
or that either complete sweep is safe. A GPU timeout/recovery failure is an
outcome shared by multiple possible initiating causes. No release or promotion
is authorized by this review.

Current-state update, REPORTED by Groku via Kam during review: JUPI 1 booted at
14:06 PST, display up, no timeouts/resets, about 6.2 GB free RAM and swap zero.
This supersedes the stock result's capture-time 'currently down' statement as
an operator report. Read-only source access subsequently succeeded. I did not
exercise the GPU or independently qualify its current health. The two historical
hang records remain unchanged. JUPI 2's 24-hour run remains untouched until
its stated 07:40 PST Nov 23 endpoint; this review did not contact that node.

## F. What the push draft and packet need to change

These are recommendations for a new additive revision, NOT edits performed.
Frozen morning statements remain historical evidence, but cannot serve as the
current publication summary without the follow-up.

| Location | Current problem | Required factual change |
|---|---|---|
| D:13-14 | Only the patched hang appears; reboot/stock test is prospective. | Preserve the morning crash and append the later stock-control hang, separate times and pins. The reboot and stock attempt have happened. |
| D:14 | 'Attributed to the patch or to stock' implies a binary cause decision. | State the reproduced failure is not exclusive to the patched setup. Exact cause and patch contribution remain unresolved. |
| Packet README:98,105-107 | Says stock sweeps never ran and whether stock hangs is unknown. | Date the morning cutoff; add the incomplete stock MUL_MAT attempt and matched initial failure signature. MUL_MAT_ID is still not established by this follow-up. |
| Packet README:106-107,145 | Full-sweep warning could look conditional on a missing comparison. | Keep the warning: two incomplete JUPI 1 sweeps, no complete JUPI 1 operation/ISA qualification. Stock also hung. |
| C/README.md:357 | Summary can imply a patched-only crash. | Add the stock-control reproduction and the explicit limited scope of clearance. |
| Packet RECEIPTS.txt:9-10 and its morning crash excerpt | Only morning evidence is indexed. | Add separately named stock result, receipt, kernel, guard and candidate-list records. Never replace the morning evidence. |
| Packet data/jupi1/ops/COUNTS.json | Empty aggregate; no successful full JUPI 1 result. | Preserve incomplete status and identify partial-run coverage. Do not manufacture totals or success from the newer hang. |
| Packet README:82 and stock result:21 | The stock floor timing was invalidated by overlapping execution; the replacement was not run. | Retain exclusion. No replacement timing was obtained in this control. |
| D:6,8-10,28 and its saved patch/manifest identity | Identify only morning commit 03d7320 and its file set. | Any updated packet needs a new additive commit, regenerated patch/manifest and refreshed draft pins. Existing hashes do not cover new stock evidence. |
| D:26 | Revert is followed by pushing local main while the checked-out branch is fc-nods128. | As written, the revert would land on the feature branch and the push would name unchanged local main. Require a reviewed rollback bound to the actually published branch and Kam's go. No rollback/push was run. |

Two other publication claims need narrower wording: the packet's 'every case'
correctness claim must preserve CPU-reference skips and reconcile nominal
2754/1109 enumerations with the retained distinct result entries (2722 MUL_MAT,
including 234 SKIP_CPU and 2488 patched OK; 1093 MUL_MAT_ID). The reason for
that enumeration difference was not established here. The short-3 logit example
is consistent with numerical/order sensitivity; it does not prove universal
absence of corruption or fully isolate summation order as its cause. These
findings come from existing local packet data, not new JUPI 2 execution.

Do not list 'root cause unknown' itself as now false. The stale question is
whether the recorded stock setup can reproduce the signature; the underlying
root cause remains UNKNOWN. Likewise, the new stock result's unqualified
'NOT caused'/'patch cleared' wording should carry this review's scope qualifier.

### Offline Git and packet checks

CHECKED without fetch/push: branch fc-nods128, HEAD
03d732024fcd23c129de81f909cf24635ff1bb41. Its parent and cached origin/main are
e76750add3f25514e75c0a045f67545fa6af9c35. The commit changes 53 files: 52 added
and README.md modified, with 2088 inserted lines and zero deletions; its anchor
file is unchanged. Cached origin/main is not
proof of the live server branch, and this check does not certify current remote
publication state.

- Staged format-patch SHA256: 9c8a666ecf4e70c3b7c977a262275b9c59d2d7d3a87ac1ac32da945d7b7c0a47.
- Stable Git patch ID: 0e3bc419b0b952e358f553536360c86cefaacd7b; staged patch matches the HEAD diff. Git commit/patch IDs here are not SHA256 file digests.
- Packet SHA256SUMS.txt: 13808a83c41b86c9f92224f926fd3cadf8d6e3aad4b3f3550314cb5fda2f4c80; 51/51 listed members match, and those bytes match HEAD blobs.
- Compiler patch: ef0d6315ccc92f1575e0c1638e3a5d2a3a2e4d7ef303a4b97cdad1b3498a5ee3.
- Packet README: cf576d1365836142a3f15d00b8246078caa00076787b7a7ba2a247f83516fd15.
- Root README: d65050c7d2d4af195f5a8cc0a48b556419b8ddd18c61022e15c7cf88d1a3c2a9.

## Next decision

Keep JUPI 1's GPU idle for now. The next useful step is an additive evidence
and publication-draft correction, preserving both runs, partial coverage and
this scoped causal result. No new full sweep is justified by this review.
If exact-case isolation is later required, it needs its own bounded recovery
window and owner approval; it is not part of this read-only task. Do not disturb
JUPI 2's ongoing run. This review supplies evidence, not a push or test go.

The report's own SHA256 is in the adjacent external .sha256 file; no circular
self-hash is embedded. ASCII and selected historical-term checks are 0/0 for
the report before/after writing. Source paths with a historical restricted
parent component are referred to by the Packet alias, not altered on disk.

**Verdict: PATCH CLEARED of a patch-exclusive hang attribution under the recorded stock-control setup; exact root cause and general patch safety remain UNKNOWN.**

