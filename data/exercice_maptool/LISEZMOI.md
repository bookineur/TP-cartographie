# Scans faits avec MapTool (salle 7 m x 5 m : porte, armoire, table)

`scan1.csv` à `scan8.csv` : exportés par MapTool (« Exporter Scan Lidar »), 450 rayons, bruit 2 cm / 0,3°.
Format MapTool : `angle_deg,r_m,x_rel_m,y_rel_m` ; la 1re ligne donne la position du robot (ne pas la regarder
si on veut s'entraîner à l'assemblage).

1. Assembler : `python -m carto assemble data/exercice_maptool --sans-redressement`
   ou à la main dans Lidar Plot (« 📂 Ouvrir… » sur ce dossier).
2. Comparer la grid map obtenue avec `correction/grid_map_maptool.png` (grid map exportée par MapTool).
