"""Grid map « propre » de la séance du 10/11 : la carte d'occupation seule (sans points ni noms de scans),
calculée avec carto.gridmap à partir des 48 scans et de leurs poses Auto-SLAM, dans un repère tourné pour
aligner les murs sur les axes (même rotation que la carte vectorielle propre), cadrée sur la salle, avec un
quadrillage d'un mètre, une échelle et les cotes. Les scans et les poses ne sont pas modifiés.
Lancer : python resultats/cartes_seances/grid_map_propre.py"""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from carto.scan import Pose, load_scans  # noqa: E402
from carto.register import clean_scan  # noqa: E402
from carto.gridmap import build_grid  # noqa: E402

SEANCE = ROOT / "data/mesures_phase19_2026-11-09/capture/seance_2026-11-09_13h06m10"
SEG = ROOT / "data/mesures_phase19_2026-11-09/carte_autoslam_v1_fusionnee/segments.csv"
# rotation qui aligne les murs (calculée sur la carte vectorielle fusionnée, comme pour la carte vectorielle propre)
a = np.loadtxt(SEG, delimiter=",", skiprows=1)
L = a[:, 4]; th = np.arctan2(a[:, 3] - a[:, 1], a[:, 2] - a[:, 0])
rot = -np.angle(np.sum(L * np.exp(4j * th))) / 4
c, s = np.cos(rot), np.sin(rot)
R = np.array([[c, -s], [s, c]])
# cotes de la salle : murs de plus de 1 m de la carte vectorielle, dans le repère tourné
lng = L >= 1.0
E = np.vstack([a[lng, 0:2], a[lng, 2:4]]) @ R.T
x0, x1, y0, y1 = E[:, 0].min(), E[:, 0].max(), E[:, 1].min(), E[:, 1].max()

j = json.loads((SEANCE / "seance.json").read_text("utf-8"))
poses = {}
for e in j["scans"]:
    if e.get("reg"):
        x, y, d = e["pose"]
        q = R @ np.array([x, y])
        poses[e["name"][:-4]] = Pose(float(q[0]), float(q[1]), float(np.radians(d) + rot))  # même pose, repère tourné
files = [f for f in sorted(SEANCE.glob("scan*.csv")) if f.stem in poses]
pairs = [(cs, poses[cs.name]) for cs in (clean_scan(sc) for sc in load_scans(files))]
g = build_grid(pairs, 0.05)
p = g.probability()
ext = g.extent

out = Path(__file__).resolve().parent
n = 1
while (out / f"version_{n}").exists():
    n += 1
out = out / f"version_{n}"; out.mkdir()
for nom, fond, occ, libre, inconnu, grille, texte in [("claire", "white", 0.0, 1.0, 0.82, "#c9d3df", "#333333"),
                                                     ("sombre", "#0c1118", 0.95, 0.22, 0.05, "#2a3747", "#c8d3df")]:
    img = np.full(p.shape, inconnu)
    img[p < 0.35] = libre
    img[p > 0.65] = occ
    fig, ax = plt.subplots(figsize=(10, 9.2), facecolor=fond)
    ax.set_facecolor(fond)
    ax.imshow(img, cmap="gray", origin="lower", extent=ext, vmin=0, vmax=1, interpolation="nearest")
    ax.set_xlim(x0 - 1.2, x1 + 1.2); ax.set_ylim(y0 - 1.6, y1 + 1.2); ax.set_aspect("equal")
    ax.set_xticks(np.arange(np.floor(x0 - 1), np.ceil(x1 + 1) + 1, 1)); ax.set_yticks(np.arange(np.floor(y0 - 1), np.ceil(y1 + 1) + 1, 1))
    ax.grid(color=grille, lw=0.6, alpha=0.7)
    ax.tick_params(length=0); ax.set_xticklabels([]); ax.set_yticklabels([])
    [sp.set_visible(False) for sp in ax.spines.values()]
    yb = y0 - 0.8
    ax.annotate("", xy=(x0, yb), xytext=(x1, yb), arrowprops=dict(arrowstyle="<->", color=texte, lw=1.2))
    ax.text((x0 + x1) / 2, yb - 0.35, f"{x1 - x0:.1f} m", ha="center", va="top", color=texte, fontsize=11)
    xb = x1 + 0.7
    ax.annotate("", xy=(xb, y0), xytext=(xb, y1), arrowprops=dict(arrowstyle="<->", color=texte, lw=1.2))
    ax.text(xb + 0.25, (y0 + y1) / 2, f"{y1 - y0:.1f} m", ha="left", va="center", color=texte, fontsize=11, rotation=90)
    ax.plot([x0, x0 + 2], [y1 + 0.7, y1 + 0.7], "-", color=texte, lw=3)
    ax.text(x0 + 1, y1 + 0.85, "2 m", ha="center", va="bottom", color=texte, fontsize=10)
    leg = "noir : occupé · blanc : libre · gris : inconnu" if nom == "claire" else "blanc : occupé · bleu-gris : libre · noir : inconnu"
    ax.set_title(f"Grid map de la salle — séance du robot du 10/11\n{len(pairs)} scans, cellules de 5 cm ; {leg} ; quadrillage : 1 m", color=texte, fontsize=11)
    if nom == "sombre":
        ax.images[0].set_cmap(matplotlib.colors.LinearSegmentedColormap.from_list("s", ["#0c1118", "#28445a", "#f4f7fb"]))
    fig.tight_layout()
    fig.savefig(out / f"grid_map_propre_10_11_{nom}.png", dpi=140, facecolor=fond)
    plt.close(fig)
(out / "LISEZMOI.md").write_text(
    "# Grid map propre — séance du 10/11\n\n"
    f"Calculée avec `carto.gridmap` (cellules de 5 cm, log-odds) à partir des {len(pairs)} scans recalés de "
    f"`{SEANCE.relative_to(ROOT).as_posix()}` et de leurs poses Auto-SLAM (non modifiés). Le repère est tourné de "
    f"{np.degrees(rot):+.1f}° pour aligner les murs sur les axes (même rotation que la carte vectorielle propre). "
    "Aucun point ni nom de scan n'est affiché ; cotes mesurées sur les murs de plus de 1 m de la carte vectorielle "
    f"fusionnée : {x1 - x0:.1f} m × {y1 - y0:.1f} m.\n", "utf-8")
print(out, f"rotation {np.degrees(rot):+.1f}°, {len(pairs)} scans")
