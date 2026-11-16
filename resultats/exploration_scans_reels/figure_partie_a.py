"""Figure de la partie A : décisions de l'explorateur rejouées sur les 48 scans réels du 10/11."""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

here = Path(__file__).resolve().parent
out = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "version_1"
rows = json.loads((out / "partie_a.json").read_text("utf-8"))
z = np.load(here.parents[1] / "data/mesures_phase19_2026-11-09/carte_autoslam_v1/gridmap.npz")

lo = z["logodds"]; res = float(z["res"]); org = z["origin"]
p = 1 - 1 / (1 + np.exp(lo))
ext = (org[0], org[0] + lo.shape[1] * res, org[1], org[1] + lo.shape[0] * res)
fig, ax = plt.subplots(figsize=(8.5, 7.5))
ax.imshow(1 - p, cmap="gray", origin="lower", extent=ext, vmin=0, vmax=1)
col = {"sûre": "#2ca02c", "dangereuse": "#d62728"}
for r in rows:
    x, y, th = r["pose"]
    if r["mode"] == "aucune":
        ax.plot(x, y, "s", color="#7f7f7f", ms=7, mfc="none", mew=1.6)
        continue
    h = np.radians(th + r["turnDeg"]); c = col.get(r["decision"], "#1f77b4")
    ax.annotate("", xy=(x + 0.6 * np.cos(h), y + 0.6 * np.sin(h)), xytext=(x, y), arrowprops=dict(arrowstyle="-|>", color=c, lw=1.6))
    ax.plot(x, y, "o", color=c, ms=3)
n = {k: sum(r.get("decision") == k for r in rows) for k in ("sûre", "dangereuse")}
na = sum(r["mode"] == "aucune" for r in rows)
ax.set_title(f"Décisions rejouées sur les scans réels : {n['sûre']} sûres (vert), {n['dangereuse']} « dangereuses » (rouge),\n"
             f"{na} sans direction (carré gris) — flèche : direction et pas choisis (allongés pour la lecture)", fontsize=10)
ax.set_xlabel("x (m)"); ax.set_ylabel("y (m)"); ax.set_aspect("equal")
fig.tight_layout(); fig.savefig(out / "partie_a_decisions.png", dpi=130)
print("ok")
