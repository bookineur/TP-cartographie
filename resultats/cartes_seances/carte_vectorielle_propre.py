"""Carte vectorielle « propre » de la séance du 10/11 : uniquement les segments de la carte fusionnée
(58 segments vus au moins 2 fois, murs proches fusionnés), salle tournée pour aligner les murs sur les axes,
quadrillage d'un mètre et échelle. Aucun segment n'est retiré ni déplacé ; seule la vue est tournée.
Lancer : python resultats/cartes_seances/carte_vectorielle_propre.py"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
SEG = ROOT / "data/mesures_phase19_2026-11-09/carte_autoslam_v1_fusionnee/segments.csv"
a = np.loadtxt(SEG, delimiter=",", skiprows=1)
P1, P2, L, N = a[:, 0:2], a[:, 2:4], a[:, 4], a[:, 5]
th = np.arctan2(P2[:, 1] - P1[:, 1], P2[:, 0] - P1[:, 0])
rot = -np.angle(np.sum(L * np.exp(4j * th))) / 4          # rotation qui aligne les murs sur les axes
R = np.array([[np.cos(rot), -np.sin(rot)], [np.sin(rot), np.cos(rot)]])
Q1, Q2 = P1 @ R.T, P2 @ R.T
lng = L >= 1.0                                             # murs longs : pour mesurer la salle
xs = np.concatenate([Q1[lng, 0], Q2[lng, 0]]); ys = np.concatenate([Q1[lng, 1], Q2[lng, 1]])
x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()

out = Path(__file__).resolve().parent
n = 1
while (out / f"version_{n}").exists():
    n += 1
out = out / f"version_{n}"; out.mkdir()

for nom, fond, trait, grille, texte in [("claire", "white", "#1F4E79", "#e3e8ef", "#333333"),
                                        ("sombre", "#0c1118", "#8fd3ff", "#1d2733", "#c8d3df")]:
    fig, ax = plt.subplots(figsize=(10, 9.2), facecolor=fond)
    ax.set_facecolor(fond)
    for q1, q2, nobs in zip(Q1, Q2, N):
        ax.plot([q1[0], q2[0]], [q1[1], q2[1]], "-", color=trait, lw=1.4 + 3.6 * (nobs / N.max()) ** 0.5, solid_capstyle="round")
    ax.set_xlim(x0 - 1.2, x1 + 1.2); ax.set_ylim(y0 - 1.6, y1 + 1.2); ax.set_aspect("equal")
    ax.set_xticks(np.arange(np.floor(x0 - 1), np.ceil(x1 + 1) + 1, 1)); ax.set_yticks(np.arange(np.floor(y0 - 1), np.ceil(y1 + 1) + 1, 1))
    ax.grid(color=grille, lw=0.8); ax.set_axisbelow(True)
    ax.tick_params(colors=texte, labelsize=8, length=0); [s.set_visible(False) for s in ax.spines.values()]
    ax.set_xticklabels([]); ax.set_yticklabels([])
    # cotes de la salle (murs longs)
    yb = y0 - 0.8
    ax.annotate("", xy=(x0, yb), xytext=(x1, yb), arrowprops=dict(arrowstyle="<->", color=texte, lw=1.2))
    ax.text((x0 + x1) / 2, yb - 0.35, f"{x1 - x0:.1f} m", ha="center", va="top", color=texte, fontsize=11)
    xb = x1 + 0.7
    ax.annotate("", xy=(xb, y0), xytext=(xb, y1), arrowprops=dict(arrowstyle="<->", color=texte, lw=1.2))
    ax.text(xb + 0.25, (y0 + y1) / 2, f"{y1 - y0:.1f} m", ha="left", va="center", color=texte, fontsize=11, rotation=90)
    # échelle de 2 m
    ax.plot([x0, x0 + 2], [y1 + 0.7, y1 + 0.7], "-", color=texte, lw=3)
    ax.text(x0 + 1, y1 + 0.85, "2 m", ha="center", va="bottom", color=texte, fontsize=10)
    ax.set_title(f"Carte vectorielle de la salle — séance du robot du 10/11\n{len(L)} segments ({L.sum():.0f} m), vus au moins 2 fois ; épaisseur : nombre d'observations ; quadrillage : 1 m",
                 color=texte, fontsize=11)
    fig.tight_layout()
    fig.savefig(out / f"carte_vectorielle_propre_10_11_{nom}.png", dpi=140, facecolor=fond)
    plt.close(fig)
(out / "LISEZMOI.md").write_text(
    "# Carte vectorielle propre — séance du 10/11\n\n"
    f"Source : `{SEG.relative_to(ROOT).as_posix()}` (non modifié) : {len(L)} segments, {L.sum():.1f} m.\n\n"
    f"Seule la vue change : rotation de {np.degrees(rot):+.1f}° pour aligner les murs sur les axes, quadrillage d'un mètre, "
    "échelle et cotes de la salle (calculées sur les murs de plus de 1 m). Aucun segment n'est retiré ni déplacé.\n\n"
    f"Dimensions mesurées sur la carte : {x1 - x0:.1f} m × {y1 - y0:.1f} m.\n", "utf-8")
print(out, f"rotation {np.degrees(rot):+.1f}°, salle {x1 - x0:.1f} x {y1 - y0:.1f} m")
