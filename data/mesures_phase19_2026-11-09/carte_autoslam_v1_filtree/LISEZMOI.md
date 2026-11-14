# Carte vectorielle filtrée — séance du 10/11

Source : `../carte_autoslam_v1/segments.csv` (non modifié).

Règle annoncée avant le filtrage : garder les segments **vus au moins 2 fois** (n_obs ≥ 2), c'est-à-dire confirmés par au moins deux scans. Aucun autre critère.

- Avant : 166 segments, longueur totale 119.5 m.
- Après : 59 segments, longueur totale 84.8 m (71 % de la longueur conservée).

Les segments retirés sont surtout des objets vus une seule fois (pieds de chaises, bruit, objets à la limite de portée).
