"""Figures et chiffres du compte rendu du Jour 2 (localisation).

Copie les figures de resultats/localisation/version_1, trace deux figures
explicatives (les trois références, le paysage du score) et écrit donnees.json
(tableaux lus par make_report.js) à partir de resultats.csv.
"""
import csv
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\HP\TP-cartographie")
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from carto import localisation as L
from carto.evaluation import SUCCESS_TH, SUCCESS_XY, perturb, sim_scan
from carto.gridmap import build_grid
from carto.scan import Pose
from carto.simulate import TRUE_POSES
from carto.vectormap import build_vector_map

ROOT = Path(r"C:\Users\HP\TP-cartographie")
RES = ROOT / r"resultats\localisation\version_1"
OUT = ROOT / r"rendu\jour2\version_1\figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.titleweight": "bold", "axes.titlesize": 11})

for n in ("sensibilite_simulation.png", "sensibilite_reel.png", "precision_temps_simulation.png",
          "precision_temps_reel.png", "exemples_simulation.png", "exemples_reel.png"):
    shutil.copy(RES / n, OUT / n)

# ------------------------------------------------- les trois références (simulation)
rng = np.random.default_rng(0)
pairs = [(sim_scan(p, rng), p) for p in TRUE_POSES.values()]
G = L.GridRef(build_grid(pairs, 0.05))
V = L.VectorRef(build_vector_map(pairs).segments)
p_ref = TRUE_POSES["pos1"]
C = L.CloudRef(sim_scan(p_ref, rng).world_xy(p_ref))
truth = Pose(1.9, 1.3, np.radians(25))
local = sim_scan(truth, rng).local_xy()
wrong = Pose(truth.x + 0.25, truth.y + 0.15, truth.theta + np.radians(6))
pts = wrong.transform(local)[::6]

fig, axes = plt.subplots(1, 3, figsize=(15, 5))
ax = axes[0]
g = G.grid
x0, y0 = g.origin
ext = [x0, x0 + g.shape[1] * g.res, y0, y0 + g.shape[0] * g.res]
im = ax.imshow(G.D, origin="lower", extent=ext, cmap="viridis_r", vmax=0.6)
ax.contour(G.D, levels=[0.05, 0.15, 0.3], origin="lower", extent=ext, colors="w", linewidths=0.5)
plt.colorbar(im, ax=ax, fraction=0.04, label="distance au mur le plus proche (m)")
ax.set_title("1. Grid map : champ de distance précalculé")
for k, (ref, ax) in enumerate(((G, axes[0]), (V, axes[1]), (C, axes[2]))):
    d, gr = ref.query(pts)
    q = pts - d[:, None] * gr
    ok = d < 0.9
    for a, b in zip(pts[ok], q[ok]):
        ax.plot([a[0], b[0]], [a[1], b[1]], "-", color="tab:orange", lw=0.8)
    ax.plot(pts[:, 0], pts[:, 1], "o", color="tab:red", ms=3, label="scan (pose fausse)")
for s in V.segments:
    axes[1].plot([s.p1[0], s.p2[0]], [s.p1[1], s.p2[1]], "k-", lw=2)
axes[1].set_title("2. Carte vectorielle : distance au segment")
axes[2].plot(C.P[:, 0], C.P[:, 1], ".", color="0.35", ms=2, label="scan de référence")
axes[2].set_title("3. Entre scans : distance au point le plus proche")
for ax in axes:
    ax.set_aspect("equal")
    ax.set_xlim(-0.3, 8.3)
    ax.set_ylim(-0.3, 6.3)
    ax.legend(loc="upper right", fontsize=8)
fig.tight_layout()
fig.savefig(OUT / "fig_references.png", dpi=110)
plt.close(fig)

# ------------------------------------------------- paysage du score (σ large / σ fin)
sub = L._subsample(local, 150)
r = np.linspace(-0.6, 0.6, 81)
X, Y = np.meshgrid(truth.x + r, truth.y + r)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
for ax, sig in zip(axes, (0.15, 0.03)):
    poses = np.column_stack([X.ravel(), Y.ravel(), np.full(X.size, truth.theta)])
    S = G.score_many(sub, poses, sig).reshape(X.shape)
    im = ax.imshow(S, origin="lower", extent=[-0.6, 0.6, -0.6, 0.6], cmap="magma")
    ax.plot(0, 0, "c+", ms=14, mew=2)
    plt.colorbar(im, ax=ax, fraction=0.045, label="score (vraisemblance moyenne)")
    ax.set_title(f"σ = {sig * 100:.0f} cm : " + ("bassin large, sommet émoussé" if sig > 0.1 else "sommet net, bassin étroit"))
    ax.set_xlabel("décalage en x (m)")
    ax.set_ylabel("décalage en y (m)")
fig.suptitle("Score de la grid map autour de la vraie pose (θ exact) — principe de la multi-résolution", fontweight="bold")
fig.tight_layout()
fig.savefig(OUT / "fig_paysage_score.png", dpi=110)
plt.close(fig)

# ------------------------------------------------- convergence de Gauss-Newton
init = perturb(truth, (0.35, 12.0), np.random.default_rng(4))
x = np.array([init.x, init.y, init.theta])
traj = [x.copy()]
for it in range(1, 16):
    res = L.gauss_newton(G, local, init, iters=it)
    traj.append([res.pose.x, res.pose.y, res.pose.theta])
traj = np.array(traj)
e = np.hypot(traj[:, 0] - truth.x, traj[:, 1] - truth.y) * 100
a = np.degrees(np.abs(L.wrap(traj[:, 2] - truth.theta)))
fig, ax = plt.subplots(figsize=(7, 3.6))
ax.semilogy(e, "o-", label="erreur de position (cm)")
ax.semilogy(a, "s-", label="erreur d'angle (°)")
ax.axhline(SUCCESS_XY * 100, color="tab:blue", ls=":", lw=1)
ax.axhline(SUCCESS_TH, color="tab:orange", ls=":", lw=1)
ax.set_xlabel("itérations de Gauss-Newton")
ax.set_title("Convergence de Gauss-Newton sur la grid map (départ 35 cm / 12°)")
ax.grid(alpha=0.3, which="both")
ax.legend()
fig.tight_layout()
fig.savefig(OUT / "fig_convergence_gn.png", dpi=120)
plt.close(fig)

# ------------------------------------------------- chiffres pour les tableaux
rows = list(csv.DictReader(open(RES / "resultats.csv", encoding="utf-8-sig"), delimiter=";"))
for r in rows:
    for k in ("init_m", "init_deg", "err_m", "err_deg", "temps_ms", "score"):
        r[k] = float(r[k].replace(",", "."))
    r["reussite"] = int(r["reussite"])
levels = sorted({(r["init_m"], r["init_deg"]) for r in rows})
REFS = ["grid map", "carte vectorielle", "entre scans (point-à-point)", "entre scans (point-à-droite)"]
ORDER = ["brute force", "multi-résolution", "Gauss-Newton", "ICP", "particules", "direct (murs)", "direct (moments)"]


def sel(jeu, ref, m, lv=None):
    return [r for r in rows if r["jeu"] == jeu and r["reference"] == ref and r["methode"] == m
            and (lv is None or (r["init_m"], r["init_deg"]) == lv)]


data = {"levels": [f"{d:.2f} m / {a:.0f}°".replace(".", ",") for d, a in levels], "comparaison": {}, "sensibilite": {},
        "n_cas": {}}
for jeu in ("simulation", "réel"):
    comp, sens = [], []
    for ref in REFS:
        for m in ORDER:
            g = sel(jeu, ref, m, levels[2])
            if not g:
                continue
            e = np.array([r["err_m"] for r in g]); a = np.array([r["err_deg"] for r in g])
            comp.append([ref, m, f"{np.mean([r['reussite'] for r in g]):.0%}",
                         f"{np.median(e) * 100:.1f}".replace(".", ","), f"{np.median(a):.2f}".replace(".", ","),
                         f"{np.mean([r['temps_ms'] for r in g]):.0f}"])
            sens.append([ref, m] + [f"{np.mean([r['reussite'] for r in sel(jeu, ref, m, lv)]):.0%}" for lv in levels])
        data["n_cas"][jeu] = len(sel(jeu, "grid map", "Gauss-Newton", levels[2]))
    data["comparaison"][jeu] = comp
    data["sensibilite"][jeu] = sens

# écart scan par scan (réel) et incertitude des références (lues dans la synthèse)
txt = (RES / "synthese.md").read_text(encoding="utf-8")
def md_table(title):
    block = txt.split(title, 1)[1].split("\n\n")
    lines = next(b for b in block if b.startswith("|")).splitlines()
    return [[c.strip() for c in l.strip("|").split("|")] for l in lines[2:]]
data["incertitude"] = md_table("### Incertitude des poses de référence")
data["par_scan"] = md_table("### Écart à la référence scan par scan")
data["seuils"] = [SUCCESS_XY, SUCCESS_TH]
(OUT.parent / "sources" / "donnees.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), "utf-8")

sizes = {p.name: list(Image.open(p).size) for p in sorted(OUT.glob("*.png"))}
(OUT / "_tailles.json").write_text(json.dumps(sizes), "utf-8")
print("figures :", ", ".join(sizes))
