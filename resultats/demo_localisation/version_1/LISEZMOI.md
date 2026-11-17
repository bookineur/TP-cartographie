# Démo vidéo : « Où le robot a-t-il pris ce scan ? » (Lidar Lab)

`demo_localisation_scan.mp4` (52 s, 1600 × 900) : dans Lidar Lab, avec la séance **réelle** du 10/11
(48 scans recalés), on tire **3 scans au hasard**. Pour chacun, la recherche se fait sur la grid map
construite **sans ce scan** (ni les scans pris à moins de 15 cm), sur toute la carte et sur 360°, **sans
position de départ**. Le panneau affiche la position trouvée et l'écart avec la pose enregistrée par
l'Auto-SLAM (qui n'est pas une vérité terrain). Ce sont des scans **enregistrés** : ce n'est pas le
robot en direct.

Tirages de la vidéo (`tirages.txt`) : écarts de 2,5 cm / 0°, 3,5 cm / 1°, 2,5 cm / 0°.

## Tous les scans (même calcul, `../demo_localisation_48scans.js`)

| Règles de refus | Acceptés | dont < 10 cm et < 2° | Fausses poses (≥ 30 cm ou 5°) | Refus |
|---|---|---|---|---|
| recouvrement ≥ 35 % + ambiguïté (règles de la démo) | 42 / 48 | 39 | 0 | 6 ambigus (scans 1, 2, 3, 19, 39, 40) |
| + contradiction avec l'espace libre (étape 4 de l'assemblage) | 9 / 48 | 9 | 0 | 33 « contradiction », 6 ambigus |

Écart des acceptés (règles de la démo) : médiane 2,5 cm, maximum 21,1 cm.

**Constat :** le test « contradiction avec l'espace libre » (seuil 14,2 %, réglé sur la séance du 04/11)
refuse 33 poses justes sur 48 de la séance du 10/11 (écart médian de ces poses : 2,5 cm). Il est donc trop
strict sur d'autres données ; il reste actif par défaut dans le bouton « Localiser et construire la
carte ». La démo ne l'utilise pas. À revoir séparément.

## Refaire la vidéo
1. Copier `data/mesures_phase19_2026-11-09/capture/seance_2026-11-09_13h06m10` dans un dossier vide D.
2. `node serveur_robot/serveur.js --robot http://127.0.0.1:9 --port 8012 --dossier D` (codex_lidar).
3. `node ../enregistrer_video.js http://localhost:8012/ <dossier_images> video 3`, puis assembler les
   images avec ffmpeg (`liste.txt` : une image et sa durée réelle).
