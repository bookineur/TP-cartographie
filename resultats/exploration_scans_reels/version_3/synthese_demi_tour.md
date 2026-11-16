# Correctif « demi-tour dans un recoin » — résultats

Règle et critères : `PROTOCOLE_demi_tour.md` (committé avant de coder). Code : `codex_lidar`,
`serveur_robot/exploration.js` (mode « demi-tour » et arrêt « aucune direction libre »).

| Critère | Résultat |
|---|---|
| D1 : tests unitaires (test X10) | **atteint** — demi-tour vers la seule sortie ; arrêt explicite si entouré. L'ancien code renvoyait « rien » dans la même situation |
| D2 : tests de Lidar Lab | **atteint** — 64/64 (le test instable est passé cette fois) |
| D3 : non-régression, salle réelle reconstruite | **atteint** — les 3 explorations sont identiques à `version_1` (mêmes pas, couverture 86,7 / 87,0 / 57,2 %, 0 collision) : la nouvelle règle ne s'est jamais déclenchée dans ce monde simulé |
| D4 : données de conception (sans valeur de preuve) | 10/11 : 0 arrêt à tort, aucun changement. 04/11 : 4 arrêts à tort → 0 ; 3 demi-tours (sorties libres de 1,07 à 2,64 m, contrôle d'avant-pas passé à chaque fois) et 1 arrêt « aucune direction libre » (scan 1 : aucune direction n'avait 75 cm de libre) |

Limites :
- Aucune donnée réelle indépendante : les deux séances avec le robot ont servi à trouver les défauts. La
  preuve viendra de l'essai réel.
- D3 montre que le simulateur ne produit pas de recoins de ce type : il ne teste donc pas le demi-tour.
- Risque non mesuré : après un demi-tour, le chemin peut ramener le robot vers le même recoin (aller-retour)
  jusqu'à la limite de pas. À observer pendant l'essai.

Fichiers : `rejeu_demi_tour.json`, `partie_b_depart*.json`, `journal_partie_b.txt` ; scripts dans le dossier parent.
