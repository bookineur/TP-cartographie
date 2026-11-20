"""Cartes « titre », « algorithme » et « code » ajoutées en tête de la vidéo de localisation (1920 x 1080).
Le code présenté est celui de lidar_core.js (locateScanOnGrid, chooseCandidate), simplifié pour la lecture.
Usage : python cartes_localisation.py <dossier_sortie>"""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
FOND, PANNEAU, TXT, GRIS, JAUNE = "#0b1017", "#121a24", "#e8eef6", "#8a99ab", "#f2c94c"
BANDEAU = "Lidar Lab — localisation d'un scan sur la grid map"


def base(titre, sous):
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(FOND)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0, 0.9), 1, 0.1, boxstyle="square,pad=0", fc="#1F4E79", ec="none"))
    ax.text(0.5, 0.95, BANDEAU, color="white", fontsize=22, fontweight="bold", ha="center", va="center")
    ax.text(0.05, 0.84, titre, color=TXT, fontsize=30, fontweight="bold", va="center")
    ax.text(0.05, 0.79, sous, color=GRIS, fontsize=15, va="center")
    return fig, ax


def blocs(ax, liste, y=0.72):
    for st, lignes in liste:
        if st:
            ax.text(0.05, y, st, color=JAUNE, fontsize=15, fontweight="bold", va="center"); y -= 0.04
        h = 0.032 * len(lignes) + 0.02
        ax.add_patch(FancyBboxPatch((0.05, y - h + 0.017), 0.9, h, boxstyle="round,pad=0.004,rounding_size=0.008", fc=PANNEAU, ec="#26364a", lw=1.2))
        for l in lignes:
            c = "#7f8ea0" if l.strip().startswith(("//", "#")) else TXT
            ax.text(0.065, y, l, color=c, fontsize=14, family="DejaVu Sans Mono", va="center"); y -= 0.032
        y -= 0.045


def save(fig, nom):
    fig.savefig(OUT / nom, dpi=100, facecolor=FOND); plt.close(fig)


# 1. titre
fig, ax = base("", "")
ax.text(0.5, 0.74, "Où le robot a-t-il pris ce scan ?", color=TXT, fontsize=40, fontweight="bold", ha="center", va="center")
ax.text(0.5, 0.65, "Localisation globale sur la grid map, sans position de départ", color=GRIS, fontsize=18, ha="center", va="center")
for k, l in enumerate(["1.  On tire un scan au hasard et on le retire de la carte",
                       "2.  On cherche sa position sur toute la grid map, sur 360°",
                       "3.  On garde la meilleure position, sauf si elle est douteuse",
                       "4.  On compare avec la position enregistrée par l'Auto-SLAM"]):
    ax.text(0.14, 0.53 - 0.085 * k, l, color=TXT, fontsize=22, va="center")
save(fig, "L00_titre.png")

# 2. algorithme
fig, ax = base("L'algorithme : recherche exhaustive, puis affinage",
               "Méthodes du cours (Jour 2). Score d'une pose : distance de chaque point du scan au mur le plus proche ; plus elle est petite, meilleure est la pose")
blocs(ax, [(None, [
    "carte_des_distances <- pour chaque cellule, distance au mur le plus proche (deux passes sur la grille)",
    "pour x, y dans toute la carte (pas de 20 cm) et θ de -180° à 180° (pas de 15°) :      recherche exhaustive",
    "    coût(x, y, θ) <- moyenne des (distance au mur)² des points du scan placés à cette pose",
    "candidats <- les 5 meilleures poses distinctes (+ 5 avec un coût plafonné à 50 cm)",
    "pour chaque candidat : affiner autour (pas de 5 cm et 3°, puis 2,5 cm et 0,5°)        multi-résolution",
    "recouvrement p <- part des points du scan à moins de 10 cm d'un mur",
    "meilleure <- le candidat de plus petit coût",
    "si un candidat éloigné (> 60 cm ou > 23°) est presque aussi bon : REFUS (position ambiguë)",
    "sinon si p < 35 % : REFUS (trop peu de points sur des murs connus)",
    "sinon : ACCEPTÉE -> position (x, y, θ) du robot"])])
save(fig, "L01_algorithme.png")

# 3. code
fig, ax = base("Le code : lidar_core.js (locateScanOnGrid, chooseCandidate)",
               "Extraits du code exécuté par la démo, simplifiés pour la lecture (noms et calculs inchangés, commentaires résumés)")
blocs(ax, [("Le score d'une pose : distances des points au mur le plus proche", [
    "function score(x, y, a, pts) {",
    "  let sum = 0;",
    "  for (const p of pts) { const d = distanceAt(x, y, a, p); sum += d * d; }  // d lu dans la carte des distances",
    "  return sum / pts.length;",
    "}"]),
    ("La recherche exhaustive sur toute la carte", [
    "for (let x = lx0; x <= lx1; x += cStep)              // cStep = 20 cm",
    "  for (let y = ly0; y <= ly1; y += cStep)",
    "    for (let deg = la0; deg <= la1; deg += dStep)    // dStep = 15°",
    "      keep(topFull, { x, y, a: deg * Math.PI / 180, cost: score(x, y, deg * Math.PI / 180) }, 5);"]),
    ("La décision : accepter ou refuser", [
    "const far = (q) => Math.hypot(q.x - best.x, q.y - best.y) > 0.6 || angleDiff(q.a, best.a) > 0.4;",
    "rival = pool.find((q) => far(q) && q.overlap >= best.overlap - delta);   // delta = 2·sqrt(p(1-p)/N)",
    "let ok = !ambiguous && best.overlap >= o.minOverlap;                      // minOverlap = 0,35"])], y=0.70)
save(fig, "L02_code.png")
print("ok")
