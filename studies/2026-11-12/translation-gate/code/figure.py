import json, os, matplotlib
matplotlib.use('Agg'); import matplotlib.pyplot as plt
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
plt.rcParams.update({'font.family': 'monospace', 'font.size': 8, 'axes.edgecolor': 'black', 'text.color': 'black',
                     'axes.labelcolor': 'black', 'xtick.color': 'black', 'ytick.color': 'black'})
A = json.load(open(f"{B}/compare/ANALYSIS.json")); T = A["T0"]; n = T["raw_correct"][1]
fig, ax = plt.subplots(1, 3, figsize=(14, 4.8), facecolor='white')
a = ax[0]; cats = list(T["by_cat"].keys())
labs = ["ALL"] + cats; raw = [T["raw_correct"][0] / n] + [T["by_cat"][c]["raw"][0] / T["by_cat"][c]["raw"][1] for c in cats]
gat = [T["gate_pass"][0] / n] + [T["by_cat"][c]["gate_pass"][0] / T["by_cat"][c]["gate_pass"][1] for c in cats]
x = range(len(labs)); w = 0.38
a.bar([i - w / 2 for i in x], raw, w, color='white', edgecolor='black', hatch='///', label='raw correct (lenient)')
a.bar([i + w / 2 for i in x], gat, w, color='black', edgecolor='black', label='gated PASS (all correct)')
a.set_xticks(list(x)); a.set_xticklabels(labs, rotation=30); a.set_ylim(0, 1.05); a.legend(frameon=False, loc='upper right')
a.set_title(f"A  T0 ACCURACY, n={n} items, qwen3-0.6b on JUPI 2\nraw {T['raw_correct'][0]}/{n}  gated PASS {T['gate_pass'][0]}/{n}  (rest = HOLD)", loc='left')
a = ax[1]; al = A["all"]; c = A["consensus"]
names = ["full gate\n(schema+recompute)", "schema-only\ngate", f"consensus\ngate (k={c['k']})"]
vals = [al["silent_wrong_full_gate"], al["silent_wrong_schema_only"], c["consensus_gate_silent_wrong"]]
a.bar(range(3), vals, 0.55, color=['black', 'white', 'white'], edgecolor='black', hatch=['', '///', '...'])
for i, v in enumerate(vals): a.text(i, v + 0.3, str(v), ha='center')
a.set_xticks(range(3)); a.set_xticklabels(names); a.set_ylim(0, max(vals + [1]) * 1.25 + 1)
a.set_title(f"B  SILENT WRONG ANSWERS PASSED\n{A['n_outputs']} outputs (consensus gate: {c['n_items']} items)\nwrong home actions: full gate {al['unsafe_actuation_full_gate']}, schema-only {al['unsafe_actuation_schema_only']}", loc='left')
a = ax[2]; m = c["2x2"]; a.set_xlim(0, 2); a.set_ylim(0, 2); a.set_xticks([0.5, 1.5]); a.set_yticks([0.5, 1.5])
a.set_xticklabels(['F0 correct', 'F0 wrong']); a.set_yticklabels([f'split', f'all {c["k"]} agree'])
cells = {(0, 1): m["unanimous_correct"], (1, 1): m["unanimous_wrong"], (0, 0): m["split_correct"], (1, 0): m["split_wrong"]}
for (i, j), v in cells.items():
    a.add_patch(plt.Rectangle((i, j), 1, 1, fill=(i, j) == (1, 1), color='black' if (i, j) == (1, 1) else None, ec='black', lw=1))
    a.text(i + 0.5, j + 0.5, str(v), ha='center', va='center', fontsize=20, color='white' if (i, j) == (1, 1) else 'black')
pr = c['precision']; rc = c['recall']
a.set_title(f"C  CONSENSUS vs CORRECTNESS ({c['n_items']} items)\nprecision {pr:.2f}  recall {rc:.2f}\nblack = unanimous and wrong", loc='left')
fig.suptitle("JUPI TRANSLATION GATE v0  --  model proposes, deterministic gate disposes  (synthetic, private)", x=0.01, ha='left', fontsize=9)
fig.tight_layout(); fig.savefig(f"{B}/TRANSLATION-GATE-FIGURE.png", dpi=130, facecolor='white')
print("ok")
