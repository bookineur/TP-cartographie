// Compte rendu TP Jour 1 — génération du .docx (docx-js)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, LevelFormat, Footer, Header, PageNumber, BorderStyle, PageBreak,
  TableOfContents,
} = require("docx");

const OUT_DIR = String.raw`C:\Users\HP\TP-cartographie\rendu\version_1`;
const FIG = path.join(OUT_DIR, "figures");
const SIZES = JSON.parse(fs.readFileSync(path.join(FIG, "_tailles.json"), "utf8"));
const FONT = "Calibri";
const ACCENT = "1F4E79";
const PAGE_W = 11906, MARGIN = 1134, CONTENT_W = PAGE_W - 2 * MARGIN; // A4, marges 2 cm

// ---------------------------------------------------------------- texte enrichi
// **gras**, `code`, ??à compléter?? (surligné jaune)
function runs(text, base = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`|\?\?[^?]+\?\?)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: 19, ...base }));
    else out.push(new TextRun({ text: t.slice(2, -2), highlight: "yellow", bold: true, ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const P = (text, opts = {}) => new Paragraph({ children: runs(text, opts.run || {}), spacing: { after: 120, line: 276 },
  alignment: opts.align || AlignmentType.JUSTIFIED, ...(opts.para || {}) });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true });
const H1first = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const B = (text, level = 0) => new Paragraph({ children: runs(text), numbering: { reference: "puces", level },
  spacing: { after: 60, line: 264 } });
let numInstance = 0;
function N(items) { // liste numérotée qui repart de 1
  numInstance += 1;
  return items.map((t) => new Paragraph({ children: runs(t), numbering: { reference: "num", level: 0, instance: numInstance },
    spacing: { after: 60, line: 264 } }));
}
const note = (text, fill = "EAF2FB") => new Paragraph({ children: runs(text), shading: { type: ShadingType.CLEAR, fill },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 6 } },
  spacing: { before: 80, after: 160, line: 264 }, indent: { left: 120, right: 120 } });

function img(name, widthPx = 620, caption) {
  const [w, h] = SIZES[name];
  const height = Math.round(widthPx * h / w);
  const out = [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: !!caption,
    children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(FIG, name)),
      transformation: { width: widthPx, height }, altText: { title: caption || name, description: caption || name, name } })] })];
  if (caption) out.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: runs(caption, { italics: true, size: 18, color: "555555" }) }));
  return out;
}

function table(headers, rows, widthsPct) {
  const widths = widthsPct.map((p) => Math.round(CONTENT_W * p / 100));
  widths[widths.length - 1] += CONTENT_W - widths.reduce((a, b) => a + b, 0);
  const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
  const borders = { top: border, bottom: border, left: border, right: border };
  const cell = (text, i, head, shade) => new TableCell({
    width: { size: widths[i], type: WidthType.DXA }, borders,
    shading: head ? { type: ShadingType.CLEAR, fill: ACCENT } : shade ? { type: ShadingType.CLEAR, fill: "F2F6FA" } : undefined,
    margins: { top: 50, bottom: 50, left: 90, right: 90 },
    children: [new Paragraph({ spacing: { after: 0 }, children: runs(String(text),
      head ? { bold: true, color: "FFFFFF", size: 19 } : { size: 19 }) })],
  });
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => cell(h, i, true)) }),
      ...rows.map((r, k) => new TableRow({ children: r.map((c, i) => cell(c, i, false, k % 2 === 1)) }))],
  });
}
const space = () => new Paragraph({ children: [], spacing: { after: 80 } });

// ================================================================== CONTENU
const C = [];

// ---------------------------------------------------------------- page de titre
C.push(new Paragraph({ spacing: { before: 2600, after: 200 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Compte rendu de TP — Jour 1", size: 30, color: "555555" })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "Extraction, visualisation et cartographie", bold: true, size: 52, color: ACCENT })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 900 },
  children: [new TextRun({ text: "avec un lidar 2D LD06", size: 36, color: ACCENT })] }));
C.push(...img("1_assemblage.png", 330));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 500, after: 100 },
  children: [new TextRun({ text: "Module : Cartographie et localisation appliquée à la robotique mobile", size: 22 })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
  children: [new TextRun({ text: "Étudiant : ", size: 22 }), new TextRun({ text: "Nom Prénom (à compléter)", size: 22, highlight: "yellow", bold: true })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Séance du 2 novembre 2026", size: 22 })] }));

// ---------------------------------------------------------------- sommaire
C.push(new Paragraph({ children: [new PageBreak()] }));
C.push(new Paragraph({ children: [new TextRun({ text: "Sommaire", bold: true, size: 32, color: ACCENT })], spacing: { after: 200 } }));
C.push(new TableOfContents("Sommaire", { hyperlink: true, headingStyleRange: "1-2" }));

// ---------------------------------------------------------------- introduction
C.push(H1("Introduction"));
C.push(P("L'objectif du TP est de passer des **mesures brutes d'un lidar 2D** à deux représentations de la salle : une **carte d'occupation** (grid map) et une **carte vectorielle** (segments). Le cours rappelle que construire une carte cohérente implique d'acquérir les données, de les fusionner et de les aligner dans un repère commun ; une mauvaise superposition entraîne des déformations."));
C.push(H2("Matériel et données"));
C.push(B("**Capteur** : lidar 2D LD06 (360°, 4 500 mesures/s, 5 à 13 tours/s, portée 0,02 à 12 m, précision typique 30 mm d'après la datasheet)."));
C.push(B("**Carte** : ESP32 (convertisseur USB-série CH340, port COM3) avec le sketch fourni `ESP32_LD06_Test.ino` ; il envoie chaque tour au format **Teleplot** à 115 200 bauds."));
C.push(B("**Données** : 14 scans réels de la salle, enregistrés le 2 novembre 2026 entre 18 h 32 et 18 h 45, dans `data/salle_2026-11-02_18h31/`."));
C.push(H2("Logiciel développé"));
C.push(P("Tous les outils ont été écrits en **Python** (numpy, matplotlib, tkinter, pyserial) dans le dossier `TP-cartographie`. Ils sont couverts par **36 tests automatiques** (pytest), dont les cas limites de la découpe de segments."));
C.push(table(["Module", "Rôle", "Étape du TP"], [
  ["`ld06/protocol.py`", "Décodage des paquets binaires du LD06 (en-tête, CRC, angles)", "1"],
  ["`carto/plot_app.py`", "Lidar Plot : acquisition en direct façon Teleplot, captures, exports", "1, 2"],
  ["`carto/viewer.py`", "Visualiseur multi-scans, pose modifiable à la souris", "2"],
  ["`carto/register.py`", "Prétraitement et recalage automatique des scans", "2"],
  ["`carto/gridmap.py`", "Carte d'occupation : création et mise à jour", "3"],
  ["`carto/segments.py`", "Segments : extraction, angle, proximité, fusion, intersection, découpe", "4"],
  ["`carto/vectormap.py`", "Carte vectorielle", "5"],
  ["`carto/build_map.py`", "Chaîne complète sur une session : assemblage, cartes, rapport", "3, 5"],
], [28, 57, 15]));

// ================================================================ 1. EXTRACTION
C.push(H1("1. Extraction des données lidar"));
C.push(H2("1.1 Le protocole de communication du LD06"));
C.push(P("Le LD06 envoie en continu, sans commande, des paquets de **47 octets** sur une liaison série à 230 400 bauds. Chaque paquet contient **12 mesures** :"));
C.push(table(["Octets", "Champ", "Rôle"], [
  ["1", "En-tête `0x54`", "Caractère de début de trame (84 en décimal), choisi arbitrairement pour être reconnaissable"],
  ["1", "`0x2C`", "Les 5 bits de poids faible donnent le nombre de points : 12"],
  ["2", "Vitesse", "Vitesse de rotation en °/s"],
  ["2", "Angle de début", "En centièmes de degré : 1° → 100, 359,99° → 35 999 (< 65 535, maximum sur 2 octets)"],
  ["12 × 3", "Mesures", "Distance sur 2 octets (mm) + confiance (intensité) sur 1 octet (0 à 255)"],
  ["2", "Angle de fin", "En centièmes de degré"],
  ["2", "Horodatage", "En ms (revient à 0 après 30 000)"],
  ["1", "CRC", "CRC-8 (polynôme 0x4D) des 46 octets précédents"],
], [12, 22, 66]));
C.push(space());
C.push(P("Seuls l'angle de début et l'angle de fin sont transmis : les 12 angles sont **interpolés** (`pas = (fin − début) / 11`), en tenant compte du passage 360° → 0°. Un tour complet (environ 450 points à 10 tr/s) représente donc environ 38 paquets. Pour se synchroniser, on attend `0x54` suivi de `0x2C`, puis on vérifie le CRC : un faux départ (un `0x54` au milieu des données) est ainsi rejeté et l'on se recale sur l'en-tête suivant."));
C.push(note("**Vérification** : notre décodeur Python retrouve exactement le paquet d'exemple de la documentation (CRC 0x50, 2 152 °/s, angles de 324,27° à 334,70°, mesures 224 mm et 220 mm)."));

C.push(H2("1.2 La librairie fournie"));
C.push(P("La librairie Arduino `LD06` (fichiers `ld06.h` / `ld06.cpp`) réalise ce décodage. Ses principales fonctions :"));
C.push(table(["Fonction", "Rôle"], [
  ["`readDataCRC()`", "Machine à états octet par octet : attend 0x54 puis 0x2C, remplit les 47 octets, calcule le CRC au vol"],
  ["`computeData()`", "Calcule les 12 angles, détecte la fin d'un tour, convertit en sens trigonométrique, calcule x et y"],
  ["`readScan()` / `swapBuffers()`", "Double tampon : on lit le dernier tour complet pendant que le suivant se remplit"],
  ["`printScanTeleplot()` / `printScanCSV()`", "Envoi d'un tour au format Teleplot (x, y) ou CSV (angle, distance, intensité, x, y)"],
  ["`enableFiltering()`, `setIntensityThreshold()`, `setDistanceRange()`", "Filtres optionnels, appliqués sur la carte avant l'envoi"],
], [38, 62]));
C.push(space());
C.push(P("En lisant le code, nous avons relevé plusieurs points, pris en compte dans nos outils :"));
C.push(B("**Repère** : le capteur compte les angles dans le sens horaire ; la librairie convertit en sens trigonométrique (`360 − angle`), mais ses coordonnées x, y (`y = −d·sin(angle)`) sont **en miroir**. Nos outils corrigent ce miroir pour les données Teleplot (vérifié en simulation : 21 mm d'écart avec correction, 493 mm sans)."));
C.push(B("**Interpolation** légèrement différente de la documentation (écart < 0,4°, inférieur à l'erreur angulaire de 2° du capteur)."));
C.push(B("**Fonction isChecksumOk()** : l'affectation y est inversée ; après la première erreur de CRC, la fonction renvoie toujours faux."));
C.push(B("**Débit série** : un tour en texte pèse environ 12 ko ; à 115 200 bauds, l'envoi peut faire perdre des paquets du tour suivant."));

C.push(H2("1.3 Acquisition dans la salle"));
C.push(P("Plutôt que le site Teleplot, nous avons développé **Lidar Plot**, une application qui lit directement le port série (formats Teleplot, CSV ou LD06 binaire, débit détecté automatiquement), affiche le tour en direct et permet de **mettre en pause** puis de **capturer** l'image affichée. Chaque capture est sauvée en coordonnées polaires (`scanK.csv` : angle en degrés, distance en mm, intensité)."));
C.push(P("Nous avons enregistré **14 scans**. Pour les scans 1 à 9, le lidar était posé en hauteur (??à préciser : sur une table / sur le robot??) à différents endroits de la salle ; pour les scans 10 à 14, il était **posé au sol, au fond de la salle, à droite**."));
C.push(table(["Scan", "Heure", "Points", "Pas angulaire", "Position du lidar"], [
  ["1", "18:32:50", "455", "0,73°", "en hauteur"], ["2", "18:33:57", "454", "0,73°", "en hauteur"],
  ["3", "18:34:28", "454", "0,73°", "en hauteur"], ["4", "18:35:45", "454", "0,73°", "en hauteur"],
  ["5", "18:37:22", "455", "0,73°", "en hauteur"], ["6", "18:37:57", "1 050", "0,33°", "en hauteur"],
  ["7", "18:38:53", "687", "0,58°", "en hauteur"], ["8", "18:40:33", "1 149", "0,29°", "en hauteur"],
  ["9", "18:41:07", "455", "0,73°", "en hauteur"], ["10", "18:42:53", "454", "0,73°", "au sol"],
  ["11", "18:43:35", "974", "0,36°", "au sol"], ["12", "18:44:25", "1 158", "0,29°", "au sol"],
  ["13", "18:44:48", "735", "0,48°", "au sol"], ["14", "18:45:34", "976", "0,34°", "au sol"],
], [12, 18, 15, 20, 35]));
C.push(...img("fig_scan_polaire_cartesien.png", 620, "Figure 1 — Le scan 1 tel que mesuré (coordonnées polaires) et converti en coordonnées cartésiennes."));

C.push(H2("1.4 Difficultés, hypothèses et limites"));
C.push(B("**Pas d'intensité dans nos données** : le format Teleplot n'envoie que x et y. Le filtrage par intensité recommandé se fait donc **sur le robot** (`ld06.enableFiltering(); ld06.setIntensityThreshold(seuil);`, bloc désactivé dans le sketch), ou en envoyant les scans en CSV. Nous l'avons remplacé par d'autres filtres (§ 2)."));
C.push(B("**Nombre de points variable** (454 à 1 158) : le pas angulaire passe de 0,73° à 0,29° quand le lidar tourne plus lentement ; les tours restent complets."));
C.push(B("**Port série occupé** : un seul programme peut ouvrir COM3 (fermer le moniteur série de l'IDE Arduino)."));
C.push(B("**Positions non mesurées** : les poses du robot n'ont pas été relevées au mètre ; elles ont été retrouvées par recalage (§ 2.3)."));

// ================================================================ 2. VISUALISATION
C.push(H1("2. Visualisation des nuages de points"));
C.push(H2("2.1 Des coordonnées polaires au repère de la carte"));
C.push(P("Chaque point (θ, r) du lidar est d'abord converti dans le repère du lidar, puis placé dans le repère de la carte avec la **pose** (x, y, θ) du lidar au moment du scan :"));
C.push(P("P_local = (r·cos θ, r·sin θ)        P_carte = R(θ_pose) · P_local + (x_pose, y_pose)", { align: AlignmentType.CENTER, run: { font: "Consolas", size: 20 } }));
C.push(P("Convention : angles dans le sens trigonométrique, 0° vers l'avant du lidar (la flèche du capot), distances en mètres."));
C.push(H2("2.2 L'outil de visualisation"));
C.push(P("Deux outils répondent à ce point de l'énoncé :"));
C.push(B("**Lidar Plot** (`python -m carto plot`) : carte centrale en direct, scans capturés dans des **couleurs distinctes** (scan 1 vert, scan 2 orange, scan 3 violet…), visibilité de chaque scan, **pose modifiable** (x, y, θ) avec des boutons ± et un bouton de recalage automatique, zoom à la molette, coordonnées du curseur, exports image, Excel et CSV."));
C.push(B("**Visualiseur** (`python -m carto view`) : plusieurs scans affichés simultanément ; le scan sélectionné se **déplace à la souris** (glisser), se **tourne à la molette**, ou par saisie directe de sa pose ; les poses sont enregistrées dans `poses.json`."));
C.push(...img("fig_lidarplot.png", 620, "Figure 2 — Lidar Plot avec les 9 scans retenus, une couleur par scan, et l'éditeur de pose du scan 2."));

C.push(H2("2.3 Placement des scans : manuel puis automatique"));
C.push(P("Placer à la main des scans dont on ne connaît pas la position est long et imprécis. Nous avons donc ajouté un **recalage automatique** (`carto/register.py`), qui complète le déplacement manuel :"));
C.push(...N([
  "**Prétraitement** de chaque scan : suppression des points à moins de 10 cm (boîtier, câbles) ou à plus de 10 m (précision dégradée), et des **points isolés** (moins de 2 voisins à moins de 15 cm), qui remplacent le filtre d'intensité absent.",
  "**Recalage global** de chaque paire de scans : pour chaque rotation de 0 à 360° (pas de 2°), la meilleure translation est trouvée par **corrélation FFT** entre les points d'un scan et une grille floutée des points de l'autre.",
  "**Affinage par ICP** (Iterative Closest Point, cité dans le cours pour la détection de boucle).",
  "**Assemblage** : le recouvrement (part des points à moins de 10 cm d'un point de l'autre scan) mesure la qualité ; on garde les meilleures liaisons (arbre couvrant de recouvrement maximal) et on compose les poses depuis un scan de référence.",
  "**Redressement** : la carte entière est tournée de +4,9° pour que les murs soient parallèles aux axes.",
]));
C.push(P("Validation en simulation (salle connue) : les positions inconnues sont retrouvées à quelques centimètres et moins de 2° près."));
C.push(table(["Scan", "x (m)", "y (m)", "θ (°)", "Recouvrement avec les autres"], [
  ["3 (réf.)", "0,00", "0,00", "4,9", "89 %"], ["1", "−2,13", "2,55", "−13,5", "93 %"],
  ["2", "0,33", "0,38", "8,3", "88 %"], ["4", "0,61", "0,23", "175,0", "88 %"],
  ["5", "0,59", "−0,70", "97,5", "84 %"], ["6", "1,07", "−0,58", "88,8", "91 %"],
  ["7", "−2,77", "−0,85", "94,9", "80 %"], ["8", "−2,63", "3,46", "87,1", "85 %"],
  ["9", "−1,10", "−2,06", "−176,2", "63 %"],
], [16, 16, 16, 16, 36]));
C.push(...img("1_assemblage.png", 560, "Figure 3 — Les 9 scans pris en hauteur, superposés dans le repère commun (une couleur par scan)."));
C.push(H2("2.4 Choix, hypothèses et limites"));
C.push(B("**Hypothèse** : le lidar est immobile pendant un tour (pas de correction de mouvement)."));
C.push(B("**Limite** : le recalage peut se tromper dans une pièce très symétrique ou très encombrée ; c'est pourquoi un recouvrement minimal est exigé et le résultat est toujours vérifié visuellement."));
C.push(B("**Limite** : le repère final dépend du scan de référence ; le redressement suppose des murs perpendiculaires."));

// ================================================================ 3. GRID MAP
C.push(H1("3. Construction d'une grid map 2D"));
C.push(note("Le document « Construction d'une grid map 2D à partir d'un scan lidar » ne nous a pas été transmis sous forme de fichier ; nous avons appliqué la méthode classique de la carte d'occupation par log-odds, décrite dans le cours (« l'espace est divisé en cellules avec une probabilité d'occupation »). ??Vérifier l'adéquation avec le document du professeur.??", "FFF4E5"));
C.push(H2("3.1 Principe"));
C.push(...N([
  "**Discrétisation** : le plan est découpé en cellules carrées de **5 cm** (environ 3 fois la résolution de mesure du LD06).",
  "**Lancer de rayons** : pour chaque point, les cellules entre le lidar et l'impact sont tracées avec l'algorithme de **Bresenham**. Les cellules traversées sont **libres** (le laser y est passé), la cellule d'impact est **occupée**.",
  "**Probabilité en log-odds** : chaque cellule stocke l = log(p / (1 − p)), qui vaut 0 pour une cellule inconnue (p = 0,5). Une observation libre ajoute −0,4, une observation occupée ajoute +0,85, et l est borné à [−4 ; 4]. Additionner les log-odds revient à appliquer la règle de Bayes (mesures supposées indépendantes) ; la borne permet à la carte de rester modifiable.",
]));
C.push(H2("3.2 Les deux outils demandés"));
C.push(B("**Scan + pose → carte d'occupation** : `OccupancyGrid.from_scan(scan, pose)` dimensionne la grille autour du scan (marge de 1 m) puis intègre ses rayons."));
C.push(B("**Carte + scan + pose → carte mise à jour** : `grid.update(scan, pose)` agrandit la grille si le scan dépasse (en gardant l'alignement des cellules), puis met à jour les **cellules traversées** et les **cellules d'impact**."));
C.push(P("Deux choix techniques améliorent la mise à jour :"));
C.push(B("**une seule mise à jour par cellule et par scan** : près du lidar, une cellule est traversée par des centaines de rayons ; sans cette règle, elle deviendrait « certaine » dès le premier scan ;"));
C.push(B("**priorité à l'impact** : une cellule vue à la fois libre et occupée dans un même scan est comptée occupée (les rayons rasants traversent souvent la cellule d'un mur)."));
C.push(H2("3.3 Résultats sur nos scans"));
C.push(...img("fig_grid_etapes.png", 620, "Figure 4 — Construction progressive : création avec le scan de référence, puis mises à jour (3 et 9 scans)."));
C.push(...img("2_grid_map.png", 470, "Figure 5 — Grid map finale (9 scans, cellules de 5 cm) : noir = occupé, blanc = libre, gris = inconnu."));
C.push(P("La pièce principale mesure environ **8 × 10 m** ; une ouverture donne sur une zone à droite (mur vers x ≈ 9,7 m). Surface libre cartographiée : 76,6 m² ; surface occupée : 2,5 m²."));
C.push(H2("3.4 Propriétés supplémentaires"));
C.push(B("**Durée de vie des cellules** (`decay`) : avant chaque mise à jour, l ← l·(1 − decay) ramène la carte vers « inconnu » ; ce qui n'est plus revu s'efface progressivement."));
C.push(B("**Compteur d'impacts** par cellule et **classification** en trois états (seuils p ≤ 0,35 libre, p ≥ 0,65 occupé)."));
C.push(B("**Filtrage** des points avant intégration (§ 2.3)."));
C.push(H2("3.5 Hypothèses, difficultés et limites"));
C.push(B("Les poses sont supposées exactes : une erreur de pose dédouble les murs."));
C.push(B("Les mesures sans écho (distance 0) sont ignorées : on ne peut pas distinguer « rien jusqu'à 12 m » d'une vitre ou d'une surface noire."));
C.push(B("Loin du lidar, les rayons s'écartent (10 cm entre deux rayons à 6 m) : des cellules libres ne sont jamais traversées, d'où les stries visibles."));
C.push(B("Une cellule vue libre une seule fois a p = 0,40 : il faut plusieurs observations pour la confirmer."));

// ================================================================ 4. SEGMENTS
C.push(H1("4. Extraction et manipulation de segments"));
C.push(P("Un segment est stocké par ses deux extrémités E₁(x₁, y₁) et E₂(x₂, y₂), avec un compteur d'observations. Toutes les fonctions sont dans `carto/segments.py`."));
C.push(H2("4.1 Nuage de points → segments"));
C.push(P("Méthode **Split-and-Merge** :"));
C.push(...N([
  "**Clusters** : le nuage, trié par angle, est coupé là où deux points successifs sont à plus de 20 cm. Le scan étant circulaire, on commence au plus grand trou pour ne pas couper un mur au passage 0°.",
  "**Split** (Douglas-Peucker) : on coupe au point le plus éloigné de la corde tant qu'il est à plus de **10 cm**.",
  "**Merge** : deux morceaux voisins sont réunis si la droite ajustée sur l'union de leurs points reste à moins de 10 cm de chaque point (le bruit crée des coupures parasites ; un vrai coin donne un grand écart).",
  "**Ajustement** par moindres carrés **totaux** (distance orthogonale, valable aussi pour un mur vertical, contrairement à y = ax + b).",
  "**Filtre** : segments de moins de 15 cm ou de moins de 6 points rejetés.",
]));
C.push(note("**Choix du seuil de 10 cm** : la datasheet donne une précision de 30 mm (typique) ; avec ce bruit, en simulation, un seuil de 5 cm découpe 11 murs réels en 67 morceaux, 8 cm en 19, et 10 cm en 11."));
C.push(H2("4.2 Angle, proximité, fusion, intersection"));
C.push(B("**Angle entre deux segments** : angle entre leurs droites, dans [0° ; 90°] (A→B et B→A sont le même mur) ; une version orientée donne l'angle signé."));
C.push(B("**Segments « proches »** : angle ≤ 8° **et** extrémités du plus court à moins d'une distance latérale donnée de la droite du plus long **et** recouvrement, ou trou de moins de 10 à 20 cm, une fois projetés sur le plus long."));
C.push(B("**Fusion** : direction moyenne pondérée par les longueurs, droite passant par le barycentre des milieux, extrémités = projections extrêmes des 4 extrémités ; les compteurs d'observations s'additionnent."));
C.push(B("**Intersection** : résolution de p + t·r = q + u·s ; le point est accepté si t et u sont dans [0 ; 1] à la tolérance près. Segments parallèles ou colinéaires : pas de point unique."));
C.push(H2("4.3 Découpe d'un segment traversé"));
C.push(P("**Tolérance numérique : TOL = 1 µm**, très en dessous de la résolution du LD06 (15 mm) mais très au-dessus des erreurs d'arrondi des calculs (≈ 10⁻¹⁴ m) ; deux droites sont parallèles si |sin(angle)| ≤ 10⁻⁹. Les règles de l'énoncé sont appliquées et chacune est testée :"));
C.push(table(["Cas testé (T de (0,0) à (10,0))", "Résultat attendu et obtenu"], [
  ["Coupeur croisant T en x = 3", "Découpé : on garde (3,0)–(10,0), le plus long côté"],
  ["Coupeur croisant T en x = 7", "Découpé : on garde (0,0)–(7,0)"],
  ["Coupeur qui ne touche pas T (x = 12)", "Inchangé"],
  ["Intersection à une extrémité de T (x = 0, x = 10, ou à 0,5·TOL)", "Inchangé"],
  ["Intersection juste à l'intérieur (2·TOL de l'extrémité)", "Découpé"],
  ["Coupeur qui touche T par son extrémité (jonction en T)", "Découpé (l'intersection est sur les deux segments)"],
  ["Coupeur colinéaire (chevauchant ou non) ou parallèle", "Inchangé"],
  ["Longueurs égales : x = 5, et x = 5 ± 0,4·TOL", "Découpé : on garde le côté contenant le premier point"],
  ["Segment T inversé, coupé en x = 5", "On garde (10,0)–(5,0) : le côté de son premier point"],
], [55, 45]));
C.push(...img("fig_segments_operations.png", 620, "Figure 6 — Les six opérations : extraction sur le scan 1, angle, proximité, fusion, intersection et découpe."));

// ================================================================ 5. CARTE VECTORIELLE
C.push(H1("5. Construction d'une carte vectorielle"));
C.push(P("La carte vectorielle est construite avec les fonctions du § 4, en suivant les étapes du document « Construction d'une carte vectorielle 2D à partir d'un scan lidar » :"));
C.push(table(["Étape du document", "Mise en œuvre"], [
  ["1. Caractéristiques de la zone", "Environnement intérieur structuré : murs et meubles représentés par des **segments** (x₁, y₁, x₂, y₂) avec un compteur de confiance ; carte stockée dans un fichier texte `carte_vectorielle.txt`, initialement vide"],
  ["2. Acquisition et prétraitement", "Polaire → cartésien, puis repère global P = R(θ)·P_local + T ; suppression des points trop proches, trop lointains et isolés (intensité non disponible)"],
  ["3. Extraction des primitives", "Segmentation par discontinuité de distance (> 20 cm), puis simplification polygonale (Douglas-Peucker) et régression (moindres carrés totaux)"],
  ["4. Ajout et mise à jour", "Comparaison (angle + position) avec les segments existants : **fusion** si proches, sinon **ajout**"],
  ["5. Absence de détection", "Option : chaque rayon (lidar → impact, raccourci de 15 cm) qui traverse un segment le **découpe** (fonction du § 4.3)"],
  ["6. Mise à jour continue et nettoyage", "Alignement des scans (recalage § 2.3), refusion des segments devenus proches, suppression des segments < 15 cm"],
], [30, 70]));
C.push(...img("3_carte_vectorielle.png", 500, "Figure 7 — Carte vectorielle (9 scans) : 82 segments, l'épaisseur indique le nombre d'observations."));
C.push(P("Résultat : **82 segments**, dont **19 vus au moins deux fois**, pour 79,8 m de murs. Les longs segments épais sont les murs, vus depuis plusieurs positions ; les petits segments du centre sont les meubles coupés à la hauteur du lidar."));
C.push(H2("Propriétés supplémentaires"));
C.push(B("**Confiance** : chaque segment compte ses observations ; on peut ne garder que ceux vus au moins deux fois (une personne qui passe n'est vue qu'une fois)."));
C.push(B("**Gestion des absences** par découpe le long des rayons (désactivée par défaut, car une petite erreur de pose ferait couper de vrais murs)."));
C.push(H2("Hypothèses et limites"));
C.push(B("La qualité dépend directement des poses : 2° d'erreur font 10 cm d'écart à 3 m et empêchent la fusion."));
C.push(B("Les objets ronds (pieds de chaise, poubelles) donnent de petits segments instables ; des cercles seraient une meilleure primitive."));
C.push(B("La fusion est gloutonne : l'ordre d'intégration des scans influe légèrement sur le résultat."));

// ================================================================ 6. DISCUSSION
C.push(H1("6. Discussion : hauteur du lidar et validation"));
C.push(H2("6.1 Les scans pris au sol (10 à 14)"));
C.push(P("Les scans 10 à 14 n'ont pas pu être rattachés de façon fiable à la carte. Un lidar 2D ne voit que dans **un seul plan** (cours, § 5) : posé au sol, ce plan coupe surtout des **pieds de chaises, de tabourets et de tables**, et des sacs. Ces scans contiennent donc très peu de murs (10 à 27 % de leurs points, 47 % pour le scan 10), contre 52 à 92 % pour les scans pris en hauteur. Le recalage n'a presque rien de commun et de stable à superposer ; une seule ligne droite commune ne suffit pas, car le scan peut « glisser » le long d'elle. Les étudiants qui se déplaçaient pendant la capture ajoutent des points différents d'un scan à l'autre (objets mobiles, § 5 du document)."));
C.push(P("Nous avons choisi de **ne pas les intégrer** plutôt que de fausser la carte."));
C.push(...img("4_scans_ecartes.png", 620, "Figure 8 — En rouge, les points situés sur des murs : un scan pris en hauteur (utilisé) et des scans pris au sol (écartés)."));
C.push(H2("6.2 Comparaison avec la salle réelle"));
C.push(P("Les photos de la salle confirment l'interprétation de la carte : grande salle rectangulaire aux murs droits, nombreuses tables et tabourets (petits segments au centre), grande table blanche du circuit, portes orange et rangée de fenêtres. Les **vitres** et les **portes ouvertes** expliquent les points situés au-delà des murs."));
C.push(new Table({
  width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W / 2, CONTENT_W / 2],
  rows: [new TableRow({ children: ["photo_salle_1.png", "photo_salle_2.png"].map((n) => new TableCell({
    width: { size: CONTENT_W / 2, type: WidthType.DXA },
    borders: { top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE }, left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE } },
    children: img(n, 250) })) })],
}));
C.push(P("Figure 9 — Photos de la salle cartographiée.", { align: AlignmentType.CENTER, run: { italics: true, size: 18, color: "555555" } }));

// ================================================================ CONCLUSION
C.push(H1("Conclusion"));
C.push(P("Nous avons parcouru toute la chaîne de cartographie : décodage du protocole du LD06, acquisition de scans réels, visualisation et superposition des scans, puis construction d'une **carte d'occupation** et d'une **carte vectorielle** de la salle. Les deux représentations se complètent : la grid map indique aussi l'espace libre et l'inconnu, la carte vectorielle est compacte (82 segments au lieu de plus de 100 000 cellules) et précise."));
C.push(P("Le point critique est la **superposition des scans** : sans mesure des positions, il a fallu les retrouver par recalage, et les scans pris au sol, trop pauvres en murs, n'ont pas pu être placés. Pour la suite, il serait utile de mesurer les positions (ou d'utiliser l'odométrie), de filtrer par intensité sur le robot, et d'aborder la **localisation** et la **fermeture de boucle**, qui permettent de corriger la dérive accumulée."));

// ================================================================ ANNEXES
C.push(H1("Annexe — Commandes et tests"));
C.push(H2("Reproduire les résultats"));
C.push(table(["Commande", "Effet"], [
  ["`Lidar Plot.bat` (double-clic)", "Acquisition en direct, captures, exports"],
  ["`python -m carto assemble data\\salle_2026-11-02_18h31 --scans 1-9 --ecartes 10-14`", "Assemblage, grid map, carte vectorielle et rapport (dans un nouveau dossier version_N)"],
  ["`python -m carto view <dossier> --poses <poses.json>`", "Visualiseur multi-scans, pose modifiable à la souris"],
  ["`python -m carto grid <dossier> --poses <poses.json> --steps`", "Grid map, avec une image après chaque scan"],
  ["`python -m carto vector <dossier> --poses <poses.json> --cut-rays`", "Carte vectorielle avec découpe par les rayons"],
  ["`python -m pytest`", "Les 36 tests automatiques"],
], [55, 45]));
C.push(space());
C.push(H2("Tests automatiques (36)"));
C.push(B("Protocole : paquet d'exemple de la documentation, CRC, resynchronisation, passage 360° → 0°, assemblage des tours, lecture Teleplot et correction du miroir."));
C.push(B("Grid map : Bresenham, création, mise à jour, agrandissement de la grille."));
C.push(B("Segments : angle, proximité, fusion, intersection, tous les cas limites de la découpe, extraction des 4 murs d'une pièce bruitée."));
C.push(B("Recalage : poses inconnues retrouvées en simulation, filtre des points isolés et des pieds de meubles."));

// ================================================================ DOCUMENT
const doc = new Document({
  creator: "Compte rendu TP cartographie", title: "Compte rendu TP Jour 1 — Cartographie LD06",
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, color: ACCENT, font: FONT },
        paragraph: { spacing: { before: 120, after: 200 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: ACCENT, space: 4 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, color: ACCENT, font: FONT },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1, keepNext: true } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 23, bold: true, color: "333333", font: FONT },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2, keepNext: true } },
    ],
  },
  numbering: { config: [
    { reference: "puces", levels: [
      { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
      { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 1080, hanging: 270 } } } }] },
    { reference: "num", levels: [
      { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 540, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } }, titlePage: true },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      children: [new TextRun({ text: "TP Jour 1 — Cartographie avec un lidar LD06", size: 16, color: "888888" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: ["Page ", PageNumber.CURRENT, " / ", PageNumber.TOTAL_PAGES], size: 16, color: "888888" })] })] }) },
    children: C,
  }],
});

const outFile = path.join(OUT_DIR, "compte_rendu_TP1_cartographie_v1.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outFile, buf); console.log("->", outFile); });
