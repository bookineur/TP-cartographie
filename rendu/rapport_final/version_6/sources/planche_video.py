"""Planche d'images tirées de la vidéo de démonstration (figure du rapport)."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

src = Path(sys.argv[1])
legendes = [(1, "1. La grid map de la salle (séance réelle du 10/11, 48 scans)"),
            (5, "2. Un scan est tiré au hasard et retiré de la carte ;\nen haut à gauche, ce que voyait le robot"),
            (12, "3. Résultat de l'essai 1 : le scan (en jaune) se pose sur les murs ;\nle cadre donne la position du robot"),
            (26, "4. Essai 2 : un autre scan est tiré ; la carte est reconstruite sans lui"),
            (32, "5. Résultat de l'essai 2"),
            (60, "6. Résultat de l'essai 3 : coin opposé de la salle")]
fig, axes = plt.subplots(3, 2, figsize=(13, 11.2))
for ax, (t, txt) in zip(axes.ravel(), legendes):
    ax.imshow(mpimg.imread(src / f"cle_{t}.png"))
    ax.set_title(txt, fontsize=10.5, loc="left")
    ax.axis("off")
fig.tight_layout()
fig.savefig(Path(__file__).resolve().parents[1] / "figures" / "planche_video_demo.png", dpi=110)
print("ok")
