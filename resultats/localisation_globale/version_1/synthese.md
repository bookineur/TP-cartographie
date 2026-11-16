# Localisation globale d'un scan — résultats (séance réelle du 10/11)

Protocole : `PROTOCOLE.md` (écrit et committé avant la mesure). Référence de comparaison : poses de l'Auto-SLAM, **pas une vérité terrain**.

| Référence | scans | concordant (< 10 cm, < 2°) | proche (< 30 cm, < 5°) | faux positif | refusé | écart médian des acceptés | temps moyen |
|---|---|---|---|---|---|---|---|
| grid map | 48 | 42 | 1 | 0 | 5 | 1.8 cm / 0.29° | 3.3 s |
| carte vectorielle | 48 | 47 | 0 | 0 | 1 | 2.5 cm / 0.28° | 3.1 s |

## Critères annoncés

- grid map : 0 faux positif → **atteint** (0) ; ≥ 80 % concordants ou proches → **atteint** (43/48 = 90 %)
- carte vectorielle : 0 faux positif → **atteint** (0) ; ≥ 80 % concordants ou proches → **atteint** (47/48 = 98 %)

## Scan par scan

| scan | grid map | carte vectorielle |
|---|---|---|
| scan1 | refusé (230 cm, 0.9°, p=0.56, rival=0.53) | concordant (3 cm, 1.3°, p=0.76, rival=0.57) |
| scan2 | refusé (286 cm, 179.2°, p=0.55, rival=0.54) | concordant (3 cm, 0.8°, p=0.74, rival=0.55) |
| scan3 | refusé (282 cm, 179.1°, p=0.55, rival=0.55) | concordant (3 cm, 0.9°, p=0.77, rival=0.56) |
| scan4 | concordant (1 cm, 0.7°, p=0.64, rival=0.39) | concordant (2 cm, 0.1°, p=0.81, rival=0.52) |
| scan5 | concordant (1 cm, 0.4°, p=0.64, rival=0.43) | concordant (2 cm, 0.2°, p=0.83, rival=0.52) |
| scan6 | concordant (2 cm, 0.7°, p=0.65, rival=0.41) | concordant (2 cm, 0.2°, p=0.84, rival=0.53) |
| scan7 | concordant (6 cm, 1.1°, p=0.74, rival=0.47) | concordant (7 cm, 1.4°, p=0.86, rival=0.54) |
| scan8 | concordant (2 cm, 0.5°, p=0.79, rival=0.55) | concordant (3 cm, 0.3°, p=0.74, rival=0.58) |
| scan9 | concordant (4 cm, 0.2°, p=0.77, rival=0.57) | concordant (2 cm, 0.0°, p=0.73, rival=0.61) |
| scan10 | concordant (3 cm, 1.0°, p=0.69, rival=0.63) | concordant (1 cm, 0.0°, p=0.82, rival=0.66) |
| scan11 | refusé (1 cm, 1.0°, p=0.61, rival=0.60) | concordant (0 cm, 0.6°, p=0.86, rival=0.65) |
| scan12 | concordant (1 cm, 0.3°, p=0.79, rival=0.60) | concordant (2 cm, 0.1°, p=0.80, rival=0.65) |
| scan13 | concordant (2 cm, 0.1°, p=0.86, rival=0.59) | concordant (2 cm, 0.2°, p=0.83, rival=0.66) |
| scan14 | concordant (1 cm, 0.0°, p=0.88, rival=0.68) | concordant (1 cm, 0.3°, p=0.86, rival=0.71) |
| scan15 | concordant (2 cm, 0.0°, p=0.87, rival=0.66) | concordant (1 cm, 0.3°, p=0.85, rival=0.71) |
| scan16 | concordant (4 cm, 0.3°, p=0.82, rival=0.59) | concordant (3 cm, 0.7°, p=0.81, rival=0.58) |
| scan17 | concordant (3 cm, 0.4°, p=0.84, rival=0.60) | concordant (1 cm, 0.4°, p=0.85, rival=0.68) |
| scan18 | concordant (1 cm, 0.2°, p=0.75, rival=0.51) | concordant (0 cm, 0.6°, p=0.77, rival=0.52) |
| scan19 | concordant (3 cm, 0.1°, p=0.81, rival=0.61) | concordant (0 cm, 0.1°, p=0.84, rival=0.62) |
| scan20 | concordant (5 cm, 0.5°, p=0.71, rival=0.59) | concordant (6 cm, 0.1°, p=0.83, rival=0.65) |
| scan21 | concordant (1 cm, 0.1°, p=0.75, rival=0.52) | concordant (2 cm, 0.1°, p=0.85, rival=0.56) |
| scan22 | concordant (1 cm, 0.2°, p=0.81, rival=0.51) | concordant (1 cm, 0.8°, p=0.90, rival=0.61) |
| scan23 | concordant (1 cm, 0.2°, p=0.77, rival=0.51) | concordant (2 cm, 0.5°, p=0.81, rival=0.55) |
| scan24 | concordant (3 cm, 0.5°, p=0.81, rival=0.58) | concordant (3 cm, 0.3°, p=0.79, rival=0.54) |
| scan25 | refusé (5 cm, 0.6°, p=0.59, rival=0.57) | concordant (5 cm, 0.3°, p=0.80, rival=0.62) |
| scan26 | concordant (5 cm, 0.7°, p=0.73, rival=0.49) | concordant (4 cm, 0.1°, p=0.82, rival=0.56) |
| scan27 | concordant (2 cm, 0.2°, p=0.85, rival=0.63) | concordant (1 cm, 0.0°, p=0.88, rival=0.65) |
| scan28 | concordant (1 cm, 0.0°, p=0.89, rival=0.71) | concordant (3 cm, 0.2°, p=0.90, rival=0.73) |
| scan29 | concordant (1 cm, 0.2°, p=0.85, rival=0.73) | concordant (1 cm, 0.6°, p=0.88, rival=0.74) |
| scan30 | concordant (1 cm, 0.3°, p=0.86, rival=0.67) | concordant (3 cm, 0.2°, p=0.90, rival=0.70) |
| scan31 | concordant (1 cm, 0.4°, p=0.90, rival=0.72) | concordant (2 cm, 0.4°, p=0.94, rival=0.77) |
| scan32 | concordant (1 cm, 0.2°, p=0.89, rival=0.66) | concordant (2 cm, 0.2°, p=0.90, rival=0.68) |
| scan33 | concordant (1 cm, 0.3°, p=0.89, rival=0.64) | concordant (3 cm, 0.1°, p=0.95, rival=0.71) |
| scan34 | concordant (4 cm, 0.6°, p=0.82, rival=0.66) | concordant (4 cm, 0.8°, p=0.93, rival=0.72) |
| scan35 | concordant (1 cm, 0.3°, p=0.80, rival=0.70) | concordant (3 cm, 0.1°, p=0.88, rival=0.69) |
| scan36 | concordant (1 cm, 0.0°, p=0.76, rival=0.49) | concordant (4 cm, 0.5°, p=0.76, rival=0.59) |
| scan37 | concordant (2 cm, 0.1°, p=0.80, rival=0.54) | concordant (4 cm, 0.2°, p=0.77, rival=0.59) |
| scan38 | concordant (2 cm, 0.0°, p=0.82, rival=0.63) | concordant (1 cm, 0.4°, p=0.80, rival=0.65) |
| scan39 | concordant (1 cm, 0.5°, p=0.85, rival=0.74) | concordant (5 cm, 0.2°, p=0.83, rival=0.74) |
| scan40 | concordant (2 cm, 0.3°, p=0.82, rival=0.66) | refusé (253 cm, 3.8°, p=0.74, rival=0.69) |
| scan41 | concordant (8 cm, 0.6°, p=0.93, rival=0.65) | concordant (6 cm, 0.0°, p=0.92, rival=0.67) |
| scan42 | concordant (4 cm, 0.2°, p=0.94, rival=0.73) | concordant (2 cm, 0.5°, p=0.95, rival=0.69) |
| scan43 | concordant (6 cm, 0.3°, p=0.92, rival=0.72) | concordant (6 cm, 0.2°, p=0.93, rival=0.70) |
| scan44 | concordant (6 cm, 0.9°, p=0.83, rival=0.57) | concordant (8 cm, 0.1°, p=0.90, rival=0.59) |
| scan45 | concordant (2 cm, 0.5°, p=0.85, rival=0.58) | concordant (1 cm, 0.8°, p=0.87, rival=0.60) |
| scan46 | concordant (4 cm, 1.0°, p=0.60, rival=0.49) | concordant (2 cm, 0.7°, p=0.66, rival=0.53) |
| scan47 | proche (11 cm, 0.8°, p=0.74, rival=0.62) | concordant (6 cm, 0.4°, p=0.82, rival=0.66) |
| scan48 | concordant (5 cm, 0.4°, p=0.57, rival=0.35) | concordant (4 cm, 0.1°, p=0.62, rival=0.40) |

## Reproductibilité

Le calcul a été lancé deux fois (le premier lancement, cru arrêté, tournait encore). Les deux
donnent des résultats identiques sur les 96 lignes, temps de calcul mis à part.
`journal.txt`, `resultats.csv` et `resultats.json` sont ceux du second lancement.

## Lecture

- Les refus ont évité 4 fausses poses à plus de 2 m (grid map : scans 1 à 3 ; carte vectorielle :
  scan 40) : un rival presque aussi bon a déclenché le refus.
- Deux refus « par prudence » sur la grid map (scans 11 et 25) : la pose était juste, mais un rival
  était trop proche pour décider.
- Écarts mesurés par rapport à l'Auto-SLAM, qui n'est pas une vérité terrain.
