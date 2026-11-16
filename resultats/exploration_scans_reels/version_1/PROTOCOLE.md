# Exploration automatique testée avec les scans réels du 10/11 — protocole (écrit AVANT la mesure)

But : tester l'exploration automatique (bonus) avec les **vrais scans** de la séance du 10/11 (48 scans
recalés, `data/mesures_phase19_2026-11-09/capture/seance_2026-11-09_13h06m10`, non modifiés), avant
l'essai sur le robot. Code testé : `codex_lidar/serveur_robot/exploration.js` (commit 91dd476), réglages
par défaut (`DEFAULTS`) sauf mention contraire.

## Partie A — Rejeu des décisions sur les scans réels

Pour chaque scan recalé k (ordre de capture), on reconstruit exactement ce que l'explorateur verrait
juste après la capture k : grid map des scans 1 à k (même calcul que le serveur), pose Auto-SLAM du scan k,
poses déjà visitées. Avec les **points réels du scan k**, on appelle `chooseDirection`, puis le contrôle
d'avant-pas (`corridorClearance` dans la direction choisie, après rotation sur place) : le pas est
**bloqué** si le dégagement est inférieur à 35 cm + longueur du pas.

**Contrôle de sécurité** : pour chaque pas non bloqué, on regarde la zone balayée par le robot dans la
carte complète (points des 48 scans) : rectangle partant de la pose, dans la direction choisie, de longueur
pas + 12 cm et de largeur 30 cm (robot supposé de 30 cm de large, lidar à 12 cm de l'avant : à mesurer sur
le robot). La décision est **dangereuse** si au moins 3 points de la carte complète tombent dans ce rectangle.

- Critère A : **0 décision dangereuse** sur les 48 scans.
- Mesures rapportées aussi : nombre de décisions par mode (direction, contournement, aucune), pas bloqués,
  longueur des pas.
- Limite connue : la carte complète contient la dérive de l'Auto-SLAM (environ 20 cm) et d'éventuelles
  personnes ; chaque décision dangereuse est examinée et rapportée, jamais retirée.

## Partie B — Exploration dans la salle réelle reconstruite (SIMULATION)

Monde simulé = carte vectorielle **brute** de la séance (`carte_autoslam_v1/segments.csv`, 166 segments,
murs et mobilier observés). Le robot et le lidar sont simulés comme dans les tests de Lidar Lab
(`tests/simulateur_robot.js`, `tests/synthetic_ld06.js`) : rotation ±5 %, distance ±10 %, collision à 12 cm.

- 3 départs : poses Auto-SLAM des scans 1, 20 et 40 ; graines 1, 2 et 3.
- Réglages : `maxSteps` = 200 et `maxMs` = 60 min (temps simulé) au lieu de 60 pas / 15 min, car la salle
  (13 × 12 m) est bien plus grande que la salle de test ; tous les autres réglages par défaut.
- Surface de référence : cellules **libres** de la grid map réelle des 48 scans.
- Critères :
  1. **aucune collision** ;
  2. toutes les poses recalées à moins de **10 cm et 3°** de la vérité simulée ;
  3. au moins **80 %** de la surface de référence cartographiée.
- Limites connues : le lidar simulé ne voit que les segments (pas de vitres, de personnes ni de reflets) ;
  les trous de la carte (zones jamais vues) laissent passer les rayons et le robot.

Aucun réglage ne sera changé après avoir vu les résultats ; tout écart au protocole sera signalé.
Résultats : `resultats.json`, `synthese.md` et figures dans ce dossier.
