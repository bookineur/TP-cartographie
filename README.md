# TP Jour 1 : LD06, extraction, visualisation et cartographie

```
arduino/LD06_capture/   sketch Arduino/Teensy : envoie les scans en CSV
ld06/protocol.py        décodage du protocole LD06 (miroir Python de la librairie)
ld06/capture.py         capture série -> fichiers CSV (étape 1)
ld06/sources.py         lecture en direct (Teleplot, CSV, LD06 binaire, simulation) dans un thread
carto/plot_app.py       Lidar Plot : visualiseur temps réel façon Teleplot + captures + exports
carto/theme.py          thèmes visuels (sombre pour Lidar Plot, clair pour l'assistant)
carto/assistant.py      assistant de capture guidée (fenêtre)
carto/guide.py          qualité des scans, recouvrement, recalage, suggestions de positions
carto/scan.py           scans, poses, lecture/écriture CSV
carto/viewer.py         visualiseur multi-scans, poses éditables (étape 2)
carto/gridmap.py        grid map : création + mise à jour (étape 3)
carto/segments.py       segments : extraction, angle, proximité, fusion, intersection, découpe (étape 4)
carto/vectormap.py      carte vectorielle (étape 5)
carto/simulate.py       scans simulés pour tester sans lidar
tests/                  32 tests (pytest), dont les cas limites de la découpe
Lidar Plot.bat          double-clic pour lancer Lidar Plot
```

Installation : `pip install -r requirements.txt` (Python 3.10 ou plus récent).

## Lidar Plot : le scan en direct, façon Teleplot

On lance l'application par un double-clic sur **`Lidar Plot.bat`**, ou en ligne de commande :

```bash
python -m carto plot
```

1. **Barre du haut.** Choisir le **port** du robot, laisser **Débit = Auto**, puis cliquer sur **Connecter**. En mode Auto, l'application écoute le port à 115 200 bauds (exemple `Basic`, format Teleplot), puis à 921 600 bauds (sketch `LD06_capture`, format CSV), puis à 230 400 bauds (LD06 branché en direct). Elle en déduit le débit et le format.
2. **Au centre, la carte en direct** (points bleu clair), avec des anneaux tous les mètres :
   - molette : zoom ;
   - glisser : déplacer la vue ;
   - double-clic : recentrer.

   En bas de la fenêtre, la position du curseur s'affiche en x, y, distance et angle.
3. **Pause (Espace)** fige l'image, qui passe en orange. **Capturer (Entrée)** enregistre exactement ce qui est affiché :
   - **Scan 1 en vert**, Scan 2 en orange, Scan 3 en violet, et ainsi de suite ;
   - chaque scan est aussitôt sauvé dans le dossier de la session, `scanK.csv`, avec `poses.json` ;
   - **Session** : **« ＋ Nouvelle session »** demande un nom (par exemple « salle B204 ») et crée `data/salle_B204/` ; la carte repart de zéro, et les anciennes sessions restent intactes sur le disque. **« 📂 Ouvrir… »** reprend n'importe quelle session. Au lancement, la dernière session utilisée est rouverte (`data/.derniere_session`).
4. **Scans capturés.** Pour chaque scan : afficher ou masquer, sélectionner, supprimer (le fichier va dans `_supprimes/`). Pour superposer des scans pris à des endroits différents, on donne au scan sélectionné la **position du lidar** (x, y, θ) ; **« Recaler sur les autres scans »** l'ajuste ensuite automatiquement par corrélation, à condition que la position saisie soit à moins de 40 cm et 8° près.
5. **Exporter :**
   - **Image PNG** sur fond blanc, pour le rapport ;
   - **Excel (`scans_lidar.xlsx`)**, avec quatre onglets :
     - **Carte** : l'image ;
     - **Graphique** : un vrai nuage de points Excel, une couleur par scan, axes à la même échelle, modifiable ;
     - **Résumé** : une ligne par scan ;
     - **Points** : tous les points, en nombres, avec filtres. Les points valides de chaque scan viennent en premier.

     Un fichier CSV ne peut pas contenir d'image : pour voir la carte dans Excel, il faut ce classeur ;
   - **Tableau CSV** de tous les points : scan, n° de point, angle, distance, intensité, x et y dans le repère du lidar, pose, x et y dans le repère de la carte. Le séparateur est « ; » et la virgule est décimale, pour ouvrir le fichier directement dans Excel en français ;
   - **Tout exporter** : l'image, le tableau et un `resume.md` (tableau des scans avec points, part de points valides, distances min/max et pose).
6. **Assemblage à la main** : sélectionner un scan dans la liste, puis cocher **« 🖐 Déplacer à la souris »**. Glisser déplace le scan, la molette le tourne autour de la position du lidar (Maj : 0,1°). La pose est mise à jour dans les champs et dans `poses.json`. Une fois le scan posé à peu près, **« Recaler sur les autres scans »** termine l'alignement au centimètre.
7. **Intensité** :
   - « Couleur = intensité » colore chaque point de 0 (violet) à 255 (jaune) ;
   - « Intensité min » masque les points plus faibles que le seuil, à l'écran et dans l'image exportée ;
   - au survol d'un point, la barre du bas donne sa distance, son angle et son intensité ;
   - les statistiques indiquent la médiane, le minimum et le maximum, et la part des points sous le seuil.

   ⚠ Le format Teleplot ne transmet **pas** l'intensité. Pour la mesurer, il faut téléverser `arduino/ESP32_LD06_CSV_intensite`, qui envoie les scans en CSV à 921 600 bauds.
8. **Statistiques en direct** : points, part de points valides, fréquence des tours, distances min et max, format reçu. On y trouve aussi les variables Teleplot (`>nom:valeur`) et une **console série** (bouton en bas à gauche).

Dans la liste des ports, « Simulation (sans lidar) » permet de s'entraîner, avec le bouton « Déplacer le lidar virtuel ».

**À propos du miroir Teleplot.** La librairie calcule `y = −d·sin(angle_trigo)`, si bien que ses x et y sont en miroir par rapport à la salle réelle (c'est aussi ce qu'affiche le site Teleplot). L'option « Corriger miroir Teleplot », cochée par défaut, remet le bon sens. C'est vérifié en simulation : avec la correction, l'écart médian avec la vérité est de 21 mm ; sans elle, de 493 mm.

## Construire la carte de la pièce à partir des scans de Lidar Plot

```bash
python -m carto assemble data/salle_2026-11-02_18h31 --scans 1-9 --ecartes 10-14
```

`--ecartes` : scans laissés hors de la carte mais montrés dans le rapport. Par exemple, des scans pris avec le lidar au sol, où l'on ne voit presque que des pieds de meubles. La figure `4_scans_ecartes.png` compare la part de points situés sur des murs pour les scans utilisés et pour les scans écartés.

La commande suit les étapes du document « Construction d'une carte vectorielle 2D » et écrit tout dans `<session>/carte/` :

1. **Prétraitement.** On supprime :
   - les points trop proches (moins de 10 cm) ou trop lointains (plus de 10 m) ;
   - les **points isolés** (moins de 2 voisins à moins de 15 cm) ;
   - les points de **faible intensité** (moins de 50), seulement si l'intensité a été transmise. Le format Teleplot ne la transmet pas : pour filtrer par intensité, il faut activer `ld06.enableFiltering(); ld06.setIntensityThreshold(...)` sur le robot, ou envoyer en CSV.
2. **Assemblage.** Si les positions du robot n'ont pas été mesurées (`--use-poses` pour utiliser `poses.json`), elles sont retrouvées par **recalage global** (`carto/register.py`) :
   - pour chaque paire de scans et chaque rotation de 0 à 360°, la translation est cherchée par corrélation FFT ;
   - le résultat est affiné par ICP ;
   - un arbre de recouvrement maximal relie les scans ;
   - les scans sans recouvrement fiable sont écartés et signalés.

   La carte est ensuite redressée pour que les murs soient parallèles aux axes.
3. **Grid map** : `2_grid_map.png` et `gridmap.npz`.
4. **Carte vectorielle** : `3_carte_vectorielle.png`, `carte_vectorielle.txt` (une ligne `x1,y1,x2,y2` par segment, comme dans le document) et `segments.csv`.
5. **Fichiers complémentaires :**
   - `1_assemblage.png` : les scans superposés, une couleur par scan ;
   - `poses_assemblees.json` : les positions retrouvées ;
   - `rapport_carte.md` : la démarche, les tableaux et les limites ;
   - `session_assemblee/` : la session avec ses positions, à rouvrir dans Lidar Plot avec « 📂 Ouvrir… ».

Sur la salle simulée, l'assemblage retrouve les positions inconnues à quelques centimètres et moins de 2° près (`tests/test_register.py`).

## Autres commandes

```bash
python -m carto assistant --folder data/salle
python -m carto simulate --out data/sim
python -m carto view data/sim --poses data/sim/poses_init.json --save-poses data/sim/poses.json
python -m carto grid data/sim --poses data/sim/poses_truth.json --out out/grid --steps
python -m carto vector data/sim --poses data/sim/poses_truth.json --out out/vector
python -m pytest
```

---

## 1. Extraction des données lidar

### Le protocole (doc « LD06 Development manual » §3)

Un paquet fait **47 octets** et contient 12 mesures :

| octets | champ | détail |
|---|---|---|
| 1 | header | `0x54` (= 84 en décimal), choisi arbitrairement pour reconnaître le début de trame |
| 1 | ver_len | `0x2C` : les 5 bits de poids faible valent le nombre de points (`0x2C & 0x1F = 12`) ; c'est aussi, par coïncidence, la taille de la charge utile (2+2+36+2+2 = 44 = 0x2C) |
| 2 | speed | vitesse de rotation en °/s (LSB d'abord) |
| 2 | start_angle | en 0,01° : 1° → 100, 359,99° → 35 999 (< 65 535, max sur 2 octets) |
| 12×3 | mesures | distance sur 2 octets (mm) + confiance sur 1 octet (0 à 255, ~200 pour un objet blanc à moins de 6 m) |
| 2 | end_angle | en 0,01° |
| 2 | timestamp | en ms, revient à 0 après 30 000. **Ce champ manquait dans l'explication orale**, mais sans lui on n'arrive pas à 47 octets. |
| 1 | CRC | CRC-8 (polynôme 0x4D) calculé sur les 46 octets précédents |

Total : 1+1+2+2+36+2+2+1 = 47. Avec ~450 points par tour, il faut **environ 38 paquets** (450/12) pour couvrir un tour. Un paquet peut chevaucher 360°→0° (par exemple de 355° à 6°).

**Angles intermédiaires.** Seuls le premier et le dernier angle sont transmis. On interpole : `step = (end − start) / 11`, puis `angle_i = start + i·step`, en ajoutant 360 à l'écart si le paquet passe par 0°.

**Synchronisation.** Pour accepter une trame, on attend `0x54` suivi de `0x2C`. Si on démarre au milieu d'une trame, un `0x54` peut apparaître dans les données. La paire `0x54 0x2C` élimine presque tous ces faux départs, et le CRC élimine les rares qui restent. On se recale ensuite sur l'en-tête suivant.

**Repère.** Le capteur compte les angles dans le sens horaire (repère main gauche), avec 0° vers l'avant. La librairie, et tout ce projet, utilisent le sens trigo : `angle = 360 − angle_capteur`.

### Ce que fait la librairie (src/ld06.cpp)

| fonction | rôle |
|---|---|
| `init()` | ouvre Serial1 à 230 400 bauds (et la broche PWM du moteur si elle est donnée) |
| `readDataCRC()` | machine à états octet par octet : attend 0x54 puis 0x2C, remplit les 47 octets en calculant le CRC au vol et compare avec le dernier octet |
| `computeData()` | calcule les 12 angles, détecte la fin d'un tour (l'angle redescend après plus de 340° parcourus), convertit en sens trigo, filtre éventuellement, calcule x et y |
| `swapBuffers()` | double tampon : on remplit `_currentScan` pendant que l'utilisateur lit `_previousScan`, qui contient le dernier tour complet |
| `readScan()` | renvoie true quand un tour complet est disponible (ou à chaque paquet si `disableFullScan()`) |
| `printScanCSV()` / `printScanTeleplot()` | envoient le tour sur le port série |
| `enableFiltering()`, `setDistanceRange()`, `setIntensityThreshold()`, `setAngleRange()` | filtres optionnels |
| `setBasePosition()` / `setOffsetPosition()` | pose du robot et position du lidar sur le robot, pour obtenir des x et y dans le repère monde |

**Points à signaler en lisant le code :**

1. **Interpolation.** La librairie calcule `start + (i + 0.5)·(écart/12)`, alors que la doc donne `start + i·écart/11`. L'écart est inférieur à 0,4°, donc plus petit que l'erreur angulaire du capteur (2°). `ld06/protocol.py` suit la doc.
2. **x et y.** Ils sont calculés avec `y = −d·sin(angle_trigo)`, ce qui redonne le repère horaire du capteur : les x et y de la librairie sont en miroir par rapport à sa colonne angle. Les outils Python ignorent donc ces colonnes et recalculent x et y à partir de l'angle et de la distance.
3. **Bug dans `isChecksumOk()`.** On y lit `checksumFailCount = previousChecksumFailCount;`, alors qu'il faudrait `previousChecksumFailCount = checksumFailCount;`. Après la première erreur de CRC, la fonction renvoie false indéfiniment.
4. **CRC faux.** La librairie jette les 47 octets d'un coup. Un vrai paquet qui commencerait au milieu est perdu. Le parseur Python, lui, ne jette que l'octet d'en-tête et relance la recherche.
5. **Débit série.** Un tour imprimé en CSV pèse environ 12 ko, soit à peu près 1 s à 115 200 bauds. Pendant ce temps, le buffer UART du lidar déborde. Le sketch `arduino/LD06_capture` imprime donc un tour, puis jette le tour suivant (qui serait troué), et utilise 921 600 bauds (le débit est natif en USB sur Teensy).

### Procédure de capture

Montage A, avec la carte Arduino/Teensy :

- Installer le dossier `LD06/` dans `Documents/Arduino/libraries/`.
- Téléverser `arduino/LD06_capture`.
- Lancer :

```bash
python -m ld06.capture --port COM5 --mode arduino --count 5 --out data/salle --prefix pos1
```

Montage B, avec un adaptateur USB-UART branché directement sur le LD06 : `--mode raw`. Le décodage se fait alors en Python, et `--save-raw dump.bin` garde aussi les octets bruts, qu'on peut relire avec `--replay`.

Fichier produit (angles en sens trigo, 0° = avant du lidar) :

```
# speed_dps=3600 mode=arduino
angle_deg,distance_mm,intensity
0.80,1532,210
```

Le chargeur lit aussi directement un copier-coller du moniteur série (format `printScanCSV`, plusieurs tours séparés par des lignes vides).

**Dans la salle :** faites 3 à 5 positions. À chaque position, mesurez au mètre la position du lidar et notez à quoi correspond son 0° (la flèche sur le capot). Prenez plusieurs tours par position et écrivez les poses mesurées dans un `poses.json` : `{"pos1_000": [x_m, y_m, theta_deg], ...}`. Les deux premiers tours sont ignorés (`--skip 2`) le temps que le moteur se stabilise.

### Assistant de capture guidée

```bash
python -m carto assistant --folder data/salle
```

C'est une fenêtre qui guide la capture position par position (`carto/assistant.py`, analyses dans `carto/guide.py`) :

Une ligne en haut du panneau montre l'avancement : Connexion, 1re position, Positions, Rapport.

1. **Connexion.** Choisir le port de la carte, ou utiliser **« Détection auto »** : chaque port est écouté à 921 600 bauds, où l'on attend les lignes CSV du sketch, puis à 230 400 bauds, où l'on attend des paquets LD06 valides (en-tête et CRC). L'assistant en déduit à la fois le port et le montage.

   Si aucun tour n'arrive au bout de 6 s, le guide affiche un **diagnostic** selon ce qui a été reçu :
   - aucun octet : lidar arrêté, mauvais port ou Tx mal branché ;
   - du texte mais pas au format CSV : mauvais sketch ou mauvais débit ;
   - des octets mais aucun paquet valide : mauvais mode.

   « Simulation (sans lidar) » sert à s'entraîner : un **clic droit** sur la carte pose un lidar virtuel, avec un bruit de 30 mm comme dans la datasheet.
2. **Pose.** Saisir la pose mesurée au mètre. Le scan **en direct** (en rouge) se superpose à la carte déjà construite. On peut l'aligner à la souris : **glisser** pour le déplacer, **molette** pour le tourner (1°, ou 0,2° avec Maj).
   - Le **recouvrement** indique quelle part de ses points tombe sur des murs connus : au moins 70 %, la pose est cohérente ; de 30 à 70 %, elle est à vérifier ; moins de 30 %, elle est fausse.
   - Un **contrôle en direct** signale les problèmes **avant** la capture : tour incomplet, lidar masqué, objet collé contre le lidar.
   - **« Recaler sur la carte »** propose une correction (±40 cm, ±8°) obtenue par corrélation du scan avec la carte.
   - **« Aligner θ sur les murs »**, surtout utile pour la 1re position, corrige θ pour rendre les murs parallèles aux axes. On prend la moyenne circulaire de 4φ des segments du scan, pondérée par leur longueur, ce qui donne l'orientation des murs modulo 90°. Hypothèse : les murs sont perpendiculaires et l'axe x suit un mur. En simulation, l'erreur passe d'environ 2° à moins de 0,3°.

   Pour ces deux corrections, l'utilisateur accepte ou refuse.
3. **« Capturer ».** Les N tours enregistrés sont contrôlés automatiquement :
   - points par tour (tour incomplet ?) ;
   - mesures sans écho (lidar masqué, vitres ?) ;
   - points à moins de 15 cm (câble ou main contre le lidar ?) ;
   - stabilité entre tours (le lidar a bougé ? quelqu'un passait ?) ;
   - vitesse de rotation.

   Les tours sont ensuite enregistrés en CSV, avec `poses.json` et `journal.json`, puis intégrés à la grid map.
4. **Suggestions.** Des étoiles indiquent où se placer ensuite : ce sont les frontières entre zone libre et zone inconnue de la grid map. Avant de les chercher, on bouche les trous dus à l'écartement des rayons par une fermeture morphologique. Quand il n'en reste plus, l'assistant indique que la carte est complète.

5. **« Terminer ».** Écrit dans `rapport/` :
   - `gridmap.png` et `gridmap.npz` ;
   - `vectormap.png` et `segments.csv` ;
   - `rapport.md` : un tableau des positions (pose, points par tour, mesures sans écho, écart entre tours, recouvrement, alertes), les surfaces libre, occupée et inconnue, la frontière restante et les statistiques de la carte vectorielle. On peut le reprendre tel quel dans le compte rendu.

La session reprend là où on s'était arrêté (relecture du dossier), et « Retirer » met les fichiers d'une position dans `_retires/`.

**Hypothèse importante.** Le repère de la carte est défini par la pose de la **première** position. Une erreur de 4° sur cette mesure fait tourner toute la carte, et le recalage des positions suivantes reste cohérent avec la carte, pas avec la salle réelle. Mesurez donc la première position avec soin.

---

## 2. Visualisation des nuages de points

```bash
python -m carto view data/salle --poses data/salle/poses.json
```

- Pour chaque point : `p_local = (d·cos θ, d·sin θ)`, puis `p_carte = R(θ_pose)·p_local + (x, y)`.
- Chaque scan a sa couleur (palette tab10). Une flèche indique la pose et le cap du lidar.
- **La pose de chaque scan se modifie indépendamment.** On choisit le scan actif dans la liste, puis :
  - glisser à la souris (zoom et pan de la barre d'outils désactivés) ;
  - flèches : 5 cm, ou 1 cm avec Maj ;
  - molette, ou a / e : 1°, ou 0,1° avec Maj ;
  - saisie directe de x, y et θ ;
  - n : scan suivant.
- Les cases « Visible » masquent des scans, « Sauver poses » écrit le JSON, et les boutons « Grid map » et « Carte vectorielle » construisent les cartes avec les poses courantes.
- Points filtrés par défaut : distance 0 (pas d'écho), moins de 5 cm (boîtier, câbles) et plus de 12 m.

**Méthode de recalage manuel :** fixer le premier scan en (0, 0, 0), puis amener chaque autre scan à superposer ses murs sur ceux du premier, en commençant par l'angle (les murs parallèles) puis la translation. `data/sim/poses_init.json` contient des poses volontairement fausses pour s'entraîner ; la solution est dans `poses_truth.json`.

---

## 3. Grid map 2D

> Je n'avais pas le document « Construction d'une grid map 2D à partir d'un scan lidar ». J'ai appliqué la méthode standard (log-odds et Bresenham). Vérifiez que les étapes et le vocabulaire correspondent à ceux du document.

**Démarche** (`carto/gridmap.py`) :

1. **Discrétisation.** Les cellules font `res` de côté (5 cm par défaut, environ 3 fois la résolution du LD06). `origin` est le coin de la cellule [0, 0], et `cellule = floor((p − origin) / res)`.
2. **Rayons.** Pour chaque point, on trace avec Bresenham la ligne de cellules entre la cellule du lidar et la cellule d'impact. Les cellules traversées sont libres, la cellule d'impact est occupée.
3. **Log-odds.** Chaque cellule stocke `l = log(p / (1 − p))`, qui vaut 0 pour une cellule inconnue (p = 0,5). Une observation libre ajoute `l_free = −0,4`, une observation occupée ajoute `l_occ = +0,85`, et on borne l dans [−4, 4]. Additionner est équivalent à la mise à jour bayésienne, si on suppose les mesures indépendantes. La borne laisse la carte capable de changer (une porte qui s'ouvre, par exemple).
4. **Outil 1, `OccupancyGrid.from_scan(scan, pose)`** : dimensionne la grille autour du scan, avec une marge d'1 m, puis applique les étapes 2 et 3.
5. **Outil 2, `grid.update(scan, pose)`** : agrandit la grille si le scan déborde (avec `np.pad`, en gardant l'alignement des cellules), puis applique les étapes 2 et 3.

**Choix et hypothèses :**

- **Une seule mise à jour par cellule et par scan.** Près du lidar, une cellule est traversée par des centaines de rayons. Si chaque rayon comptait, elle passerait à « sûre » dès le premier scan.
- **Une cellule vue à la fois libre et occupée dans le même scan est comptée occupée.** Les rayons rasants traversent souvent la cellule d'un mur voisin.
- **Les mesures à 0 (pas d'écho) sont ignorées.** On pourrait les traiter comme « libre jusqu'à 12 m », mais une vitre ou un objet noir donne aussi 0 : ce serait dangereux.
- **Les poses sont supposées exactes.** Toute erreur de pose dédouble les murs.
- **Le lidar est supposé immobile pendant un tour**, donc sans correction de mouvement.

**Ajouts :**

- `decay` donne une durée de vie aux cellules : avant chaque mise à jour, `l *= (1 − decay)` ramène lentement la carte vers « inconnu », ce qui fait disparaître ce qui n'est plus revu.
- `hits` compte les impacts par cellule.
- `classify()` renvoie −1 (inconnu), 0 (libre) ou 1 (occupé), avec des seuils à 0,35 et 0,65.

**Limites :**

- Loin du lidar, les rayons s'écartent (à 1° d'écart, ils sont à 10 cm l'un de l'autre à 6 m). Des cellules libres ne sont jamais traversées, d'où les stries sur l'image.
- Après un seul scan, une cellule libre a p = 0,40, ce qui reste « inconnu » selon les seuils. Il faut au moins deux observations pour la confirmer.
- Le coût est en O(points × longueur des rayons). Mesuré à environ 15 ms par scan sur la salle simulée (8 × 6 m, 5 cm).

`--steps` enregistre une image après chaque scan, pour montrer la construction incrémentale.

---

## 4. Segments (`carto/segments.py`)

**Tolérance numérique.** `TOL = 1e-6 m` (1 µm) : c'est bien en dessous de la résolution du LD06 (15 mm), mais bien au-dessus des erreurs d'arrondi des flottants (~1e-14 m pour des coordonnées d'une dizaine de mètres). Deux droites sont considérées parallèles si `|sin(angle)| ≤ 1e-9`.

| outil | méthode |
|---|---|
| `extract_segments(points)` | **Split-and-Merge.** (1) On coupe le nuage, trié par angle, là où deux points consécutifs sont à plus de 20 cm. Le scan étant circulaire, on démarre au plus grand trou, pour ne pas couper un mur au passage 0°. (2) **Split** à la Douglas-Peucker : on coupe au point le plus loin de la corde tant qu'il est à plus de 10 cm, soit environ 3σ pour la précision de 30 mm donnée par la datasheet. Mesuré en simulation avec 30 mm de bruit : un seuil de 5 cm donne 67 morceaux pour 11 murs réels, 8 cm en donne 19 et 10 cm en donne 11. (3) **Merge** : on réunit deux morceaux consécutifs si la droite ajustée sur l'union de leurs points reste à moins de 10 cm de chaque point. Le bruit crée des coupures parasites, alors qu'un vrai coin donne un gros résidu. (4) **Ajustement** par moindres carrés totaux (ACP) : on minimise la distance orthogonale, ce qui marche aussi pour les murs verticaux, contrairement à y = ax + b. (5) On rejette les segments de moins de 15 cm ou de moins de 6 points. |
| `angle_between(s1, s2)` | angle entre les droites, dans [0, 90°], car un mur A→B et B→A sont le même mur. `oriented=True` donne l'angle signé entre les directions, dans ]−180°, 180°]. |
| `are_close(s1, s2)` | trois critères. **Angulaire** : angle ≤ 8°. **Latéral** : les extrémités du segment le plus court sont à moins de `dist_tol` de la droite du plus long. **Longitudinal** : une fois projetés sur le plus long, les deux segments se recouvrent, ou le trou entre eux est inférieur à `gap_tol`. |
| `merge(s1, s2)` | la direction est la moyenne des deux directions, pondérée par les longueurs (après avoir mis s2 dans le même sens que s1). La droite passe par le barycentre des milieux, et les extrémités sont les projections extrêmes des 4 extrémités. `n_obs` additionne les observations. |
| `intersection(s1, s2)` | on résout `p + t·r = q + u·s`. Le point est accepté si `t` et `u` sont dans [0, 1] à `TOL` près (extrémités comprises). Pour des segments parallèles ou colinéaires, la fonction renvoie `None`, car il n'y a pas de point unique. |
| `cut(cible, coupeur)` | exactement les règles de l'énoncé, détaillées ci-dessous. Renvoie `(segment, a_été_coupé)`. |

Règles de `cut`, toutes testées dans `tests/test_segments.py` :

- l'intersection doit être sur les deux segments. Si le coupeur touche la cible par son extrémité (jonction en T), on coupe bien ;
- l'intersection doit être strictement à l'intérieur de la cible, à plus de `TOL` de ses extrémités. À 0,5·TOL d'une extrémité, rien ne change ; à 2·TOL, on coupe ;
- segments colinéaires (chevauchants ou non) ou parallèles : pas de découpe ;
- on garde le côté le plus long. En cas d'égalité à `TOL` près, on garde le côté qui contient `p1`. Si on inverse la cible, c'est donc l'autre moitié qui est gardée.

---

## 5. Carte vectorielle (`carto/vectormap.py`)

> Même remarque qu'au point 3 : sans le document « Construction d'une carte vectorielle 2D », j'ai appliqué l'approche classique. Comparez avec les étapes du document.

Pour chaque scan et sa pose :

1. On transforme les points dans le repère carte.
2. On extrait les segments (outil 4.1).
3. Option `--cut-rays` : chaque rayon lidar, raccourci de 15 cm pour ne pas couper le mur qu'il touche, prouve qu'il n'y a rien sur son trajet. S'il traverse un segment de la carte, on découpe ce segment (outil 4.6) en gardant le plus long côté. C'est utile pour une porte qui était fermée et qui est maintenant ouverte.
4. **Association.** Chaque nouveau segment est comparé à la carte avec `are_close` (outil 4.3). S'il est proche d'un ou de plusieurs segments existants, ils sont fusionnés (outil 4.4) ; sinon, il est ajouté.
5. **Consolidation.** On refusionne les segments de la carte devenus proches, puis on supprime ceux de moins de 15 cm.

Chaque segment garde `n_obs`, le nombre d'observations qui l'ont formé. `confirmed(2)` ne garde que les segments vus au moins deux fois, ce qui élimine une personne qui passe ou du bruit. Le CSV exporté contient `x1, y1, x2, y2, length, n_obs`.

**Limites :**

- Tout dépend des poses : une erreur de 2° sur la pose fait 10 cm d'écart à 3 m, ce qui empêche la fusion.
- Les objets ronds (pieds de chaise, poubelles) donnent de petits segments instables.
- La découpe par rayons garde un seul côté. Si un rayon traverse le milieu d'un vrai mur, à cause d'une erreur de pose ou d'un reflet, on perd la plus petite moitié du mur. C'est pour cela que l'option est désactivée par défaut.
- La fusion est gloutonne : l'ordre des scans influence légèrement le résultat.

---

## Validation

- `pytest` : 32 tests. Ils couvrent :
  - le paquet d'exemple de la doc LD06 (§3.3) : CRC = 0x50, vitesse 2152 °/s, angles de 324,27° à 334,70°, mesures 224 mm et 220 mm ;
  - la resynchronisation après un CRC faux et un paquet coupé entre deux lectures ;
  - le passage 360°→0° ;
  - l'assemblage des tours ;
  - Bresenham ;
  - la grille : agrandissement, une seule mise à jour par cellule et par scan ;
  - toutes les règles de découpe ;
  - l'extraction d'une pièce carrée bruitée (on retrouve 4 murs de 4 m) ;
  - la carte vectorielle de la salle simulée.
- `out/grid/` et `out/vector/` : résultats sur la salle simulée (pièce en L de 8 × 6 m, cloison avec porte, pilier). La carte vectorielle retrouve tous les murs visibles, l'ouverture de la porte et deux faces du pilier ; les deux autres faces ne sont vues depuis aucune position.
- **Pas encore testé avec le vrai LD06 ni avec le montage Arduino** (pas de matériel ici). Le décodeur est validé sur le paquet de la doc, et la capture « raw » sur un flux d'octets synthétique avec un paquet corrompu.
