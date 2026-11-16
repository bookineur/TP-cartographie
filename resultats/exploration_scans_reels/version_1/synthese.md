# Exploration testée avec les scans réels du 10/11 — résultats

Protocole : `PROTOCOLE.md`, écrit et committé avant la mesure (commit 4f76fd5). Code testé :
`codex_lidar/serveur_robot/exploration.js` au commit 91dd476, réglages par défaut.

## Partie A — décisions rejouées sur les 48 scans réels

| Décision | Nombre |
|---|---|
| sûre | 23 |
| « dangereuse » (≥ 3 points de la carte complète dans la zone balayée) | 21 |
| aucune direction (l'explorateur se serait arrêté) | 4 (scans 9, 39, 40, 41) |
| pas bloqué par le contrôle d'avant-pas | 0 |

**Critère A (0 décision dangereuse) : non atteint (21).**

Examen des 21 cas (`partie_a.json`, `partie_a_sans_points_proches.json`) :
- dans les 21 cas, le scan réel pris au moment de la décision voyait **au moins 1,05 m libre** dans la
  direction choisie (pour les scans 42 à 44, aucun point dans le couloir jusqu'à 8 m) : les points en cause
  viennent tous d'**autres** scans ;
- origine : le scan suivant seulement (scans 10, 14, 18, 23 à 28), les scans 1 à 3 pris au départ
  (scans 4 à 6 et 22), ou de nombreux scans (17 et plus pour les scans 42 et 43, près de la porte) ;
- hypothèse testée APRÈS le résultat : « ce sont des points du robot lui-même » → **rejetée** (les 21 cas
  restent dangereux sans les points à moins de 30 cm de leur lidar) ;
- explications possibles restantes, non démontrées : objets ou personnes qui ont bougé entre deux scans,
  dérive des poses de l'Auto-SLAM (murs doublés de 14 à 23 cm). Le contrôle choisi (carte cumulée) n'est
  pas une vérité de l'instant : ce critère était mal conçu pour trancher. Seul un essai réel le peut.

**Défaut trouvé (scans 9, 39, 40, 41).** Les scans réels contiennent des points à environ **11 cm** du
lidar, presque toujours au même angle (310 à 330°, avant droit) : dans 18 à 27 scans sur 48. C'est
probablement une partie du robot. Un point plus proche que la demi-largeur du couloir (20 cm) bouche
toutes les directions de son côté : l'explorateur ne trouve plus de direction et s'arrête en affichant
à tort « plus de zone inconnue accessible », alors qu'un chemin vers l'inconnu existait (1,4 à 2,7 m).

## Partie B — exploration SIMULÉE dans la salle réelle reconstruite

| Départ | Pas | Distance | Collision | Erreur de pose max | Scans à > 10 cm | Couverture | Fin |
|---|---|---|---|---|---|---|---|
| scan 1 | 150 | 50,5 m | non | 12,9 cm / 1,4° | 7 / 151 | 86,7 % | plus de zone inconnue |
| scan 20 | 165 | 52,3 m | non | 24,8 cm / 1,8° | 135 / 166 | 87,0 % | plus de zone inconnue |
| scan 40 | 136 | 44,7 m | non | 964 cm / 92,6° | 29 / 137 | 57,2 % | plus de zone inconnue |

Critères : 1. aucune collision → **atteint** (3/3) ; 2. poses < 10 cm et 3° → **non atteint** (0/3) ;
3. couverture ≥ 80 % → **atteint pour 2 départs sur 3**.

- Départ 20 : **dérive** qui s'accumule le long des 52 m (médiane 19,6 cm) : sans fermeture de boucle,
  l'erreur grandit avec la distance, comme sur la vraie séance.
- Départ 40 : le **dernier scan** est accepté à une pose fausse (9,6 m, 93°) : faux positif du recalage
  (règle de l'Auto-SLAM, sans les étapes 3 et 4 de l'assemblage). Le robot était aussi sorti de la salle par
  un trou de la carte (mur gauche incomplet), limite annoncée dans le protocole.
- Les trajets montrent de longues hésitations dans les coins (nombreux petits pas au même endroit).
- Limites : lidar simulé sur des segments seulement (pas de vitres, de personnes, ni de points du robot).

Fichiers : `partie_a*.json`, `partie_a_decisions.png`, `partie_b_depart*.json`, `partie_b_exploration.png`,
`journal_partie_b.txt` ; scripts dans le dossier parent.
