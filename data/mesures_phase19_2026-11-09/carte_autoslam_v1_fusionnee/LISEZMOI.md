# Carte vectorielle fusionnée — séance du 10/11

Source : `../carte_autoslam_v1_filtree/segments.csv` (non modifié).

Fusion avec les fonctions du projet `carto.segments.are_close` puis `merge` (fiche du cours, §4 « fusion »), répétée jusqu'à ce qu'aucune paire ne soit plus fusionnable. Tolérances fixées avant le calcul :
- angle entre les deux segments ≤ 5° ;
- écart latéral ≤ 10 cm (extrémités du plus court par rapport à la droite du plus long) ;
- trou le long du mur ≤ 30 cm (une porte, ≥ 80 cm, n'est pas refermée).

La direction fusionnée est la moyenne pondérée par les longueurs ; les extrémités sont les projections extrêmes ; n_obs est la somme.

- Avant : 59 segments, 84.8 m.
- Après : 58 segments, 85.1 m (1 fusions).

## Pourquoi presque rien n'a fusionné (diagnostic)

Les paires de segments longs et presque parallèles (angle < 2°) se rangent en deux cas :
- **murs doublés** : deux segments qui se recouvrent sur toute leur longueur mais sont décalés de **14 à 23 cm** latéralement. C'est le **même mur vu depuis des poses légèrement fausses** (dérive de l'Auto-SLAM), pas deux morceaux d'un mur. Les fusionner masquerait cette erreur de pose : ils sont laissés tels quels.
- **morceaux alignés** : écart latéral de 3 à 10 cm, mais trou de **30 à 34 cm**, juste au-dessus de la tolérance fixée (30 cm).

Conclusion : la carte n'a pas besoin d'une fusion plus agressive. Ce qu'il faut corriger, c'est la **dérive des poses** (correction de boucle, ou poses mesurées au sol).
