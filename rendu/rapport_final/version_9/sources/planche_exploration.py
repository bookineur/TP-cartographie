"""Planche d'images de la vidéo de l'exploration automatique (figure du rapport, partie bonus)."""
import sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

src = Path(sys.argv[1])
leg = [("e0001_a.png", "1. Le robot scanne ; le scan (jaune) est recalé\nsur la carte déjà construite"),
       ("e0001_b.png", "2. Il choisit la zone inconnue la plus proche\n(étoile rose), à partir des frontières (orange)"),
       ("e0001_c.png", "3. Il avance d'un petit pas (36 cm),\naprès avoir vérifié la place devant lui"),
       ("e0030.png", "4. Scan 31 : la carte grandit, le robot\ncontinue vers la zone inconnue suivante"),
       ("e0090.png", "5. Scan 91 : la salle est presque entièrement\ncartographiée (85 %)"),
       ("e0150_fin.png", "6. Fin : plus de zone inconnue accessible ;\n151 scans, 50 m, aucune collision, 87 %")]
fig, axes = plt.subplots(3, 2, figsize=(13, 11.4))
for ax, (f, t) in zip(axes.ravel(), leg):
    ax.imshow(mpimg.imread(src / f)); ax.set_title(t, fontsize=10.5, loc="left"); ax.axis("off")
fig.tight_layout()
out = Path(__file__).resolve().parents[1] / "figures"; out.mkdir(exist_ok=True)
fig.savefig(out / "planche_video_exploration.png", dpi=110)
print("ok")
