# Vidéo de démonstration — exploration automatique (bonus)

`exploration_automatique_demo.mp4` (1 min 49, 1920 × 1080).

**Ce que montre la vidéo.** Le vrai code d'exploration de Lidar Lab (`serveur_robot/exploration.js`) pilote un
robot **simulé** (`tests/simulateur_robot.js` : erreurs de rotation ±5 %, de distance ±10 %, arrêt sans ordre,
collision à 12 cm) dans la salle réelle du 10/11 reconstruite à partir de sa carte vectorielle brute (166 segments).
Le lidar est simulé sur ces murs. À chaque étape : scan et recalage, choix de la zone inconnue la plus proche
(frontière), petit pas, nouveau scan. Les six premiers scans sont expliqués lentement, en vue rapprochée ; la suite
est accélérée.

**Résultat de cet essai** (`bilan.json`) : 151 scans, 50,5 m, aucune collision, 87 % de la salle cartographiée,
arrêt seul (« plus de zone inconnue accessible »), écart avec la vraie position de 12,9 cm au plus. C'est le même
essai que le départ « scan 1 » de `resultats/exploration_scans_reels/` (mêmes départ et graine) ; les deux autres
départs y sont aussi rapportés (dérive jusqu'à 25 cm ; un faux recalage en fin de parcours).

**Limite.** Simulation : le lidar simulé ne voit ni vitres, ni personnes, ni reflets. L'essai sur le vrai robot
suit la fiche `rendu/essai_exploration_robot/version_3`.

Refaire la vidéo : `node ../enregistrer_exploration.js` (variable `LIDAR_LAB` = dossier de Lidar Lab), puis
`python ../images.py .` et `ffmpeg -f concat -safe 0 -i montage.txt -vf "fps=30,format=yuv420p" -c:v libx264 -crf 18 exploration_automatique_demo.mp4`.
