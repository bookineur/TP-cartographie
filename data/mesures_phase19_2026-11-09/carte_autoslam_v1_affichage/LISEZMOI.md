# Carte vectorielle — VERSION D'AFFICHAGE (séance du 10/11)

**À n'utiliser que pour illustrer.** Cette version fusionne des murs doublés, décalés d'environ 14 à 23 cm à cause de la dérive des poses de l'Auto-SLAM. Elle **masque cette dérive** : elle ne doit servir ni à mesurer une précision ni à localiser.

Source : `../carte_autoslam_v1_filtree/segments.csv` (non modifié). Fusion `carto.segments.are_close` puis `merge`, répétée jusqu'à stabilité. Tolérances : angle ≤ 5°, **écart latéral ≤ 25 cm** (contre 10 cm dans `carte_autoslam_v1_fusionnee`), trou ≤ 30 cm.

- Avant : 59 segments, 84.8 m.
- Après : 53 segments, 79.3 m (6 fusions).

Pour le rapport : présenter `carte_autoslam_v1_fusionnee` comme la carte mesurée, et celle-ci comme une illustration, en citant l'écart masqué.
