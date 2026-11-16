# Localisation globale d'un scan sur la carte — protocole (écrit AVANT la mesure)

Question : « le robot a pris ce scan ; sans aucune indication de position, peut-il
retrouver où il était, sur la grid map, puis sur la carte vectorielle ? »

## Données

- Séance réelle du 10/11 : 48 scans recalés par l'Auto-SLAM
  (`data/mesures_phase19_2026-11-09/carte_autoslam_v1/session_assemblee`, non modifiés).
- **Pose de référence** = pose de l'Auto-SLAM (`poses.json`). Ce n'est **pas une vérité terrain**
  (dérive estimée à environ 20 cm sur cette séance) : on mesure la **cohérence** avec l'Auto-SLAM.

## Cartes « sans le scan testé » (leave-one-out)

Pour chaque scan testé, la grid map (cellules de 5 cm, `build_grid`) et la carte vectorielle
(`build_vector_map`) sont construites avec les autres scans à leur pose Auto-SLAM, **sans** le scan
testé **ni** les scans pris au même endroit (à moins de 15 cm : règle `SAME_MARK` du Jour 2). Sinon un
scan presque identique serait dans la carte et la localisation serait faussement facile.
Prétraitement : `clean_scan` (10 cm à 10 m, points isolés supprimés), comme pour la carte du 10/11.

## Méthode (aucune pose initiale donnée)

1. **Candidats globaux** : corrélation par FFT du scan avec les points de la référence (cellules
   occupées de la grid map, ou points tous les 2 cm le long des segments), pour tous les angles de
   0 à 358° par pas de 2° ; on garde les 8 meilleurs candidats distincts (> 0,6 m ou > 20° entre eux).
2. **Affinage** de chaque candidat avec les méthodes du Jour 2, sur la référence elle-même :
   multi-résolution (fenêtre ±0,3 m, ±6°) puis Gauss-Newton.
3. **Choix** : le candidat qui a la plus grande part p de points à moins de 10 cm de la référence.
4. **Acceptation** (règles déjà utilisées dans Lidar Lab, aucun seuil nouveau) :
   - p ≥ 35 % ;
   - pas d'ambiguïté : aucun autre candidat affiné éloigné (> 0,6 m ou > 0,4 rad) n'a une part
     ≥ p − 2·√(p(1−p)/N) (N = nombre de points du scan).
   Sinon : **refus** (« je ne sais pas où je suis »).

## Mesures et critères (fixés avant)

- Écart de position et d'angle à la pose Auto-SLAM, temps de calcul.
- Classement d'un scan accepté : **concordant** si < 10 cm et < 2° ; **proche** si < 30 cm et < 5° ;
  **faux positif** sinon.
- Critères annoncés :
  1. **0 faux positif** sur chaque référence ;
  2. au moins **80 %** des 48 scans acceptés et concordants ou proches, sur chaque référence.
- Les deux références sont comparées sur les mêmes scans. Aucun réglage ne sera changé après
  avoir vu les résultats ; un écart au protocole sera signalé dans le rapport.
