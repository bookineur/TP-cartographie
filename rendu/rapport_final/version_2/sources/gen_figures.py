"""Figures nouvelles du rapport final (les autres sont copiées des comptes rendus précédents).
explo.json est produit par dump_explo.js (robot SIMULÉ de codex_lidar, graines 11-13)."""
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "..", "figures")
d = json.load(open(os.path.join(HERE, "explo.json"), encoding="utf8"))

def inside(x, y):
    return (0 < x < 5 and 0 < y < 4) or (5 <= x < 9 and 0 < y < 3)

fig, axes = plt.subplots(1, 3, figsize=(15, 4.4))
bilan = []
for ax, run in zip(axes, d["runs"]):
    t0 = run["t0"]  # angle initial 0 : repère de la carte = salle décalée de t0
    tr = np.array(run["truth"]); es = np.array(run["est"])
    if run["grid"] is None:
        # refaire la grille n'est pas nécessaire pour le bilan : seule la graine 11 est dessinée en fond
        pass
    g = run["grid"]
    if g is not None:
        rows = np.array(g["rows"]); img = np.full(rows.shape, 0.6); img[rows == 0] = 1.0; img[rows == 1] = 0.0
        x0, y0, r = g["origin"][0] + t0[0], g["origin"][1] + t0[1], g["resolution"]
        ax.imshow(img, cmap="gray", vmin=0, vmax=1, extent=[x0, x0 + g["width"] * r, y0, y0 + g["height"] * r], interpolation="nearest")
        known = tot = 0
        for x in np.arange(0.05, 9, 0.1):
            for y in np.arange(0.05, 4, 0.1):
                if not inside(x, y): continue
                tot += 1
                c = int((x - x0) // r); rw = g["height"] - 1 - int((y - y0) // r)
                if 0 <= c < g["width"] and 0 <= rw < g["height"] and rows[rw, c] != -1: known += 1
        cov = known / tot
    else:
        cov = None
    for a, b in d["walls"]:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#1F4E79", lw=1.6)
    ax.plot(tr[:, 0], tr[:, 1], "-o", color="#2ca02c", ms=3, lw=1.2, label="vraie trajectoire")
    ax.plot(es[:, 0] + t0[0], es[:, 1] + t0[1], "x", color="#d62728", ms=4, label="poses recalées")
    ax.plot(*tr[0, :2], "s", color="k", ms=6)
    ax.set_aspect("equal"); ax.set_xlim(-0.5, 9.5); ax.set_ylim(-0.5, 4.5)
    t = f"graine {run['seed']} : {run['n']} scans, {run['travelled']:.1f} m, erreur max {run['emax']*100:.1f} cm"
    ax.set_title(t, fontsize=10)
    bilan.append({"graine": run["seed"], "scans": run["n"], "distance_m": round(run["travelled"], 1),
                  "erreur_max_cm": round(run["emax"] * 100, 1), "collision": run["collided"],
                  "couverture": None if cov is None else round(cov, 3), "statut": run["status"]})
axes[0].legend(loc="upper right", fontsize=8)
fig.suptitle("Exploration automatique — robot SIMULÉ, salle jamais vue (deux pièces, table, armoire). Fond : grid map construite par le robot", fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "fig_exploration_simulation.png"), dpi=130, bbox_inches="tight")
json.dump(bilan, open(os.path.join(HERE, "bilan_exploration.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
print(bilan)

# Faux positifs : chiffres de codex_lidar/tests/resultats_faux_positifs.md (scans simulés, graines 101-200)
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
et = ["Étape 1\n(bouton seul)", "Étape 3\n+ ambiguïté\nrecouvrement", "Étape 4\n+ refus si\ncontradiction"]
for a, vals, title in [(ax[0], [255, 48, 2], "Corpus simulé, 600 cas jamais vus au réglage"),
                       (ax[1], [14, 0, 0], "repetition_tp2 (15 scans simulés, vérité connue)")]:
    bars = a.bar(et, vals, color=["#c0504d", "#f79646", "#1F4E79"])
    for b, v in zip(bars, vals): a.text(b.get_x() + b.get_width() / 2, v, str(v), ha="center", va="bottom", fontsize=11)
    a.set_ylabel("faux positifs (pose acceptée fausse)"); a.set_title(title, fontsize=10)
    a.spines[["top", "right"]].set_visible(False); a.set_ylim(0, max(vals) * 1.18)
fig.tight_layout(); fig.savefig(os.path.join(FIG, "fig_faux_positifs.png"), dpi=130)
