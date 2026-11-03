# Versions de la carte de la salle

| version | commande | contenu |
|---|---|---|
| `version_1` | `python -m carto assemble data\salle_2026-11-02_18h31 --scans 1-9 --sans-redressement` | Première carte : scans 1 à 9 assemblés, dans l'orientation du scan de référence (carte inclinée d'environ 5°). Rapport en 6 sections, sans les scans 10 à 14. |
| `version_2` | `python -m carto assemble data\salle_2026-11-02_18h31 --scans 1-9 --ecartes 10-14` | Carte redressée (murs parallèles aux axes, rotation de +4,9°). Le rapport ajoute la colonne « points sur des murs », la section 6 « Scans écartés » (lidar au sol) et la figure `4_scans_ecartes.png`. |

Chaque nouvelle exécution de `python -m carto assemble` crée automatiquement le dossier suivant (`version_3`, `version_4`…) sans modifier les précédents.

Remarque : la version 1 a été régénérée avec le même calcul que la toute première exécution (recalage déterministe), donc les mêmes images et les mêmes positions. Seul son rapport contient en plus la colonne « points sur des murs », ajoutée au programme entre-temps.
