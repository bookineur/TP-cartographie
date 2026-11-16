"""Figure de la partie B : exploration SIMULÉE dans la salle réelle reconstruite."""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = Path(__file__).resolve().parent
out = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "version_1"
segs = np.loadtxt(here.parents[1] / "data/mesures_phase19_2026-11-09/carte_autoslam_v1/segments.csv", delimiter=",", skiprows=1)
fig, axes = plt.subplots(1, 3, figsize=(16, 5.6))
for ax, n in zip(axes, (1, 20, 40)):
    r = json.loads((out / f"partie_b_depart{n}.json").read_text("utf-8"))
    for s in segs:
        ax.plot([s[0], s[2]], [s[1], s[3]], color="#1F4E79", lw=1)
    tr = np.array(r["trajet_vrai"]); es = np.array(r["poses_recalees"]); t0 = tr[0]
    c, s_ = np.cos(np.radians(t0[2])), np.sin(np.radians(t0[2]))
    ew = np.column_stack([t0[0] + c * es[:, 0] - s_ * es[:, 1], t0[1] + s_ * es[:, 0] + c * es[:, 1]])
    ax.plot(tr[:, 0], tr[:, 1], "-", color="#2ca02c", lw=1.1, label="vraie trajectoire (simulée)")
    ax.plot(ew[:, 0], ew[:, 1], "x", color="#d62728", ms=3, label="poses recalées")
    ax.plot(*tr[0, :2], "ks", ms=7)
    ax.set_title(f"départ scan {n} : {r['pas']} pas, {r['distance_m']:.0f} m, couverture {r['couverture']*100:.0f} %\n"
                 f"erreur max {r['erreur_pos_max_m']*100:.0f} cm / {r['erreur_angle_max_deg']:.1f}°, "
                 f"collision : {'oui' if r['collision'] else 'non'}", fontsize=9.5)
    ax.set_aspect("equal"); ax.set_xlim(-13, 3); ax.set_ylim(-5, 10)
axes[0].legend(loc="lower left", fontsize=8)
fig.suptitle("Exploration automatique SIMULÉE dans la salle réelle du 10/11 reconstruite (murs = carte vectorielle brute, 166 segments)", fontsize=11)
fig.tight_layout(); fig.savefig(out / "partie_b_exploration.png", dpi=120, bbox_inches="tight")
print("ok")
