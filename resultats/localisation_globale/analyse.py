"""Bilan de la localisation globale : synthese.md + figures (à partir de resultats.json).
Lancer : python resultats/localisation_globale/analyse.py resultats/localisation_globale/version_1"""
import json
import sys
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from carto.gridmap import build_grid  # noqa: E402
from carto.register import clean_scan  # noqa: E402
from carto.scan import load_poses, load_scans  # noqa: E402
from carto.localisation_globale import SESSION, _num  # noqa: E402

out = Path(sys.argv[1])
rows = json.loads((out / "resultats.json").read_text("utf-8"))
REFS = ["grid map", "carte vectorielle"]
CLASSES = ["concordant", "proche", "faux positif", "refusé"]
COL = {"concordant": "#2ca02c", "proche": "#f2a900", "faux positif": "#d62728", "refusé": "#7f7f7f"}

lines = ["# Localisation globale d'un scan — résultats (séance réelle du 10/11)", "",
         "Protocole : `PROTOCOLE.md` (écrit et committé avant la mesure). Référence de comparaison : "
         "poses de l'Auto-SLAM, **pas une vérité terrain**.", "",
         "| Référence | scans | concordant (< 10 cm, < 2°) | proche (< 30 cm, < 5°) | faux positif | refusé | "
         "écart médian des acceptés | temps moyen |", "|---|---|---|---|---|---|---|---|"]
summ = {}
for ref in REFS:
    rs = [r for r in rows if r["reference"] == ref]
    c = {k: sum(r["classe"] == k for r in rs) for k in CLASSES}
    acc = [r for r in rs if r["decision"] == "accepté"]
    med = (f"{np.median([r['ecart_m'] for r in acc]) * 100:.1f} cm / {np.median([r['ecart_deg'] for r in acc]):.2f}°"
           if acc else "—")
    summ[ref] = c
    lines.append(f"| {ref} | {len(rs)} | {c['concordant']} | {c['proche']} | {c['faux positif']} | {c['refusé']} | "
                 f"{med} | {np.mean([r['temps_s'] for r in rs]):.1f} s |")
n = len([r for r in rows if r["reference"] == REFS[0]])
lines += ["", "## Critères annoncés", ""]
for ref in REFS:
    c = summ[ref]
    ok1 = c["faux positif"] == 0
    ok2 = c["concordant"] + c["proche"] >= 0.8 * n
    lines.append(f"- {ref} : 0 faux positif → **{'atteint' if ok1 else 'non atteint'}** ({c['faux positif']}) ; "
                 f"≥ 80 % concordants ou proches → **{'atteint' if ok2 else 'non atteint'}** "
                 f"({c['concordant'] + c['proche']}/{n} = {100 * (c['concordant'] + c['proche']) / n:.0f} %)")
lines += ["", "## Scan par scan", "", "| scan | grid map | carte vectorielle |", "|---|---|---|"]
by = {}
for r in rows:
    by.setdefault(r["scan"], {})[r["reference"]] = r
fmt = lambda r: f"{r['classe']} ({r['ecart_m'] * 100:.0f} cm, {r['ecart_deg']:.1f}°, p={r['p']:.2f}, rival={r['rival']:.2f})"
for s in sorted(by, key=_num):
    lines.append(f"| {s} | {fmt(by[s]['grid map'])} | {fmt(by[s]['carte vectorielle'])} |")
(out / "synthese.md").write_text("\n".join(lines) + "\n", "utf-8")
print("\n".join(lines[:12 + len(REFS)]))

# ---- figure : carte complète (fond) + poses Auto-SLAM et poses trouvées
truth = load_poses(SESSION / "poses.json")
files = sorted(SESSION.glob("scan*.csv"), key=lambda f: _num(f.stem))
scans = {s.name: clean_scan(s) for s in load_scans(files) if s.name in truth}
g = build_grid([(scans[k], truth[k]) for k in sorted(scans, key=_num)], 0.05)
fig, axes = plt.subplots(1, 2, figsize=(13, 6.2))
for ax, ref in zip(axes, REFS):
    ax.imshow(1 - g.probability(), cmap="gray", origin="lower", extent=g.extent, vmin=0, vmax=1)
    for r in (r for r in rows if r["reference"] == ref):
        t = truth[r["scan"]]
        col = COL[r["classe"]]
        ax.plot(t.x, t.y, "o", mfc="none", mec="#1F4E79", ms=6)
        if r["decision"] == "accepté":
            ax.plot([t.x, r["x"]], [t.y, r["y"]], "-", color=col, lw=1)
            ax.plot(r["x"], r["y"], "x", color=col, ms=6, mew=1.6)
    c = summ[ref]
    ax.set_title(f"{ref} : {c['concordant']} concordants, {c['proche']} proches, "
                 f"{c['faux positif']} faux positifs, {c['refusé']} refus", fontsize=10)
    ax.set_xlabel("x (m)")
    ax.set_aspect("equal")
axes[0].set_ylabel("y (m)")
h = [plt.Line2D([], [], ls="", marker="o", mfc="none", mec="#1F4E79", label="pose Auto-SLAM")] + \
    [plt.Line2D([], [], ls="", marker="x", color=COL[k], label=f"pose trouvée : {k}") for k in CLASSES[:3]]
fig.legend(handles=h, loc="lower center", ncol=4, fontsize=9, frameon=False)
fig.suptitle("Localisation globale de chaque scan, SANS pose initiale, sur une carte construite sans ce scan "
             "(séance réelle du 10/11)", fontsize=11)
fig.tight_layout(rect=(0, 0.05, 1, 0.96))
fig.savefig(out / "localisation_globale.png", dpi=130, bbox_inches="tight")
print("figure ->", out / "localisation_globale.png")
