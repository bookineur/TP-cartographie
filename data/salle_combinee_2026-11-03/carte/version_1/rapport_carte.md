# Cartographie de la pièce — grid map et carte vectorielle

Généré le 03/11/2026 16:49.

## 1. Données

Scans utilisés : scan13, scan1, scan2, scan3, scan4, scan5, scan6, scan7, scan8, scan9, scan10, scan11, scan12, scan14, scan15, scan16, scan17, scan19, scan20, scan21, scan22, scan23, scan24, scan25, scan26, scan27, scan28, scan29, scan30. Scans écartés : scan18, scan31 (aucun recouvrement fiable avec la pièce).

Chaque scan est un tour du LD06 : environ 450 points (angle, distance) à 10 tr/s, plus de 1 000 points quand le lidar tourne plus lentement. Les scans ont été reçus au format Teleplot (`printScanTeleplot`), qui transmet x et y mais **pas l'intensité**.

## 2. Prétraitement (§2 du document)

- points à moins de 10 cm (boîtier, câbles) ou à plus de 10 m (précision dégradée) supprimés ;
- points **isolés** supprimés (moins de 2 voisins à moins de 15 cm) : reflets, poussières, mesures aberrantes ;
- intensité < 50 supprimée.

Bilan : 18816 points bruts → 16009 points conservés.

| scan | points bruts | conservés | sur des murs (segments ≥ 60 cm) | utilisé |
|---|---|---|---|---|
| scan1 | 455 | 336 | 92% | oui |
| scan2 | 454 | 369 | 64% | oui |
| scan3 | 454 | 365 | 61% | oui |
| scan4 | 454 | 358 | 54% | oui |
| scan5 | 455 | 390 | 54% | oui |
| scan6 | 1050 | 986 | 80% | oui |
| scan7 | 687 | 503 | 69% | oui |
| scan8 | 1149 | 1036 | 81% | oui |
| scan9 | 455 | 386 | 52% | oui |
| scan10 | 454 | 337 | 47% | oui |
| scan11 | 974 | 899 | 10% | oui |
| scan12 | 1158 | 1095 | 21% | oui |
| scan13 | 735 | 660 | 10% | oui |
| scan14 | 976 | 873 | 27% | oui |
| scan15 | 870 | 820 | 18% | oui |
| scan16 | 304 | 279 | 74% | oui |
| scan17 | 305 | 212 | 50% | oui |
| scan18 | 304 | 204 | 38% | non |
| scan19 | 302 | 208 | 41% | oui |
| scan20 | 792 | 710 | 15% | oui |
| scan21 | 758 | 656 | 51% | oui |
| scan22 | 766 | 656 | 95% | oui |
| scan23 | 784 | 721 | 39% | oui |
| scan24 | 304 | 254 | 64% | oui |
| scan25 | 693 | 532 | 88% | oui |
| scan26 | 454 | 352 | 93% | oui |
| scan27 | 454 | 361 | 75% | oui |
| scan28 | 455 | 349 | 28% | oui |
| scan29 | 454 | 366 | 29% | oui |
| scan30 | 453 | 375 | 68% | oui |
| scan31 | 454 | 361 | 34% | non |

## 3. Assemblage des scans (superposition dans un repère commun)

Les positions du robot n'ayant pas été mesurées, elles ont été retrouvées par **recalage** :

1. pour chaque paire de scans (A, B) et chaque rotation θ de 0 à 360° (pas de 2°), la translation qui superpose le mieux B sur A est cherchée par corrélation (FFT) entre les points de B et une grille floutée des points de A ;
2. la meilleure pose est affinée par **ICP** (Iterative Closest Point, cité dans le cours pour la détection de boucle) ;
3. le **recouvrement** (part des points de B à moins de 10 cm d'un point de A) mesure la qualité ; on garde les meilleures liaisons (arbre couvrant de recouvrement maximal) et on compose les poses depuis un scan de référence (pose 0, 0, 0).

Formule appliquée à chaque point : P_global = R(θ)·P_local + T(x, y).

| scan | x (m) | y (m) | θ (°) | recouvrement avec les autres scans |
|---|---|---|---|---|
| scan13 | 0.00 | 0.00 | -34.1 | 96% |
| scan1 | 3.48 | 2.47 | 165.6 | 99% |
| scan2 | 1.01 | 4.66 | -171.4 | 96% |
| scan3 | 1.33 | 5.04 | -175.0 | 93% |
| scan4 | 0.71 | 4.81 | -4.9 | 90% |
| scan5 | 0.79 | 5.77 | -83.5 | 88% |
| scan6 | 0.32 | 5.65 | -92.2 | 94% |
| scan7 | 4.13 | 5.84 | -86.1 | 99% |
| scan8 | 3.95 | 1.55 | -93.9 | 100% |
| scan9 | 3.42 | 0.62 | -84.3 | 90% |
| scan10 | -0.03 | -0.74 | 117.7 | 78% |
| scan11 | 0.55 | -0.68 | -62.9 | 90% |
| scan12 | 1.09 | -0.58 | -2.5 | 93% |
| scan14 | 3.70 | 6.81 | 178.0 | 58% |
| scan15 | 0.47 | -0.53 | 0.8 | 89% |
| scan16 | -0.39 | -0.49 | -48.1 | 100% |
| scan17 | 1.75 | -0.72 | 95.9 | 88% |
| scan19 | 4.09 | 6.26 | -89.9 | 90% |
| scan20 | 1.27 | -0.69 | 6.7 | 78% |
| scan21 | 0.58 | 3.62 | -85.3 | 86% |
| scan22 | 3.45 | 2.33 | -83.4 | 100% |
| scan23 | 2.87 | 0.81 | 4.5 | 90% |
| scan24 | 2.65 | -0.93 | 1.2 | 91% |
| scan25 | 2.85 | 3.23 | -1.3 | 100% |
| scan26 | 3.44 | 2.44 | -1.3 | 100% |
| scan27 | 0.74 | 3.53 | 4.8 | 96% |
| scan28 | 0.49 | -0.60 | -5.9 | 94% |
| scan29 | 3.75 | -1.32 | -83.4 | 78% |
| scan30 | 3.96 | 1.72 | 77.2 | 96% |

![assemblage](1_assemblage.png)

## 4. Grid map (carte d'occupation)

Cellules de 5 cm, log-odds : chaque rayon (Bresenham) rend libres les cellules traversées et occupée la cellule d'impact.

- surface libre : 116.4 m², occupée : 3.6 m²

![grid map](2_grid_map.png)

## 5. Carte vectorielle (§3 et §4 du document)

- **segmentation** : rupture de cluster quand deux points successifs sont à plus de 20 cm ;
- **reconnaissance géométrique** : simplification polygonale (Douglas-Peucker, seuil 10 cm), puis droite des moindres carrés totaux sur chaque morceau ;
- **mise à jour** : un segment proche d'un segment existant (angle < 8°, écart latéral < 8 cm, trou < 20 cm) est **fusionné**, sinon **ajouté** ; chaque segment compte ses observations (confiance) ;
- **nettoyage** : segments de moins de 15 cm supprimés.

Résultat : 260 segments, dont 54 vus au moins 2 fois, 172.7 m de murs.

![carte vectorielle](3_carte_vectorielle.png)

Fichier `carte_vectorielle.txt` : une ligne `x1,y1,x2,y2` par segment (format du document).

## 6. Scans écartés

Les scans scan18, scan31 n'ont pas pu être rattachés de façon fiable. Ils contiennent surtout de **petits amas de points** (pieds de chaises, de tables, objets bas, personnes) et **peu de structures longues** (murs) : le recalage n'a presque rien de commun et de stable à superposer. Une seule ligne droite commune ne suffit pas non plus : le scan peut « glisser » le long d'elle.

C'est typiquement le cas d'un lidar **posé au sol** : un lidar 2D ne voit que dans **un seul plan** (cours, §5), et à quelques centimètres du sol ce plan coupe surtout des pieds de meubles. Placé plus haut (sur une table, sur le robot), il voit les murs et les plateaux. Les personnes qui se déplacent pendant la capture ajoutent des points différents d'un scan à l'autre (objets mobiles, §5 du document).

![scans écartés](4_scans_ecartes.png)

## 7. Limites

- pas d'intensité : les reflets et surfaces sombres ne peuvent pas être filtrés par qualité ;
- les positions sont estimées par recalage : une pièce très symétrique ou très encombrée peut donner un recalage faux (c'est pourquoi certains scans ont été écartés) ;
- le lidar voit dans un seul plan (hauteur du capteur) : tables, chaises et pieds de meubles apparaissent comme des points ou de petits segments ;
- objets mobiles (personnes) : vus dans un seul scan, ils donnent des segments à 1 observation.
