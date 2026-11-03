# Exercice d'assemblage (salle simulée 7 m x 5 m)

8 scans (`scan1.csv` à `scan8.csv`) pris depuis des positions inconnues. La salle a une porte (mur du bas),
une armoire contre le mur de gauche et une table au milieu.

À faire :
1. Assembler : `python -m carto assemble data/exercice_assemblage --sans-redressement`
   (ou à la main dans Lidar Plot : « 📂 Ouvrir… » sur ce dossier, puis éditeur de position).
2. Regarder `carte/version_1/2_grid_map.png` et `3_carte_vectorielle.png`.
3. Comparer avec la correction : `correction/gridmap_reference.png`, `correction/poses_vraies.json`
   (ne pas l'ouvrir avant d'avoir essayé).

Une rotation globale de la carte est normale : le premier scan sert de repère.
