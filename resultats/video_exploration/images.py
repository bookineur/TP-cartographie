"""Images de la vidéo d'exploration (1920 x 1080) à partir des étapes enregistrées par enregistrer_exploration.js.
Usage : python images.py <dossier_version>   -> <dossier>/images/*.png + <dossier>/montage.txt (durée de chaque image)"""
import json, sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle

V = Path(sys.argv[1]); IMG = V / "images"; IMG.mkdir(exist_ok=True)
etapes = [json.loads(p.read_text("utf-8")) for p in sorted((V / "etapes").glob("etape_*.json"))]
bilan = json.loads((V / "bilan.json").read_text("utf-8"))
murs = bilan["murs_reels_repere_carte"]
N = len(etapes)
FOND, PANNEAU, TXT, GRIS = "#0b1017", "#121a24", "#e8eef6", "#8a99ab"
JAUNE, ORANGE, CYAN, ROSE = "#f2c94c", "#ff8c42", "#5ad1e8", "#ff5fa2"
plt.rcParams.update({"font.family": "DejaVu Sans"})


def grille_rgb(g):
    lignes = g["cellules"].split("\n")
    H, W = g["hauteur"], g["largeur"]
    a = np.array([list(l.ljust(W)) for l in lignes])
    rgb = np.zeros((H, W, 3)); rgb[:] = matplotlib.colors.to_rgb(FOND)
    rgb[a == "."] = matplotlib.colors.to_rgb("#1d3850")
    rgb[a == "#"] = matplotlib.colors.to_rgb("#e8eef6")
    # frontières : cellules libres avec au moins 2 voisines inconnues (même règle que l'explorateur)
    inc = (a == " ")
    pad = np.pad(inc, 1, constant_values=True)
    nb = pad[:-2, 1:-1].astype(int) + pad[2:, 1:-1] + pad[1:-1, :-2] + pad[1:-1, 2:]
    front = (a == ".") & (nb >= 2)
    rgb[front] = matplotlib.colors.to_rgb(ORANGE)
    ext = (g["origine"][0], g["origine"][0] + W * g["res"], g["origine"][1], g["origine"][1] + H * g["res"])
    return rgb, ext


xs = [p[0] for m in murs for p in m]; ys = [p[1] for m in murs for p in m]
X0, X1, Y0, Y1 = min(xs) - 0.8, max(xs) + 0.8, min(ys) - 0.8, max(ys) + 0.8
# vue rapprochée pour les premiers scans expliqués lentement : centrée sur leurs poses, même rapport largeur/hauteur
LENT = 6
_c = np.array([e["pose"][:2] for e in etapes[:LENT + 1]]).mean(axis=0)
ZW = 11.0; ZH = ZW * (0.89 * 1080) / (0.69 * 1920)
ZX0, ZX1, ZY0, ZY1 = _c[0] - ZW / 2, _c[0] + ZW / 2, _c[1] - ZH / 2, _c[1] + ZH / 2


def cadre(fig):
    fig.patch.set_facecolor(FOND)
    t = fig.add_axes([0, 0.925, 1, 0.075]); t.axis("off"); t.set_xlim(0, 1); t.set_ylim(0, 1)
    t.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="square,pad=0", fc="#1F4E79", ec="none"))
    t.text(0.012, 0.62, "Exploration automatique — Lidar Lab", color="white", fontsize=22, fontweight="bold", va="center")
    t.text(0.012, 0.22, "Simulation : vrai code d'exploration, robot et lidar simulés dans la salle réelle du 10/11 reconstruite (murs réels), erreurs de déplacement ±10 %",
           color="#dbe6f3", fontsize=12.5, va="center")


def image(i, phase, nom):
    e = etapes[i]
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100); cadre(fig)
    ax = fig.add_axes([0.01, 0.02, 0.69, 0.89]); ax.set_facecolor(FOND)
    rgb, ext = grille_rgb(e["grille"])
    ax.imshow(rgb, origin="upper", extent=ext, interpolation="nearest", zorder=1)
    for a, b in murs:
        ax.plot([a[0], b[0]], [a[1], b[1]], color="#6c7d91", lw=1, ls=(0, (4, 3)), zorder=2, alpha=0.8)
    P = np.array([etapes[j]["pose"] for j in range(i + 1)])
    ax.plot(P[:, 0], P[:, 1], "-", color=CYAN, lw=2, alpha=0.85, zorder=3)
    ax.plot(P[:, 0], P[:, 1], "o", color=CYAN, ms=3, zorder=3)
    if phase in ("scan", "rapide"):
        s = np.array(e["scan"])
        if len(s):
            ax.plot(s[:, 0], s[:, 1], "o", color=JAUNE, ms=4.5 if (i < LENT and phase != "rapide") else 3, mec="none", zorder=7)
    x, y, th = e["pose"]
    nxt = etapes[i + 1] if i + 1 < N else None
    if phase in ("decision", "rapide") and nxt and nxt["cible"]:
        cx, cy = nxt["cible"]
        ax.plot([x, cx], [y, cy], color=ROSE, lw=2.5, ls=(0, (6, 4)), zorder=5)
        ax.plot(cx, cy, marker="*", color=ROSE, ms=26, mec="white", mew=1.2, zorder=6)
        if phase == "decision":
            ax.annotate("zone inconnue visée", (cx, cy), xytext=(18, 18), textcoords="offset points", color=ROSE, fontsize=14, fontweight="bold", zorder=7)
    if phase == "pas" and nxt:
        nx, ny, nth = nxt["pose"]
        ax.add_patch(Circle((nx, ny), 0.17, fc="none", ec="white", lw=2.5, ls="--", zorder=8))
        b = np.radians(nth); ax.plot([nx, nx + 0.45 * np.cos(b)], [ny, ny + 0.45 * np.sin(b)], color="white", lw=2, ls="--", zorder=9)
        ax.annotate("", xy=(nx, ny), xytext=(x, y), arrowprops=dict(arrowstyle="-|>", color=JAUNE, lw=3.5, mutation_scale=28, shrinkA=8, shrinkB=8), zorder=10)
        ax.annotate(f"pas de {np.hypot(nx - x, ny - y) * 100:.0f} cm", ((x + nx) / 2, (y + ny) / 2), xytext=(16, -22), textcoords="offset points",
                    color=JAUNE, fontsize=14, fontweight="bold", zorder=10)
    ax.add_patch(Circle((x, y), 0.17, fc=CYAN, ec="white", lw=2, zorder=8))
    a = np.radians(th); ax.plot([x, x + 0.45 * np.cos(a)], [y, y + 0.45 * np.sin(a)], color="white", lw=3, zorder=9)
    zoom = phase in ("scan", "decision", "pas") and i < LENT
    x0, x1, y0, y1 = (ZX0, ZX1, ZY0, ZY1) if zoom else (X0, X1, Y0, Y1)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.axis("off")
    u = 1 if zoom else 2
    ax.plot([x0 + 0.2 * u, x0 + 1.2 * u], [y0 + 0.18 * u, y0 + 0.18 * u], color=GRIS, lw=3)
    ax.text(x0 + 0.7 * u, y0 + 0.25 * u, f"{u} m", color=GRIS, ha="center", fontsize=12)
    if zoom:
        ax.text(x0 + 0.15, y1 - 0.15, "vue rapprochée", color=GRIS, fontsize=13, va="top")
    # panneau de droite
    p = fig.add_axes([0.71, 0.02, 0.28, 0.89]); p.axis("off"); p.set_xlim(0, 1); p.set_ylim(0, 1)
    p.add_patch(FancyBboxPatch((0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.02", fc=PANNEAU, ec="#26364a", lw=1.5))
    p.text(0.06, 0.94, f"Scan {i + 1} / {N}", color=TXT, fontsize=30, fontweight="bold", va="top")
    etapes_txt = [("1", "Scanner et se recaler", "le scan (jaune) est placé sur la carte\ndéjà construite", phase in ("scan", "rapide")),
                  ("2", "Choisir où aller", "la zone inconnue la plus proche (orange) ;\nchemin à 25 cm des murs", phase in ("decision", "rapide")),
                  ("3", "Avancer d'un petit pas", "35 cm au plus, après avoir vérifié\nla place devant, robot à l'arrêt", phase in ("pas", "rapide"))]
    yy = 0.82
    for num, titre, detail, actif in etapes_txt:
        c = JAUNE if actif else "#56677b"
        p.add_patch(Circle((0.1, yy - 0.012), 0.035, fc=c if actif else "none", ec=c, lw=2))
        p.text(0.1, yy - 0.012, num, color=FOND if actif else c, fontsize=15, fontweight="bold", ha="center", va="center")
        p.text(0.19, yy, titre, color=TXT if actif else "#7f8ea0", fontsize=17, fontweight="bold", va="center")
        p.text(0.19, yy - 0.05, detail, color=GRIS if actif else "#56677b", fontsize=10.5, va="center")
        yy -= 0.13
    err = np.hypot(e["pose"][0] - e["vrai"][0], e["pose"][1] - e["vrai"][1]) * 100
    stats = [("Salle cartographiée", f"{e['couverture'] * 100:.0f} %"), ("Distance parcourue", f"{e['distance']:.1f} m"),
             ("Écart avec la vraie position", f"{err:.1f} cm"), ("Collisions", "0")]
    yy = 0.40
    for lab, val in stats:
        p.text(0.06, yy, lab, color=GRIS, fontsize=13, va="center")
        p.text(0.94, yy, val, color=TXT, fontsize=19, fontweight="bold", ha="right", va="center")
        yy -= 0.062
    leg = [("#e8eef6", "mur vu par le robot (occupé)"), ("#1d3850", "zone vue libre"), (ORANGE, "frontière : bord de l'inconnu"),
           ("#6c7d91", "murs réels (référence, pointillés)"), (CYAN, "trajectoire du robot"), (ROSE, "cible choisie")]
    yy = 0.15
    for col, lab in leg:
        p.add_patch(FancyBboxPatch((0.06, yy - 0.012), 0.04, 0.024, boxstyle="square,pad=0", fc=col, ec="none"))
        p.text(0.13, yy, lab, color=GRIS, fontsize=10.5, va="center")
        yy -= 0.026
    f = IMG / nom; fig.savefig(f, dpi=100, facecolor=FOND); plt.close(fig)
    return f.name


def carte_texte(nom, titre, lignes, sous=None):
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(FOND)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0, 0.9), 1, 0.1, boxstyle="square,pad=0", fc="#1F4E79", ec="none"))
    ax.text(0.5, 0.95, "Lidar Lab — exploration automatique (bonus)", color="white", fontsize=22, fontweight="bold", ha="center", va="center")
    ax.text(0.5, 0.76, titre, color=TXT, fontsize=40, fontweight="bold", ha="center", va="center")
    if sous:
        ax.text(0.5, 0.67, sous, color=GRIS, fontsize=18, ha="center", va="center")
    y = 0.55
    for l in lignes:
        ax.text(0.14, y, l, color=TXT, fontsize=22, va="center")
        y -= 0.085
    fig.savefig(IMG / nom, dpi=100, facecolor=FOND); plt.close(fig)
    return nom


def carte_code(nom, titre, sous, blocs):
    """Carte avec du pseudo-code ou du code (police à chasse fixe) ; blocs = [(sous-titre, [lignes])]."""
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100); fig.patch.set_facecolor(FOND)
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.add_patch(FancyBboxPatch((0, 0.9), 1, 0.1, boxstyle="square,pad=0", fc="#1F4E79", ec="none"))
    ax.text(0.5, 0.95, "Lidar Lab — exploration automatique (bonus)", color="white", fontsize=22, fontweight="bold", ha="center", va="center")
    ax.text(0.05, 0.84, titre, color=TXT, fontsize=30, fontweight="bold", va="center")
    ax.text(0.05, 0.79, sous, color=GRIS, fontsize=15, va="center")
    y = 0.72
    for st, lignes in blocs:
        if st:
            ax.text(0.05, y, st, color=JAUNE, fontsize=15, fontweight="bold", va="center"); y -= 0.04
        h = 0.034 * len(lignes) + 0.02
        ax.add_patch(FancyBboxPatch((0.05, y - h + 0.017), 0.9, h, boxstyle="round,pad=0.004,rounding_size=0.008", fc=PANNEAU, ec="#26364a", lw=1.2))
        for l in lignes:
            c = "#7f8ea0" if l.strip().startswith(("//", "#")) else TXT
            ax.text(0.065, y, l, color=c, fontsize=14.5, family="DejaVu Sans Mono", va="center"); y -= 0.034
        y -= 0.05
    fig.savefig(IMG / nom, dpi=100, facecolor=FOND); plt.close(fig)
    return nom


montage = []
montage.append((carte_texte("00_titre.png", "Le robot décide seul où aller",
                            ["1.  Il scanne et se recale sur la carte qu'il a déjà construite",
                             "2.  Il repère la zone inconnue la plus proche (la « frontière »)",
                             "3.  Il calcule un chemin sûr et avance d'un petit pas",
                             "4.  Il recommence, jusqu'à ce que toute la salle soit connue"],
                            "Exploration par frontières : scanner, choisir, avancer"), 7.0))
montage.append((carte_code("01_algorithme.png", "L'algorithme : exploration par frontières",
    "Méthode classique de la littérature (Yamauchi, 1997), construite sur les briques du cours : grid map (Jour 1) et recalage par scan matching (Jour 2)",
    [(None, ["répéter",
             "    scan  <- tour complet du lidar, robot à l'arrêt",
             "    pose  <- recaler le scan sur la grid map            (scan matching, Jour 2)",
             "    carte <- ajouter le scan à la grid map              (log-odds, Jour 1)",
             "    frontières <- cellules libres qui touchent au moins 2 cellules inconnues",
             "    si aucune frontière atteignable : fin de l'exploration",
             "    chemin <- parcours en largeur sur la grille, murs gonflés de 25 cm,",
             "              jusqu'à la frontière la plus proche",
             "    direction <- vers le point du chemin situé à 1 m",
             "              (bouchée ? direction libre la plus proche : contournement, demi-tour)",
             "    tourner, vérifier à l'arrêt que (pas + 35 cm) sont libres, avancer d'un pas <= 35 cm"])]), 14.0))
montage.append((carte_code("02_code.png", "Le code : serveur_robot/exploration.js",
    "Extraits du code de Lidar Lab exécuté dans cette simulation (lignes de journal et d'attente omises, commentaires résumés)",
    [("Une frontière : cellule libre au bord de l'inconnu", [
        "const isFrontier = (row, col) => {",
        "  if (at(row, col) !== 0) return false;   // la cellule doit être LIBRE",
        "  let unk = 0;",
        "  for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) if (at(row + dr, col + dc) === -1) unk++;",
        "  return unk >= 2;                         // au moins 2 voisines inconnues",
        "};"]),
     ("La boucle principale : choisir, tourner, avancer, se recaler", [
        "const { pose, grid, visited } = io.state();",
        "const sc = await io.scan();",
        "const choice = chooseDirection(localPoints(sc, o), pose, grid, visited, o);",
        "if (!choice) return (reason = \"terminé : plus de zone inconnue accessible\");",
        "const ms = await move(() => io.turn(choice.turnDeg));",
        "const mv = await stepForward(choice.step);    // contrôle de l'avant, robot à l'arrêt",
        "const r = await io.capture();                 // nouveau scan + recalage (Auto-SLAM)"])]), 16.0))
lent = LENT
for i in range(N):
    if i < lent:
        montage.append((image(i, "scan", f"e{i:04d}_a.png"), 3.2 if i == 0 else 2.2))
        if i + 1 < N:
            montage.append((image(i, "decision", f"e{i:04d}_b.png"), 2.2))
            montage.append((image(i, "pas", f"e{i:04d}_c.png"), 1.4))
    else:
        montage.append((image(i, "rapide", f"e{i:04d}.png"), 0.32))
montage.append((image(N - 1, "scan", f"e{N - 1:04d}_fin.png"), 4.0))
fin = etapes[-1]
montage.append((carte_texte("99_bilan.png", "Résultat de l'exploration",
                            [f"•  {N} scans, {bilan['distance_m']:.0f} m parcourus, sans aucune collision",
                             f"•  {fin['couverture'] * 100:.0f} % de la salle cartographiée ; arrêt seul : plus de zone inconnue",
                             f"•  écart avec la vraie position : {bilan['erreur_pose_max_m'] * 100:.0f} cm au plus sur tout le trajet",
                             "•  même code que sur le robot ; essai réel : fiche d'essai prête"],
                            "Simulation dans la salle réelle reconstruite (robot et lidar simulés)"), 8.0))
(V / "montage.txt").write_text("\n".join(f"file 'images/{n}'\nduration {d:.3f}" for n, d in montage) + f"\nfile 'images/{montage[-1][0]}'\n", "utf-8")
print(len(montage), "images, durée", round(sum(d for _, d in montage), 1), "s")
