"""Schéma d'architecture des deux outils (figure du rapport)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

fig, ax = plt.subplots(figsize=(15, 8.2))
ax.set_xlim(0, 15); ax.set_ylim(0, 8.3); ax.axis("off")

def box(x, y, w, h, title, lines, fc, ec="#1F4E79", tc="#1F4E79"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12", fc=fc, ec=ec, lw=1.6))
    ax.text(x + 0.15, y + h - 0.28, title, fontsize=10.5, fontweight="bold", color=tc, va="top")
    for i, l in enumerate(lines):
        ax.text(x + 0.18, y + h - 0.68 - i * 0.33, l, fontsize=8.6, va="top", family="DejaVu Sans")

def arrow(x1, y1, x2, y2, txt="", both=False):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="<|-|>" if both else "-|>", color="#555", lw=1.4))
    if txt:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, txt, fontsize=8, color="#444", ha="center")

# ---------------- outil 1
ax.add_patch(FancyBboxPatch((0.15, 0.15), 6.9, 7.6, boxstyle="round,pad=0.02,rounding_size=0.2", fc="#F4F7FB", ec="#1F4E79", lw=2))
ax.text(0.4, 7.55, "Outil 1 — carto (Python) : analyse, cartes, évaluation", fontsize=12.5, fontweight="bold", color="#1F4E79", va="top")
box(0.4, 5.55, 3.1, 1.6, "Données", ["scan.py : lecture LD06, Teleplot, poses", "simulate.py : scans simulés", "register.py : recalage global (FFT + ICP)"], "#FFFFFF")
box(3.75, 5.55, 3.1, 1.6, "Cartographie", ["gridmap.py : grid map log-odds", "segments.py : segments et opérations", "vectormap.py, build_map.py"], "#FFFFFF")
box(0.4, 3.35, 3.1, 1.9, "Localisation", ["localisation.py : 7 méthodes,", "  3 références (grid, vecteur, scan)", "localisation_globale.py", "evaluation.py : banc chiffré"], "#FFFFFF")
box(3.75, 3.35, 3.1, 1.9, "Interfaces", ["plot_app.py : Lidar Plot (temps réel)", "localise_dialog.py : fenêtre Localiser", "viewer.py, assistant.py", "__main__.py : ligne de commande"], "#FFFFFF")
box(0.4, 0.45, 6.45, 2.6, "Qualité et résultats", ["tests/ : 65 tests automatiques (pytest)", "resultats/ : évaluations, cartes des séances, démos", "rendu/ : comptes rendus, protocoles, rapport", "data/ : scans réels et simulés (jamais modifiés)", "arduino/ : programmes de l'ESP32 (versions 1 à 7, V5 retenue)"], "#FFFFFF")
arrow(3.5, 6.35, 3.75, 6.35)
arrow(2.0, 5.55, 2.0, 5.25)
arrow(5.3, 5.55, 5.3, 5.25)
# ---------------- outil 2
ax.add_patch(FancyBboxPatch((7.35, 0.15), 7.5, 7.6, boxstyle="round,pad=0.02,rounding_size=0.2", fc="#FFF8E7", ec="#B8860B", lw=2))
ax.text(7.6, 7.55, "Outil 2 — Lidar Lab (web + robot) : SLAM en direct", fontsize=12.5, fontweight="bold", color="#8a6100", va="top")
box(7.6, 5.4, 2.9, 1.75, "Robot", ["ESP32 + lidar LD06", "sketch V5 : Wi-Fi, /scan,", "/drive, /turn, /stop"], "#FFFFFF", ec="#B8860B", tc="#8a6100")
box(11.6, 5.4, 3.0, 1.75, "Serveur PC (Node.js)", ["serveur.js : séances, scans", "auto_slam.js : capture + recalage", "exploration.js : bonus"], "#FFFFFF", ec="#B8860B", tc="#8a6100")
box(11.6, 2.75, 3.0, 2.25, "Navigateur (PC)", ["index.html : interface", "lidar_core.js : grid map,", "  recalage, assemblage", "pilote_lidar_lab.js : pilotage", "demo_localisation.js"], "#FFFFFF", ec="#B8860B", tc="#8a6100")
box(7.6, 2.75, 2.9, 2.25, "Téléphone", ["telephone.html :", "pilotage et capture", "même séance que le PC"], "#FFFFFF", ec="#B8860B", tc="#8a6100")
box(7.6, 0.45, 7.0, 1.95, "Qualité", ["tests/ : 64 tests (node --test) : capture USB, serveur, assemblage,", "  faux positifs, exploration sur robot simulé", "docs/validation : protocoles et rapports de validation"], "#FFFFFF", ec="#B8860B", tc="#8a6100")
arrow(10.5, 6.3, 11.6, 6.3, "HTTP / Wi-Fi", both=True)
arrow(13.1, 5.4, 13.1, 5.0, "", both=True)
arrow(10.5, 4.6, 11.6, 5.55, "séance partagée", both=True)
arrow(9.05, 5.0, 9.05, 5.4, "", both=True)
ax.text(7.25, 8.05, "les deux outils lisent et écrivent les mêmes fichiers (scans CSV, poses JSON, grid map CSV)", fontsize=9, ha="center", color="#444")
fig.tight_layout()
fig.savefig("../figures/architecture_deux_outils.png", dpi=130)
print("ok")
