# Correctif « le lidar voit le robot » — règle et critères (écrits AVANT la validation)

## Défaut (trouvé dans `version_1`, séance du 10/11)

Le lidar voit une partie du robot : 270 points, tous entre 7,5 et 16,3 cm du lidar et tous dans le secteur
300–340° (avant droit, angles du repère robot de Lidar Lab). Un point plus proche que la demi-largeur du
couloir (20 cm) bouche toutes les directions de son côté : 4 arrêts à tort sur 48 scans.

## Règle (conçue sur les scans du 10/11 uniquement)

Nouveau réglage `selfMask` de l'explorateur : un point **à moins de 20 cm du lidar ET dans le secteur
300–340°** est considéré comme le robot lui-même et ignoré **par l'explorateur seulement** (choix de la
direction et contrôle d'avant-pas). Tous les autres points, même très proches, restent des obstacles.
La carte, l'Auto-SLAM et les scans enregistrés ne changent pas. Sur le 10/11 : 4 arrêts à tort → 0
(données de conception, ce n'est pas une validation).

## Validation sur la séance réelle du 04/11 (jamais utilisée pour ce correctif)

`data/robot_wifi/seance_2026-11-04_17h42m59`, scans recalés, même rejeu que la partie A du 10/11.

- **V1** : arrêts à tort (aucune direction alors qu'un chemin vers l'inconnu existe) : **0 après correctif**
  (le nombre avant est rapporté).
- **V2** : le robot est vu au même endroit : au moins **80 %** des points à moins de 20 cm du lidar sont
  dans le secteur 300–340°. Si moins de 20 points proches en tout, V2 est déclaré « non mesurable ».
- **V3** : les points ignorés sont rares : moins de **2 %** des points de chaque scan.
- **V4** : tous les tests de Lidar Lab passent, sauf le test déjà instable « réutilise au redémarrage
  la dernière adresse », et un nouveau test vérifie qu'un obstacle proche HORS du secteur bloque toujours.

Si un critère n'est pas atteint, il est rapporté tel quel ; la règle n'est pas modifiée après coup.
