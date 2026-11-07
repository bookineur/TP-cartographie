# Conformité au cours : techniques appliquées et sources

Comparaison entre le code du projet et les supports du module « Cartographie et Localisation » (J. Quillès, 2026).

Les supports lus sont :
- les diapositives « Présentation du module », « Cartographie » et « Localisation » ;
- les fiches *Scan matching*, *Localisation*, *Expression de la pose*, *Construction d'une carte vectorielle 2D*, *Acquisition des données issues du Lidar LD06* et *Utiliser les outils du module*.

Légende :
- **✅ cours** : technique décrite dans le cours ;
- **≈ variante** : technique du cours, réalisée avec un détail de calcul qui n'y figure pas ;
- **⚠️ hors cours** : technique qui ne vient pas du cours (à justifier, à remplacer ou à retirer).

## 1. Acquisition et prétraitement

| Ce que fait le code | Fichier | Source dans le cours | Verdict |
|---|---|---|---|
| Polaire → cartésien, puis `P_global = R(θ)·P_local + T` | `carto/scan.py` (`Pose.transform`) | Fiche carte vectorielle §2 ; fiche LD06 §2 et §6 ; fiche Pose | ✅ cours |
| Angles LD06 dans le sens horaire, inversés en sens trigo | `carto/scan.py`, option « miroir Teleplot » | Fiche LD06 §3 et §5 (θmath = −θLD06) | ✅ cours |
| Suppression des points trop proches ou trop lointains (10 cm à 10 m, ou `--portee-max`), à faible intensité, ou isolés | `carto/register.py` (`clean_scan`) | Fiche carte vectorielle §2 (points « trop lointains, intensité trop faible, incohérents ») ; fiche Scan matching §9 | ✅ cours |

## 2. Grid map

| Ce que fait le code | Fichier | Source | Verdict |
|---|---|---|---|
| Cellules avec une probabilité d'occupation | `carto/gridmap.py` | Diapo Cartographie 6 | ✅ cours |
| Probabilité stockée en log-odds (l = log p/(1−p)), mise à jour par addition | `carto/gridmap.py` | Le cours parle de probabilité, pas de log-odds. C'est la façon usuelle de mettre à jour cette probabilité. | ≈ variante |
| Cellules traversées par le rayon marquées libres (méthode supercover) | `carto/gridmap.py` (`supercover`) | MapTool du prof (« fix supercover ») ; diapo Cartographie 5 (« nettoie : suppression d'obstacles qui ont disparu ») | ✅ cours |

## 3. Carte vectorielle

| Ce que fait le code | Fichier | Source | Verdict |
|---|---|---|---|
| Coupure du nuage aux sauts de distance entre points successifs (clusters) | `carto/segments.py` (`split_clusters`) | Fiche carte vectorielle §3.1 | ✅ cours |
| Découpe récursive Douglas-Peucker / Iterative End-Point Fit | `carto/segments.py` (`_split`, `_split_merge`) | Fiche carte vectorielle §3.2 (« Douglas–Peucker ») | ✅ cours |
| Ajustement d'une droite par moindres carrés totaux (ACP) | `carto/segments.py` | Fiche §3.2 (« régression linéaire »). Les moindres carrés totaux en sont la version qui fonctionne aussi pour les murs verticaux. | ≈ variante |
| Comparaison avec les segments existants (angle, distance), puis fusion | `carto/vectormap.py` (`_integrate`, `_consolidate`) | Fiche §4 (fusion, « cas le plus courant ») | ✅ cours |
| Raccourcissement ou coupure d'un segment traversé par un rayon | `carto/vectormap.py` (`_cut_with_rays`) | Fiche §5 (détection d'absence) | ✅ cours |
| Compteur d'observations, segment « confirmé » à partir de 2 observations | `carto/vectormap.py` (`confirmed`) | Fiche §1 (« compteur de confiance ») | ✅ cours |
| Fichier `x1,y1,x2,y2`, une ligne par segment | `carte_vectorielle.txt` | Fiche §1 ; fiche Outils | ✅ cours |

## 4. Assemblage des scans (construction de la carte)

| Ce que fait le code | Fichier | Source | Verdict |
|---|---|---|---|
| Recalage de deux scans par corrélation : essai de chaque rotation de 0 à 360° par pas de 2°, translation trouvée par corrélation | `carto/register.py` (`match_global`) | Fiche Localisation §3e et §4d (« Correlative Scan Matching ») ; fiche Scan matching §8.1 (brute force). La FFT ne sert qu'à calculer cette corrélation plus vite. | ✅ cours |
| Affinage par ICP point-à-point | `carto/register.py` (`refine`) | Fiche Localisation §3e et §4d ; fiche Scan matching §8.3 | ✅ cours |
| **Scan matching successif** : chaque scan, dans l'ordre de capture, est recalé sur le scan précédent, affiné par ICP sur la carte déjà construite, puis ajouté à la carte. C'est la méthode par défaut depuis la version 2. | `carto/register.py` (`assemble_successif`) | Fiche Localisation §4d (« Lidar – scan matching successif ») ; diapo Cartographie 5 (processus général) ; fiche carte vectorielle §6 (« alignement lidar ↔ carte ») | ✅ cours |
| Refus des recalages ambigus (deux rotations très différentes qui collent presque aussi bien) | `carto/register.py` (`Match.ambiguity`) | Fiche Scan matching §8 (« éviter les correspondances ambiguës ») | ✅ cours |
| Ancienne méthode : toutes les paires, puis **arbre couvrant maximal (Kruskal)** | `carto/register.py` (`assemble`), option `--toutes-paires` | Absent du cours ; n'est plus utilisée par défaut | ⚠️ hors cours (option) |
| Redressement de la carte (murs parallèles aux axes) par la moyenne circulaire de 4·orientation | `carto/build_map.py` (`_wall_alignment`) | Absent du cours. C'est une rotation d'affichage, désactivable avec `--sans-redressement`. | ⚠️ hors cours |

## 5. Localisation (TP jour 2)

| Méthode | Fichier | Source | Verdict |
|---|---|---|---|
| Score grid map : distance aux cellules occupées (champ de vraisemblance) | `carto/localisation.py` (`GridRef`) | Fiche Scan matching §4 (« distance aux cellules occupées les plus proches ») | ✅ cours |
| Score carte vectorielle : distance point → segment le plus proche, au carré et pondérée | `carto/localisation.py` (`VectorRef`) | Fiche Scan matching §5 (E = Σ wᵢ d²) | ✅ cours |
| Score entre scans : point-à-point, ou point-à-droite locale | `carto/localisation.py` (`CloudRef`) | Fiche Scan matching §6 (point-à-point). Le point-à-droite est une variante du même calcul. | ✅ / ≈ |
| Recherche exhaustive (brute force) | `brute_force` | Fiche Scan matching §8.1 ; énoncé | ✅ cours |
| Multi-résolution | `multi_resolution` | Fiche Scan matching §8.2 ; énoncé | ✅ cours |
| Gauss-Newton / Levenberg-Marquardt | `gauss_newton` | Fiche Scan matching §8.3 | ✅ cours |
| ICP | `icp` | Fiche Scan matching §8.3 ; fiche Localisation §3e | ✅ cours |
| Filtre de particules | `particles` | Fiche Scan matching §8.4 ; fiche Localisation §5b (MCL) | ✅ cours |
| Calcul direct par moments (barycentre, axe d'inertie) | `direct_moments` | Fiche Scan matching §8.5 | ✅ cours |
| Calcul direct par les murs (orientation des segments, puis moindres carrés) | `direct_murs` | Fiche Scan matching §7 (« calcul géométrique direct possible ») ; le calcul de l'orientation (moyenne de 4φ) est à nous | ≈ variante |
| Poids de Cauchy pour réduire l'effet des points aberrants | `gauss_newton` | Le cours prévoit des poids wᵢ et cite la sensibilité aux outliers ; le choix de Cauchy est à nous | ≈ variante |

## 6. Évaluation

| Ce que fait le code | Fichier | Source | Verdict |
|---|---|---|---|
| Mêmes scans et mêmes poses initiales pour toutes les méthodes ; erreurs (m, °), temps, taux de réussite avec seuils explicites ; pose initiale variée | `carto/evaluation.py` | Énoncé du jour 2 | ✅ cours |
| Incertitude des poses mesurées estimée par la répétabilité (robot reposé sur le même repère) | `carto/evaluation.py` (`repeatability`) | Énoncé (« indiquez l'incertitude des références mesurées ») | ✅ cours |
| Précision du recalage estimée par l'approximation de Laplace | `carto/localisation.py` (`pose_covariance`) | Absent du cours | ⚠️ hors cours |
| Intervalle de confiance de Wilson sur les taux | `carto/evaluation.py` (`wilson`) | Absent du cours. Ce n'est pas une technique de localisation, seulement de la statistique pour présenter les résultats. | ⚠️ hors cours |

## 7. Ce qu'il faut retenir pour le rapport et les commits

1. **Toutes les méthodes de localisation demandées viennent du cours.** C'est le cas des méthodes sur grid map, sur carte vectorielle et entre scans : brute force, multi-résolution, gradient, ICP, particules, calcul direct.
2. **La carte vectorielle suit la fiche du prof étape par étape** : clusters, Douglas-Peucker, fusion, détection d'absence, compteur de confiance.
3. **Éléments hors cours** (le premier est corrigé en version 2) : Pour chacun, voici ce que je propose :
   - **Arbre couvrant maximal (assemblage)** : **remplacé par défaut en version 2** par le scan matching successif du cours, avec un départ local depuis la pose du scan précédent puis un recalage global non ambigu.
     - **Résultat mesuré** : sur une trajectoire simulée de 101 scans pris en roulant, la méthode successive met 29 s, avec 8 cm d'erreur médiane et 12 cm de dérive.
     - **Limite à écrire dans le rapport** : sur nos 39 scans réels mélangés (trois sessions, sans ordre de capture), elle ne place correctement que 10 scans. Le cours le prévoit : le scan matching successif suppose des scans pris près les uns des autres. Pour ce jeu de données, on garde l'ancienne méthode en option (`--toutes-paires`), en la signalant comme hors cours.
   - **Redressement des murs** : le présenter comme un simple choix d'affichage, ou toujours utiliser `--sans-redressement`.
   - **Covariance de Laplace** : la retirer du rapport, ou la placer en annexe « pour information ». L'incertitude demandée par l'énoncé vient de la répétabilité, qui suit le cours.
   - **Intervalle de Wilson** : à garder, en le présentant comme de la statistique de présentation, pas comme une méthode.
4. **Techniques du cours pas encore utilisées**, en pistes facultatives :
   - RANSAC (segments, ou probabiliste) ;
   - recuit simulé ;
   - mise en correspondance feature-à-feature (segments, coins) ;
   - cercles et arcs dans la carte vectorielle ;
   - NDT ;
   - correction de boucle et optimisation des poses (Graph-SLAM).

   Le filtre de Kalman et l'odométrie ne s'appliquent pas : le robot n'a pas de roues codeuses.
