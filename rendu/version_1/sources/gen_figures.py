"""Figures du compte rendu, à partir des données réelles de la session."""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, r"C:\Users\HP\TP-cartographie")
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from carto import theme
from carto.gridmap import OccupancyGrid
from carto.register import clean_scan
from carto.scan import load_poses, load_scan_file
from carto.segments import Segment, angle_between, are_close, cut, extract_segments, intersection, merge
from carto.theme import C, SCAN_COLORS

ROOT = Path(r"C:\Users\HP\TP-cartographie")
SESS = ROOT / r"data\salle_2026-11-02_18h31"
V2 = SESS / r"carte\version_2"
OUT = ROOT / r"rendu\version_1\figures"
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.titleweight": "bold", "axes.titlesize": 11})

# --- copies des cartes (version 2)
for n in ("1_assemblage.png", "2_grid_map.png", "3_carte_vectorielle.png", "4_scans_ecartes.png"):
    shutil.copy(V2 / n, OUT / n)

# --- photos de la salle (webp -> png)
IMG = Path(sys.argv[1])
for k, name in ((5, "photo_salle_1.png"), (4, "photo_salle_2.png")):
    Image.open(IMG / f"{k}.webp").convert("RGB").save(OUT / name)

# --- 1. un scan : polaire puis cartésien
s = load_scan_file(SESS / "scan1.csv")[0]
f = s.filtered()
fig = plt.figure(figsize=(12, 5.2))
ax = fig.add_subplot(121, projection="polar")
ax.scatter(f.angles, f.ranges, s=3, color=C["pose"])
ax.set_title("scan1 en coordonnées polaires (θ, r)", pad=18)
ax2 = fig.add_subplot(122)
xy = f.local_xy()
ax2.scatter(xy[:, 0], xy[:, 1], s=3, color=SCAN_COLORS[0])
ax2.plot(0, 0, ">", ms=10, color=C["pose"])
ax2.set_aspect("equal"); ax2.grid(alpha=.3)
ax2.set_xlabel("x (m)"); ax2.set_ylabel("y (m)")
ax2.set_title("même scan en cartésien : x = r·cos θ, y = r·sin θ")
fig.tight_layout(); fig.savefig(OUT / "fig_scan_polaire_cartesien.png", dpi=130); plt.close(fig)

# --- 3. grid map construite scan après scan (session assemblée, version 2)
sa = V2 / "session_assemblee"
poses = load_poses(sa / "poses.json")
order = ["scan3", "scan1", "scan2", "scan4", "scan5", "scan6", "scan7", "scan8", "scan9"]
scans = {n: clean_scan(load_scan_file(sa / f"{n}.csv")[0]) for n in order}
grid = None
snaps = {}
for k, n in enumerate(order, 1):
    if grid is None:
        grid = OccupancyGrid.from_scan(scans[n], poses[n], 0.05)
    else:
        grid.update(scans[n], poses[n])
    if k in (1, 3, 9):
        snaps[k] = (grid.probability().copy(), grid.extent)
fig, axs = plt.subplots(1, 3, figsize=(15, 5.4))
for ax, (k, (p, ext)) in zip(axs, snaps.items()):
    ax.imshow(p, cmap=theme.OCC_CMAP, origin="lower", vmin=0, vmax=1, extent=ext, interpolation="nearest")
    for n in order[:k]:
        ax.plot(poses[n].x, poses[n].y, "o", ms=5, color=C["pose"], mec="white")
    ax.set_title(("1 scan : OccupancyGrid.from_scan" if k == 1 else f"après {k} scans : grid.update"))
    ax.set_xlim(-5, 11); ax.set_ylim(-5, 11); ax.set_aspect("equal")
fig.tight_layout(); fig.savefig(OUT / "fig_grid_etapes.png", dpi=110); plt.close(fig)

# --- 4. opérations sur les segments
fig, axs = plt.subplots(2, 3, figsize=(15, 9.5))
# a) extraction sur scan1 réel
ax = axs[0, 0]
c1 = clean_scan(s)
pts = c1.local_xy()
segs = extract_segments(pts)
ax.scatter(pts[:, 0], pts[:, 1], s=3, color="#94A3B8")
for sg in segs:
    ax.plot([sg.p1[0], sg.p2[0]], [sg.p1[1], sg.p2[1]], color=C["error"], lw=2.2)
ax.set_title(f"a) nuage → {len(segs)} segments (scan1)"); ax.set_aspect("equal"); ax.grid(alpha=.3)


def draw(ax, segments, colors, title, labels=None):
    for i, (sg, col) in enumerate(zip(segments, colors)):
        ax.plot([sg.p1[0], sg.p2[0]], [sg.p1[1], sg.p2[1]], color=col, lw=3, solid_capstyle="round")
        ax.plot(*sg.p1, "o", color=col, ms=5)
        if labels:
            ax.text(*(sg.midpoint + [0.05, 0.12]), labels[i], color=col, fontsize=10, weight="bold")
    ax.set_title(title); ax.set_aspect("equal"); ax.grid(alpha=.3)


# b) angle
A, B = Segment((0, 0), (3, 0)), Segment((0.5, 0.2), (2.6, 1.4))
draw(axs[0, 1], [A, B], [C["pose"], C["warn"]],
     f"b) angle entre droites : {np.degrees(angle_between(A, B)):.1f}°", ["A", "B"])
# c) proches / pas proches
A, B, Cc = Segment((0, 0), (2, 0)), Segment((2.08, 0.03), (3.5, 0.05)), Segment((0.5, 0.6), (2.5, 0.65))
draw(axs[0, 2], [A, B, Cc], [C["pose"], C["ok"], C["error"]],
     f"c) A-B proches : {'oui' if are_close(A, B) else 'non'} ; A-C : {'oui' if are_close(A, Cc) else 'non'}",
     ["A", "B", "C"])
axs[0, 2].set_ylim(-0.5, 1.2)
# d) fusion
M = merge(A, B)
draw(axs[1, 0], [A, B], [C["pose"], C["ok"]], "d) fusion de A et B (en noir)", ["A", "B"])
axs[1, 0].plot([M.p1[0], M.p2[0]], [M.p1[1] - 0.25, M.p2[1] - 0.25], color="k", lw=3)
axs[1, 0].set_ylim(-0.6, 0.6)
# e) intersection
A, B = Segment((0, 0), (3, 2)), Segment((0, 2), (3, 0))
X = intersection(A, B)
draw(axs[1, 1], [A, B], [C["pose"], C["warn"]], f"e) intersection en ({X[0]:.2f}, {X[1]:.2f})")
axs[1, 1].text(2.75, 1.65, "A", color=C["pose"], fontsize=11, weight="bold")
axs[1, 1].text(2.75, 0.25, "B", color=C["warn"], fontsize=11, weight="bold")
axs[1, 1].plot(*X, "*", ms=16, color=C["error"])
# f) découpe : garde le plus long côté
T, K = Segment((0, 0), (4, 0)), Segment((1.2, -0.8), (1.2, 0.8))
R, done = cut(T, K)
draw(axs[1, 2], [T, K], ["#CBD5E1", C["warn"]], "f) découpe de T par K : on garde le plus long côté",
     ["T (avant)", "K"])
axs[1, 2].plot([R.p1[0], R.p2[0]], [R.p1[1] - 0.15, R.p2[1] - 0.15], color=C["pose"], lw=4)
axs[1, 2].text(2.2, -0.45, "T après découpe", color=C["pose"], weight="bold")
axs[1, 2].set_ylim(-1, 1)
fig.tight_layout(); fig.savefig(OUT / "fig_segments_operations.png", dpi=110); plt.close(fig)
print("ok", sorted(p.name for p in OUT.iterdir()))
