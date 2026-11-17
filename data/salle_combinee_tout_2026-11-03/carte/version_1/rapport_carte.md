# Cartographie de la pièce — grid map et carte vectorielle

Généré le 03/11/2026 17:19.

## 1. Données

Scans utilisés : scan13, scan1, scan2, scan3, scan4, scan5, scan6, scan7, scan8, scan9, scan10, scan11, scan12, scan14, scan15, scan16, scan17, scan18, scan19, scan20, scan21, scan22, scan23, scan24, scan25, scan26, scan27, scan28, scan29, scan30, scan32, scan33, scan34, scan35, scan36, scan37, scan38, scan39. Scans écartés : scan31 (aucun recouvrement fiable avec la pièce).

Chaque scan est un tour du LD06 : environ 450 points (angle, distance) à 10 tr/s, plus de 1 000 points quand le lidar tourne plus lentement. Les scans ont été reçus au format Teleplot (`printScanTeleplot`), qui transmet x et y mais **pas l'intensité**.

## 2. Prétraitement (§2 du document)

- points à moins de 10 cm (boîtier, câbles) ou à plus de 10 m (précision dégradée) supprimés ;
- points **isolés** supprimés (moins de 2 voisins à moins de 15 cm) : reflets, poussières, mesures aberrantes ;
- intensité < 50 supprimée.

Bilan : 23788 points bruts → 20404 points conservés.

| scan | points bruts | conservés | sur des murs (segments ≥ 60 cm) | utilisé |
|---|---|---|---|---|
| scan1 | 455 | 338 | 94% | oui |
| scan2 | 454 | 372 | 64% | oui |
| scan3 | 454 | 381 | 60% | oui |
| scan4 | 454 | 368 | 55% | oui |
| scan5 | 455 | 392 | 54% | oui |
| scan6 | 1050 | 986 | 80% | oui |
| scan7 | 687 | 503 | 69% | oui |
| scan8 | 1149 | 1036 | 81% | oui |
| scan9 | 455 | 386 | 52% | oui |
| scan10 | 454 | 341 | 46% | oui |
| scan11 | 974 | 909 | 10% | oui |
| scan12 | 1158 | 1106 | 21% | oui |
| scan13 | 735 | 661 | 10% | oui |
| scan14 | 976 | 873 | 27% | oui |
| scan15 | 870 | 820 | 18% | oui |
| scan16 | 304 | 279 | 74% | oui |
| scan17 | 305 | 212 | 50% | oui |
| scan18 | 304 | 204 | 38% | oui |
| scan19 | 302 | 208 | 41% | oui |
| scan20 | 792 | 710 | 15% | oui |
| scan21 | 758 | 656 | 51% | oui |
| scan22 | 766 | 686 | 95% | oui |
| scan23 | 784 | 738 | 40% | oui |
| scan24 | 304 | 254 | 64% | oui |
| scan25 | 693 | 610 | 85% | oui |
| scan26 | 454 | 352 | 93% | oui |
| scan27 | 454 | 361 | 75% | oui |
| scan28 | 455 | 349 | 28% | oui |
| scan29 | 454 | 366 | 29% | oui |
| scan30 | 453 | 375 | 68% | oui |
| scan31 | 454 | 361 | 34% | non |
| scan32 | 455 | 353 | 66% | oui |
| scan33 | 455 | 345 | 91% | oui |
| scan34 | 453 | 344 | 83% | oui |
| scan35 | 1086 | 1015 | 20% | oui |
| scan36 | 1159 | 1106 | 32% | oui |
| scan37 | 455 | 343 | 23% | oui |
| scan38 | 454 | 345 | 14% | oui |
| scan39 | 455 | 360 | 38% | oui |

## 3. Assemblage des scans (superposition dans un repère commun)

Les positions du robot n'ayant pas été mesurées, elles ont été retrouvées par **recalage** :

1. pour chaque paire de scans (A, B) et chaque rotation θ de 0 à 360° (pas de 2°), la translation qui superpose le mieux B sur A est cherchée par corrélation (FFT) entre les points de B et une grille floutée des points de A ;
2. la meilleure pose est affinée par **ICP** (Iterative Closest Point, cité dans le cours pour la détection de boucle) ;
3. le **recouvrement** (part des points de B à moins de 10 cm d'un point de A) mesure la qualité ; on garde les meilleures liaisons (arbre couvrant de recouvrement maximal) et on compose les poses depuis un scan de référence (pose 0, 0, 0).

Formule appliquée à chaque point : P_global = R(θ)·P_local + T(x, y).

| scan | x (m) | y (m) | θ (°) | recouvrement avec les autres scans |
|---|---|---|---|---|
| scan13 | 0.00 | 0.00 | 42.4 | 100% |
| scan1 | -3.40 | 2.16 | 79.0 | 99% |
| scan2 | -1.35 | 4.76 | 101.5 | 93% |
| scan3 | -0.95 | 4.45 | 98.0 | 86% |
| scan4 | -1.21 | 5.05 | -92.0 | 91% |
| scan5 | -1.64 | 6.40 | -80.6 | 79% |
| scan6 | -2.11 | 6.26 | -89.2 | 95% |
| scan7 | -0.57 | 0.58 | 176.6 | 84% |
| scan8 | 1.75 | 2.35 | -90.9 | 99% |
| scan9 | 1.26 | 1.39 | -81.0 | 98% |
| scan10 | 0.08 | 0.43 | -73.1 | 95% |
| scan11 | 0.77 | 0.45 | 12.1 | 97% |
| scan12 | 0.81 | 1.00 | 72.5 | 96% |
| scan14 | 0.39 | 1.26 | 69.5 | 89% |
| scan15 | 0.63 | 0.33 | 77.4 | 95% |
| scan16 | 1.73 | 4.14 | 178.3 | 96% |
| scan17 | 1.10 | 1.54 | 172.4 | 92% |
| scan18 | 1.01 | -0.01 | 176.1 | 91% |
| scan19 | -0.15 | 0.57 | 172.8 | 95% |
| scan20 | 0.97 | 1.07 | 83.3 | 81% |
| scan21 | -2.41 | 5.13 | -172.0 | 87% |
| scan22 | -3.55 | 2.19 | -170.7 | 96% |
| scan23 | 0.71 | 1.55 | 7.8 | 99% |
| scan24 | 1.68 | 2.52 | 90.9 | 100% |
| scan25 | 0.57 | 3.98 | 1.8 | 100% |
| scan26 | -3.44 | 2.20 | -88.4 | 100% |
| scan27 | -2.49 | 4.97 | -82.3 | 94% |
| scan28 | 0.66 | 0.46 | 68.1 | 100% |
| scan29 | 2.07 | 3.62 | 6.3 | 90% |
| scan30 | 1.75 | 2.52 | 80.2 | 98% |
| scan32 | 1.69 | 4.06 | -85.0 | 91% |
| scan33 | -3.41 | 2.07 | 97.4 | 100% |
| scan34 | -2.59 | 4.71 | 89.3 | 96% |
| scan35 | 1.31 | 0.70 | -103.9 | 93% |
| scan36 | 2.09 | 3.31 | 12.0 | 79% |
| scan37 | 0.22 | -0.72 | -12.8 | 99% |
| scan38 | 0.22 | -0.72 | -12.7 | 98% |
| scan39 | 1.40 | 0.93 | 76.9 | 87% |

![assemblage](1_assemblage.png)

## 4. Grid map (carte d'occupation)

Cellules de 5 cm, log-odds : chaque rayon (Bresenham) rend libres les cellules traversées et occupée la cellule d'impact.

- surface libre : 150.3 m², occupée : 3.7 m²

![grid map](2_grid_map.png)

## 5. Carte vectorielle (§3 et §4 du document)

- **segmentation** : rupture de cluster quand deux points successifs sont à plus de 20 cm ;
- **reconnaissance géométrique** : simplification polygonale (Douglas-Peucker, seuil 10 cm), puis droite des moindres carrés totaux sur chaque morceau ;
- **mise à jour** : un segment proche d'un segment existant (angle < 8°, écart latéral < 8 cm, trou < 20 cm) est **fusionné**, sinon **ajouté** ; chaque segment compte ses observations (confiance) ;
- **nettoyage** : segments de moins de 15 cm supprimés.

Résultat : 336 segments, dont 73 vus au moins 2 fois, 217.6 m de murs.

![carte vectorielle](3_carte_vectorielle.png)

Fichier `carte_vectorielle.txt` : une ligne `x1,y1,x2,y2` par segment (format du document).

## 6. Scans écartés

Les scans scan31 n'ont pas pu être rattachés de façon fiable. Ils contiennent surtout de **petits amas de points** (pieds de chaises, de tables, objets bas, personnes) et **peu de structures longues** (murs) : le recalage n'a presque rien de commun et de stable à superposer. Une seule ligne droite commune ne suffit pas non plus : le scan peut « glisser » le long d'elle.

C'est typiquement le cas d'un lidar **posé au sol** : un lidar 2D ne voit que dans **un seul plan** (cours, §5), et à quelques centimètres du sol ce plan coupe surtout des pieds de meubles. Placé plus haut (sur une table, sur le robot), il voit les murs et les plateaux. Les personnes qui se déplacent pendant la capture ajoutent des points différents d'un scan à l'autre (objets mobiles, §5 du document).

![scans écartés](4_scans_ecartes.png)

## 7. Limites

- pas d'intensité : les reflets et surfaces sombres ne peuvent pas être filtrés par qualité ;
- les positions sont estimées par recalage : une pièce très symétrique ou très encombrée peut donner un recalage faux (c'est pourquoi certains scans ont été écartés) ;
- le lidar voit dans un seul plan (hauteur du capteur) : tables, chaises et pieds de meubles apparaissent comme des points ou de petits segments ;
- objets mobiles (personnes) : vus dans un seul scan, ils donnent des segments à 1 observation.
