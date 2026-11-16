# Correctif « le lidar voit le robot » — résultats

Règle et critères : `PROTOCOLE_correctif.md` (committé avant la validation). Code : `codex_lidar`,
`serveur_robot/exploration.js`, réglage `selfMask` (points à moins de 20 cm ET dans le secteur 300–340°
ignorés par l'explorateur seulement).

## Données de conception (10/11, pas une validation)
Arrêts à tort : 4 → 0.

## Validation sur la séance du 04/11 (35 scans recalés, jamais utilisée pour le correctif)

| Critère | Résultat |
|---|---|
| V1 : 0 arrêt à tort après correctif | **non atteint** : 4 avant, 4 après |
| V2 : ≥ 80 % des points < 20 cm dans le secteur 300–340° | **non mesurable** : 3 points proches en tout, aucun dans le secteur |
| V3 : moins de 2 % de points ignorés par scan | **atteint** : 0 point ignoré |
| V4 : tests de Lidar Lab | **atteint** : 62/63, seul échoue le test instable connu ; nouveau test X9 |

Lecture :
- Le 04/11, le lidar **ne voyait pas le robot** : le masque n'a rien retiré. Il n'a donc ni aidé ni gêné,
  et sa validation sur des données indépendantes est **non concluante**. Le lidar ou sa fixation a pu
  changer entre le 04/11 et le 10/11 : le masque est à vérifier lors de l'essai réel.
- Les 4 arrêts à tort du 04/11 ont **une autre cause** (scans 1, 9, 10 et 11) : le robot est dans un
  recoin (111 à 136 points à moins de 50 cm). Une sortie libre existe, mais **derrière lui** (plus de
  120° de la direction du chemin) : l'explorateur ne fait pas demi-tour et s'arrête en affichant à tort
  « plus de zone inconnue accessible ». **Ce second défaut n'est pas corrigé** : le corriger maintenant
  reviendrait à changer la règle après avoir vu ce résultat ; il demande sa propre règle, fixée avant,
  et d'autres données pour la valider.

Fichiers : `validation_0411.json` ; scripts `../validation_correctif_0411.js`, `../commun.js`.
