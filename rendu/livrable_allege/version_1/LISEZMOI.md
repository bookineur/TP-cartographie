# Livrable allégé (limite d'envoi de 20 Mo)

Le ZIP allégé contient une copie filtrée de ce dépôt (les 80 commits sont gardés) :

1. Clone du dépôt, puis retrait des fichiers lourds produits pour le rendu dans tout l'historique :
   `git filter-branch --index-filter 'git ls-files -z | grep -zE "(\.(docx|pdf|mp4|zip|bundle)$)|(^rendu/.*\.(png|jpg|jpeg|emf|gif)$)" | xargs -0 -r git rm -q --cached --ignore-unmatch' -- --all`
2. Recompression des autres PNG en 256 couleurs (`recompresser_png.py`, qui écrit la table des blobs),
   puis remplacement dans tout l'historique : `git filter-branch --index-filter "python remplacer_png.py table_png.txt" -- --all`.
3. `git gc --aggressive`, puis `git bundle create ... --all`.

Rapport : `rendu/rapport_final/version_17` (vidéos 720p, images recompressées).
Résultat : ZIP de 17,1 Mo ; 65 tests réussis sur le dépôt filtré.
