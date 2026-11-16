# Correctif « demi-tour dans un recoin » — règle et critères (écrits AVANT de coder)

## Défaut (trouvé dans `version_2`, séance du 04/11, scans 1, 9, 10, 11)

Un chemin vers une zone inconnue existe, mais la direction du chemin est bouchée de près et les seules
directions libres sont à plus de 120° de celle du chemin (la sortie est derrière le robot). L'explorateur
ne trouve rien et s'arrête en affichant à tort « plus de zone inconnue accessible ».

## Règle

Dans `chooseDirection`, quand un chemin existe mais qu'aucune direction n'a été retenue (ni « chemin »,
ni « contournement » à 120° au plus, ni « direction » vers les frontières) :
1. **demi-tour** : prendre la direction dégagée (dégagement ≥ `minClear` = 0,75 m) la plus proche de celle
   du chemin, **quel que soit l'angle** ; pas = min(35 cm, dégagement − 35 cm − 10 cm), comme ailleurs ;
2. s'il n'existe **aucune** direction dégagée : l'exploration s'arrête avec un message vrai,
   « arrêt : aucune direction libre autour du robot (zone inconnue restante) », au lieu de
   « plus de zone inconnue accessible ».
Rien d'autre ne change (mêmes seuils, même contrôle d'avant-pas, même masque du robot).

## Données disponibles

Il n'existe que deux séances réelles avec le robot (04/11 et 10/11) et **toutes deux ont servi à trouver
les défauts** : aucune donnée réelle indépendante. La preuve finale viendra de l'essai sur le robot.

## Critères

- **D1 (tests unitaires)** : direction du chemin bouchée et seule sortie derrière → mode « demi-tour » vers
  la sortie ; robot entouré de tous côtés → arrêt « aucune direction libre ».
- **D2 (non-régression, tests de Lidar Lab)** : tous les tests passent, sauf le test instable connu
  (« réutilise au redémarrage la dernière adresse »), dont X2 (salle jamais vue, 3 tirages).
- **D3 (non-régression, salle réelle reconstruite, partie B de `version_1`, mêmes départs et graines)** :
  0 collision ; couverture de chaque départ pas inférieure de plus de 5 points à `version_1`.
- **D4 (données de conception, rapporté sans valeur de preuve)** : arrêts à tort sur le 04/11 et le 10/11
  (avec le masque du robot) ; aucun pas « demi-tour » dont le contrôle d'avant-pas, sur le scan réel,
  serait bloqué.

Si un critère n'est pas atteint, il est rapporté tel quel ; la règle n'est pas modifiée après coup.
