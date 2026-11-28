# Op-count gap explained: 2754 vs 2722 (MUL_MAT) and 1109 vs 1093 (MUL_MAT_ID)

groku, Tue Nov 24 2026. Fixes the open note in the fc-nods128 benchmark README ("reason for that gap was not established").

## Answer (CONFIRMED)

The gap is duplicate test-case names. `test-backend-ops` lists some cases twice with the exact same
name string. Our driver kept the full list length as `n`, but stored results in a dictionary keyed by
name, so each duplicate pair became one entry.

| Op | n (list length, with duplicates) | distinct names (results kept) | duplicates | duplicated names |
|---|---|---|---|---|
| MUL_MAT | 2754 | 2722 | 32 | 28 names: 24 appear twice, 4 appear three times (24 + 8 = 32) |
| MUL_MAT_ID | 1109 | 1093 | 16 | 16 names, each twice |

2754 = 2722 + 32 and 1109 = 1093 + 16, exactly. No case was lost, skipped or hidden: every distinct case
has a result (MUL_MAT: 2488 OK + 234 SKIP_CPU = 2722 patched; MUL_MAT_ID: 1093 OK patched).

## Evidence

1. Driver code (JUPI 2, <lab-home>/groku-infer/mesa-nods128/opdriver.py, read-only):
   `cases = [...]` is a list built from `test-backend-ops support -b Vulkan0 -o OP`;
   `res = {}` is a dict keyed by case name; the JSON writes `"n": len(cases)` and `"results": res`.
2. Stored JSON (same folder, tests/*.json): mm-stock and mm-patched n=2754, len(results)=2722;
   mmid-stock and mmid-patched n=1109, len(results)=1093.
3. Fresh enumeration, Nov 24 2026 ~16:55 PST, on JUPI 2, CPU backend only, GPU hidden
   (VK_ICD_FILENAMES pointed at a missing file), same test-backend-ops binary that made the
   benchmark (<lab-home>/groku-infer/vk-jupi1/test-backend-ops):
   - MUL_MAT: 3118 listed, 3085 distinct. Of the 2722 Vulkan-supported names, the list holds 2754 occurrences -> 32 extra.
   - MUL_MAT_ID: 1183 listed, 1167 distinct. Of the 1093 Vulkan-supported names, 1109 occurrences -> 16 extra.
   Example duplicate: `MUL_MAT(type_a=f16,type_b=f32,m=16,n=1,k=256,bs=[1,1],nr=[1,1],per=[0,1,2,3],k_v=0,o=1,src_overlap=0,m_v=0,pad=0)` x2.

Evidence files (in evidence/phaseB-logs/opcount/):
| File | sha256 |
|---|---|
| gk-enum-MUL_MAT.txt | 115ed736bc3561ab0e8a9c0f81136f01c29c8d78b678f5b31443b8bcf04a7a68 |
| gk-enum-MUL_MAT_ID.txt | e8e1a4abfd28ff4ae7c0e1b1f5d99ca02719dd5e2f4db8f3f14ead44b8df660d |
| gk-enum-dups.json (full duplicate list with counts) | 57e12015815357ba7c6c0f804bacb17bfaac6d8c5555fc81feb81407aee7c13a |

Why some names repeat (SUSPECTED): upstream test-backend-ops builds the case list from several loops that
overlap on a few shapes (for example the m=16,n=1,k=256 vector cases), and the printed name does not include
every loop parameter. Not checked in upstream source.

What it means: the published pass/fail numbers are right; the "case" totals in the README should say
"2722 distinct cases (2754 listed, 32 duplicate names)" and "1093 distinct (1109 listed, 16 duplicates)".

- groku
