# Séance réelle du robot — 04/11/2026 (17h42 → 19h35)

**Données réelles** du LiDAR LD06 monté sur le robot, reçues en Wi-Fi par le serveur de Lidar Lab
(`codex_lidar/serveur_robot`). Ce ne sont pas des scans simulés.

## Contenu
- `scan_NN_HHhMMmSS.csv` : un tour complet du LD06 par fichier.
  - 1re ligne : `# robot_wifi id=… hz=… pts=… pwm=… moving=0|1` (identifiant du tour, fréquence de rotation,
    nombre de points, consigne PWM du moteur lidar, robot en mouvement ou non).
  - puis `angle_deg,distance_mm,intensity` (≈ 316–321 points par tour, pas ≈ 1,04°, ≈ 14 tours/s).
- **Deux séries** portent les mêmes numéros :
  - 19h19 → 19h23 : 12 scans d'un premier essai (non repris dans `seance.json`) ;
  - 19h20m09 puis 19h24 → 19h35 : la séance complète de **40 scans**, dans l'ordre de capture, listée dans `seance.json`.
- `seance.json` : état de la séance enregistré par le serveur (réglages, ordre, pose, statut de chaque scan).
- `poses.json` : poses des 35 scans recalés `{nom: [x_m, y_m, theta_deg]}`.
- `grid_map.csv` (−1 inconnu, 0 libre, 1 occupé ; origine et pas en commentaire) et `grid_map_map_tool.csv` (format MapTool 0/1) : cartes produites par l'Auto-SLAM ce jour-là.
- `reference_autoslam_2026-11-04.json` : copie séparée des poses de l'Auto-SLAM (35 recalés sur 40, 5 refusés pour
  « plusieurs positions possibles ») avec leurs notes.

## Statut des poses
Les poses viennent du **scan matching** de l'Auto-SLAM : elles servent de **référence de cohérence** pour comparer
d'autres méthodes sur les mêmes scans. Ce n'est **pas une vérité terrain** : aucune position n'a été mesurée au sol.
Le repère est le premier scan accepté (`scan_01_19h20m09` = 0, 0, 0°).
