// Rapport final du TP (jours 1 à 3 + bonus) — génération du .docx (docx-js)
// Lancer : NODE_PATH=<dossier contenant node_modules/docx> node make_report.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, LevelFormat, Footer, Header, PageNumber, BorderStyle, PageBreak,
  TableOfContents,
} = require("docx");

const OUT_DIR = path.join(__dirname, "..");
const FIG = path.join(OUT_DIR, "figures");
const SIZES = JSON.parse(fs.readFileSync(path.join(FIG, "_tailles.json"), "utf8"));
const EXPLO = JSON.parse(fs.readFileSync(path.join(__dirname, "bilan_exploration.json"), "utf8"));
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
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const B = (text, level = 0) => new Paragraph({ children: runs(text), numbering: { reference: "puces", level },
  spacing: { after: 60, line: 264 } });
let numInstance = 0;
function N(items) {
  numInstance += 1;
  return items.map((t) => new Paragraph({ children: runs(t), numbering: { reference: "num", level: 0, instance: numInstance },
    spacing: { after: 60, line: 264 } }));
}
const note = (text, fill = "EAF2FB") => new Paragraph({ children: runs(text), shading: { type: ShadingType.CLEAR, fill },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 6 } },
  spacing: { before: 80, after: 160, line: 264 }, indent: { left: 120, right: 120 } });
const warn = (text) => note(text, "FFF4E5");

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
const legend = (t) => P(t, { align: AlignmentType.CENTER, run: { italics: true, size: 18, color: "555555" } });
const fr = (x) => String(x).replace(".", ",");

// ================================================================== CONTENU
const C = [];

// ---------------------------------------------------------------- page de titre
C.push(new Paragraph({ spacing: { before: 2000, after: 200 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Rapport final de TP — Jours 1, 2, 3 et bonus (version 2)", size: 30, color: "555555" })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "Cartographie et localisation", bold: true, size: 52, color: ACCENT })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 600 },
  children: [new TextRun({ text: "avec le lidar LD06, du nuage de points au robot qui explore", size: 32, color: ACCENT })] }));
C.push(...img("s10_grid_map.png", 360));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400, after: 100 },
  children: [new TextRun({ text: "Module : Cartographie et localisation appliquée à la robotique mobile", size: 22 })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
  children: [new TextRun({ text: "Étudiant : ", size: 22 }), new TextRun({ text: "Nom Prénom (à compléter)", size: 22, highlight: "yellow", bold: true })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Novembre 2026", size: 22 })] }));

// ---------------------------------------------------------------- sommaire
C.push(new Paragraph({ children: [new PageBreak()] }));
C.push(new Paragraph({ children: [new TextRun({ text: "Sommaire", bold: true, size: 32, color: ACCENT })], spacing: { after: 200 } }));
C.push(new TableOfContents("Sommaire", { hyperlink: true, headingStyleRange: "1-2" }));
C.push(space());
C.push(note("**Comment lire ce rapport.** Il rassemble tout le TP. Les jours 1 et 2 sont résumés ici ; leurs détails (méthodes, tableaux complets) sont dans les comptes rendus déjà rendus : `rendu/version_1` (Jour 1) et `rendu/jour2/version_1` (Jour 2). Le Jour 3 et le bonus sont détaillés ici pour la première fois. Les passages **surlignés en jaune** sont à rédiger par l'étudiant."));
C.push(note("**Règle suivie dans tout le TP.** Les seuils et critères de réussite ont été **fixés avant** de regarder les résultats. Quand un critère n'est pas atteint, le rapport le dit. Les résultats **simulés** et les résultats **réels** sont toujours séparés et nommés comme tels.", "FFF4E5"));

// ================================================================ INTRODUCTION
C.push(H1("Introduction"));
C.push(P("Le TP suit le chemin complet d'un robot mobile équipé d'un lidar 2D. Le **Jour 1** transforme les mesures brutes du lidar LD06 en cartes de la salle : une **grid map** (carte d'occupation) et une **carte vectorielle** (segments). Le **Jour 2** traite le problème inverse : connaissant une carte, **retrouver la pose du robot** (position x, y et orientation θ) par **scan matching**. Le **Jour 3** met ces briques sur le **vrai robot** : on le pilote, on capture des scans pendant qu'il roule, et on construit la carte en direct. Le **bonus** rend le robot **autonome** : il choisit lui-même où aller pour cartographier la salle. Un second essai vérifie qu'un robot « perdu » **retrouve sa position** à partir d'un seul scan, sur la grid map et sur la carte vectorielle."));
C.push(H2("Matériel"));
C.push(B("**Lidar LD06** : 450 mesures par tour environ, 10 tours par seconde, portée utile d'environ 12 m, précision annoncée de ±30 mm."));
C.push(B("**Robot** à deux roues motrices, piloté par une carte **ESP32**. Il ne possède **pas d'odométrie** (pas de capteur de rotation des roues) : sa position ne peut venir que du lidar."));
C.push(B("Un **PC** portable, et un téléphone pour piloter le robot pendant les relevés."));
C.push(H2("Logiciels développés"));
C.push(table(["Dépôt", "Langage", "Rôle"], [
  ["`TP-cartographie`", "Python (numpy, matplotlib)", "Banc d'analyse : lecture des scans, Lidar Plot, grid map, segments et carte vectorielle (Jour 1) ; sept méthodes de localisation et banc d'évaluation (Jour 2) ; cartes des séances réelles. 65 tests automatiques."],
  ["`codex_lidar` (Lidar Lab)", "JavaScript (page web + serveur Node.js), C++ (sketch ESP32)", "Application de démonstration du Jour 3 : pilotage du robot, capture des scans, Auto-SLAM (carte construite en direct), assemblage hors ligne, exploration automatique (bonus). 60 tests automatiques."],
], [20, 24, 56]));
C.push(space());
C.push(P("Les deux dépôts sont sous **git**, avec un commit par modification et un message qui explique le changement. Les anciennes versions des fichiers et des résultats sont conservées (dossiers `version_N` et `anciennes_versions`). Aucun scan enregistré n'a été modifié."));

// ================================================================ JOUR 1
C.push(H1("1. Jour 1 — Construire une carte à partir des scans"));
C.push(H2("1.1 Extraction des données du lidar"));
C.push(P("Le LD06 envoie sur sa liaison série des **paquets de 47 octets** : un en-tête, la vitesse de rotation, l'angle de début, 12 mesures (distance en mm et intensité), l'angle de fin, un horodatage et un code de contrôle (CRC). On calcule l'angle de chaque mesure par interpolation entre l'angle de début et l'angle de fin. Un tour complet est reconstitué quand l'angle repasse par zéro. Nous avons enregistré chaque tour dans un fichier CSV (angle, distance, intensité)."));
C.push(P("Le LD06 tourne dans le **sens horaire** : ses angles sont donc comptés à l'inverse du sens trigonométrique. Sans correction, la carte obtenue est le **miroir** de la salle. Nous avons corrigé ce sens une fois pour toutes, à la lecture des fichiers."));
C.push(...img("fig_scan_polaire_cartesien.png", 560, "Figure 1 — Un scan en coordonnées polaires (tel que mesuré) puis converti en coordonnées cartésiennes x = d cos θ, y = d sin θ."));
C.push(H2("1.2 Visualisation et superposition des scans"));
C.push(P("L'outil **Lidar Plot** (Python) affiche plusieurs scans dans un repère commun, une couleur par scan, et permet de régler la pose de chacun à la main. Comme les positions du lidar n'avaient pas été mesurées pendant la capture, nous avons ajouté un **recalage automatique** : chaque scan est d'abord placé par une recherche sur 360° (corrélation accélérée par FFT), puis affiné par ICP. 9 scans pris en hauteur ont été placés ; les 5 scans pris au sol voyaient trop peu de murs et ont été écartés."));
C.push(...img("fig_lidarplot.png", 560, "Figure 2 — Lidar Plot : les 9 scans retenus dans le repère commun, et l'éditeur de pose d'un scan."));
C.push(H2("1.3 Grid map"));
C.push(P("La salle est découpée en **cellules de 5 cm**. Pour chaque point mesuré, on trace le rayon du lidar jusqu'au point (algorithme de Bresenham « supercover », qui ne saute aucune cellule) : les cellules traversées sont **libres**, la cellule du point est **occupée**. Les observations successives sont cumulées en **log-odds** (logarithme du rapport de probabilités), ce qui transforme la mise à jour bayésienne en une simple addition. La carte peut ainsi être créée avec un scan puis mise à jour avec les suivants."));
C.push(...img("fig_grid_etapes.png", 600, "Figure 3 — Grid map créée avec le scan de référence, puis mise à jour avec 3 puis 9 scans (noir = occupé, blanc = libre, gris = inconnu)."));
C.push(H2("1.4 Segments et carte vectorielle"));
C.push(P("Chaque scan est découpé en groupes de points voisins, puis chaque groupe est approché par des segments (méthode **split-and-merge** / Douglas-Peucker). Nous avons programmé les opérations demandées : angle entre deux segments, test de proximité, **fusion**, intersection et **découpe** d'un segment traversé par un rayon (une porte qui s'ouvre, par exemple). La carte vectorielle cumule les segments de tous les scans et fusionne ceux qui représentent le même mur."));
C.push(...img("fig_segments_operations.png", 560, "Figure 4 — Les opérations sur les segments : extraction, angle, proximité, fusion, intersection, découpe."));
C.push(...img("3_carte_vectorielle.png", 380, "Figure 5 — Carte vectorielle de la salle du Jour 1 : 82 segments (l'épaisseur indique le nombre d'observations)."));
C.push(P("**Bilan du Jour 1.** Toute la chaîne est en place et testée. Les deux cartes se complètent : la grid map dit aussi où est l'espace **libre** et l'**inconnu** ; la carte vectorielle est **compacte** (82 segments au lieu de plus de 100 000 cellules). Le point faible était la superposition des scans, faute de positions mesurées."));

// ================================================================ JOUR 2
C.push(H1("2. Jour 2 — Se localiser par scan matching"));
C.push(P("Chercher la pose du robot, c'est chercher la transformation (x, y, θ) qui pose le mieux le scan courant sur une **référence**. Nous avons utilisé les trois références demandées : la **grid map** (distance au mur le plus proche, lue dans un champ de distance), la **carte vectorielle** (distance exacte au segment le plus proche) et un **autre scan** pris à proximité (point-à-point ou point-à-droite)."));
C.push(H2("2.1 Les méthodes"));
C.push(table(["Méthode", "Famille de l'énoncé", "Idée"], [
  ["Brute force", "Recherche exhaustive", "Teste toutes les poses d'une grille ±0,5 m / ±15° et garde la meilleure"],
  ["Multi-résolution", "Multi-résolution", "Recherche grossière avec un score « flou », puis de plus en plus fine autour du meilleur"],
  ["Gauss-Newton", "Descente de gradient", "Minimise la somme des distances au carré ; poids robustes contre les points aberrants"],
  ["ICP", "Calcul direct itéré", "Plus proche point, puis rotation et translation exactes (SVD), et on recommence"],
  ["Filtre à particules", "Probabiliste", "400 poses tirées, pondérées par leur score, ré-échantillonnées 15 fois"],
  ["Direct (murs / moments)", "Calcul direct", "Orientation dominante des murs, ou centre et axe d'inertie du nuage"],
], [22, 22, 56]));
C.push(space());
C.push(...img("fig_references.png", 600, "Figure 6 — Les trois références. En rouge, un scan à une pose fausse ; en orange, la distance de chaque point à la référence."));
C.push(H2("2.2 Protocole d'évaluation"));
C.push(B("**Mêmes scans et mêmes poses initiales** pour toutes les méthodes. La pose initiale est décalée de la vraie de 5 niveaux d'erreur, jusqu'à 50 cm et 20°."));
C.push(B("**Réussite** : erreur de position < 5 cm **et** erreur d'angle < 2°. On mesure aussi l'erreur médiane et le temps de calcul."));
C.push(B("**Simulation** : la vraie pose est connue exactement. **Réel** : les 9 scans du Jour 1, chacun localisé sur une carte construite **sans lui**."));
C.push(H2("2.3 Principaux résultats"));
C.push(B("**Simulation** : les méthodes itératives retrouvent la pose à **quelques millimètres et moins de 0,3°** près. La plus précise est Gauss-Newton sur la carte vectorielle : 4 mm et 0,06°, en 6 ms."));
C.push(B("**Scans réels** : la précision tombe à **1,5 à 3 cm**. C'est l'ordre de grandeur de l'incertitude des poses de référence elles-mêmes."));
C.push(B("**Robustesse** : quand la pose initiale est mauvaise (50 cm / 20°), seules la **multi-résolution** et les **particules** restent fiables sur le réel. Gauss-Newton et ICP sont les plus rapides (moins de 20 ms), mais ce sont des méthodes **locales** : partis trop loin, elles s'arrêtent sur un faux minimum."));
C.push(B("**Calculs directs** : ils échouent presque toujours sur le réel, car le mobilier perturbe les murs détectés et deux scans voisins ne voient jamais exactement la même chose."));
C.push(...img("sensibilite_reel.png", 620, "Figure 7 — Taux de réussite selon l'erreur de la pose initiale, sur les scans réels."));
C.push(H2("2.4 Incertitude des poses de référence"));
C.push(P("Au Jour 1, les poses du lidar **n'ont pas été mesurées** : la référence de chaque scan réel est la pose trouvée par l'assemblage. Nous avons estimé son incertitude de deux façons. L'**approximation de Laplace** (covariance s²(JᵀWJ)⁻¹) donne environ 4 mm et 0,1°. L'**écart entre méthodes** est plutôt de 1 à 3 cm. La première valeur est optimiste, car elle suppose des erreurs indépendantes d'un point à l'autre."));
C.push(warn("**Ce qui manque.** L'énoncé demande aussi des **poses mesurées sur le robot**, avec leur incertitude. Un protocole a été préparé (`rendu/protocole_phase_1_9/version_1` : 3 repères au sol, 3 poses par repère, mètre ruban et rapporteur, fiches de relevé). Il **n'a pas encore été réalisé** : les deux séances sur le robot ont servi à la cartographie, pas à cette campagne de mesures. La précision réelle des méthodes n'a donc pas été vérifiée par une mesure indépendante."));

// ================================================================ JOUR 3
C.push(H1("3. Jour 3 — Cartographier avec le vrai robot"));
C.push(H2("3.1 L'application Lidar Lab"));
C.push(P("Pour le Jour 3, nous avons utilisé l'application web **Lidar Lab**. Elle a plusieurs parties :"));
C.push(B("Le **robot** : l'ESP32 lit le LD06 et crée son propre point d'accès Wi-Fi. Il répond à des requêtes HTTP simples : `/scan` (le dernier tour du lidar), `/drive` (vitesse des deux roues), `/turn` (rotation d'un angle donné) et `/stop`. Il ne traite **qu'une requête à la fois** et **s'arrête seul** s'il ne reçoit aucun ordre pendant 0,7 s : c'est une sécurité si la liaison Wi-Fi est coupée."));
C.push(B("Le **serveur** (Node.js, sur le PC) parle au robot. Il enregistre chaque séance dans un dossier, sans jamais écraser une séance précédente, et sert la page web."));
C.push(B("La **page web**, sur le PC ou le téléphone, sert au pilotage, à la capture des scans et à l'affichage de la carte. Elle exporte aussi la grid map et la carte vectorielle."));
C.push(...img("lidar_lab_capture.png", 520, "Figure 8 — Interface de Lidar Lab : panneau de connexion au robot (à gauche) et scans d'une séance réelle superposés (à droite)."));
C.push(H2("3.2 L'Auto-SLAM : la carte construite pendant le trajet"));
C.push(P("Le robot n'a pas d'odométrie : chaque nouveau scan est donc localisé **sur la grid map déjà construite** avec les scans précédents. C'est le scan matching du Jour 2 appliqué en continu. La recherche est globale : elle combine un champ de distance aux murs, plusieurs poses de départ et un affinage. Le scan n'est accepté que si au moins **35 %** de ses points tombent sur des murs connus et si la pose n'est **pas ambiguë** : le deuxième meilleur candidat, s'il est éloigné, doit avoir un coût plus de 8 % supérieur. Sinon, le scan est **refusé** plutôt que mal placé. On parle de SLAM (localisation et cartographie simultanées) car chaque scan accepté enrichit à son tour la carte."));
C.push(H2("3.3 Assemblage après coup et fiabilisation"));
C.push(P("Nous avons ajouté un bouton **« Localiser et construire la carte »** qui assemble après coup des scans déjà enregistrés. Il traite les scans dans l'ordre : chacun est d'abord cherché **près du précédent** (le robot n'a pas pu aller loin entre deux captures), puis, en cas d'échec, sur toute la carte, avec les mêmes refus que l'Auto-SLAM. Les poses de l'Auto-SLAM servent seulement de **référence de cohérence**, pas de vérité. Le travail s'est fait en quatre étapes, chacune avec ses critères **annoncés avant** la mesure :"));
C.push(table(["Étape", "Changement", "Résultat (critère annoncé)"], [
  ["1", "Bouton d'assemblage (recherche près du scan précédent, puis globale)", "Séance réelle du 04/11 : 40/40 scans placés, mais **9 scans tournés de 90°** par rapport à l'Auto-SLAM"],
  ["2", "Filtre « espace libre » : on écarte les candidats qui mettent des points dans du vide déjà observé", "Aucun seuil ne donne 0 faux positif (**critère non atteint**). Sur le réel, le filtre crée des sauts de 3,8 m. Il est **laissé désactivé**."],
  ["3", "Ambiguïté jugée aussi sur le **recouvrement** : un rival dont le recouvrement est dans l'intervalle à 95 % du meilleur rend la pose ambiguë", "Faux positifs (corpus simulé jamais vu au réglage) : **255 → 48**. Réel : **0 scan à 90°**, 31 des 32 scans comparables à moins de 10 cm de l'Auto-SLAM"],
  ["4", "Refus si la pose retenue met plus de **14,2 %** de ses points dans du vide confirmé (seuil réglé sur le réel, jamais de changement de candidat)", "Faux positifs : **48 → 2** sur 600 (critère « 0 » **non atteint**). Toujours 15/15 bonnes poses sur `repetition_tp2`."],
], [8, 44, 48]));
C.push(space());
C.push(...img("comparaison_autoslam_vs_assemblage.png", 560, "Figure 9 — Séance réelle du 04/11 à l'étape 1 : à gauche l'Auto-SLAM (35 scans recalés), à droite le bouton d'assemblage (40 scans placés). Une partie de la carte de droite est tournée de 90° : c'est le défaut corrigé par l'étape 3."));
C.push(...img("fig_faux_positifs.png", 600, "Figure 10 — Nombre de faux positifs (pose acceptée alors qu'elle est fausse) après chaque étape. Scans SIMULÉS, sur des tirages jamais utilisés pour régler les seuils."));
C.push(P("**Pourquoi la salle symétrique pose problème.** Dans une salle presque rectangulaire et vide, une pose tournée de 90° ou de 180° peut produire **exactement le même scan**. Aucun critère de forme ne peut alors trancher. C'est sans doute la cause de la divergence de 90° du 04/11. Le critère de l'étape 3 ne choisit pas une autre pose : il **refuse** de décider. Il ne peut donc qu'ajouter des refus, jamais un faux positif (vérifié par un test automatique)."));
C.push(warn("**Limites restantes.** (1) Il reste 2 faux positifs sur 600 cas simulés : un dans le bras étroit d'une salle en L, un en symétrie centrale. (2) Sur la séance réelle, le **scan 28** est placé à **4,1 m** de la pose de l'Auto-SLAM. L'Auto-SLAM l'avait accepté avec seulement 53 % de recouvrement : sans vérité terrain, on ne sait pas lequel des deux a raison."));
C.push(H2("3.4 Séance du 10/11 : cartographie de la salle"));
C.push(P("Le 10/11, de 13 h 31 à 14 h 01, le robot a parcouru la salle, piloté par Wi-Fi depuis le téléphone. **49 scans** ont été capturés ; l'Auto-SLAM en a recalé **48**. La grid map montre une salle d'environ **13 × 12 m**, avec un grand rectangle au centre, qui correspond à la table et à l'armoire présentes dans la salle. Les points bleus sont les poses du robot au moment des captures."));
C.push(...img("s10_grid_map.png", 430, "Figure 11 — Grid map de la séance du 10/11 (48 scans réels, cellules de 5 cm, poses de l'Auto-SLAM)."));
C.push(P("La carte vectorielle a été construite avec les outils du Jour 1, puis nettoyée en plusieurs versions. Chaque version est rangée dans un **nouveau dossier**, la précédente reste intacte, et la règle de chaque version a été fixée **avant** le calcul :"));
C.push(table(["Version", "Règle", "Segments", "Statut"], [
  ["Brute", "Tous les segments extraits des 48 scans", "166", "Carte mesurée"],
  ["Filtrée", "Garder les segments vus au moins 2 fois", "59", "Carte mesurée (71 % de la longueur gardée)"],
  ["Fusionnée", "Fusion si angle ≤ 5°, écart ≤ 10 cm, trou ≤ 30 cm", "58", "**Carte de référence**"],
  ["Affichage", "Même fusion avec un écart ≤ 25 cm", "53", "Illustration seulement : **masque la dérive**"],
], [14, 46, 12, 28]));
C.push(space());
C.push(...img("s10_vectorielle_fusionnee.png", 400, "Figure 12 — Carte vectorielle fusionnée de la séance du 10/11 (58 segments)."));
C.push(P("**Ce que montre la fusion.** Une seule fusion a eu lieu. Plusieurs murs apparaissent **en double**, décalés de **14 à 23 cm** : c'est le même mur, vu depuis des poses légèrement fausses. Il s'agit de la **dérive** de l'Auto-SLAM, qui s'accumule le long du trajet. Fusionner ces murs (version d'affichage) donne une carte plus jolie, mais **cache cette erreur**. Pour la corriger vraiment, il faudrait une **fermeture de boucle** (recaler le robot quand il revient dans une zone déjà vue) ou des poses mesurées au sol."));

// ================================================================ BONUS
C.push(H1("4. Bonus — Exploration automatique et localisation globale"));
C.push(warn("**Les sections 4.1 à 4.3 (exploration) sont validées en SIMULATION seulement.** L'exploration n'a **pas encore été essayée sur le vrai robot** : ces chiffres viennent d'un robot simulé. La section 4.4 (localisation globale) utilise, elle, des **scans réels**."));
C.push(H2("4.1 Principe"));
C.push(P("Le robot alterne deux phases : il **regarde**, puis il **avance d'un petit pas**. À chaque arrêt, il capture un scan et le localise sur la carte (Auto-SLAM). Il cherche ensuite la **frontière** la plus proche, c'est-à-dire une cellule libre voisine d'une cellule inconnue. Il calcule un chemin pour l'atteindre (parcours en largeur sur la grille, avec des obstacles **gonflés de 25 cm**) et fait un pas d'au plus 35 cm vers ce but. L'exploration s'arrête quand il ne reste **plus aucune frontière accessible**."));
C.push(H2("4.2 Sécurité"));
C.push(B("Avant chaque pas, le robot vérifie **à l'arrêt** que le couloir devant lui est libre : il faut au moins la distance du pas plus une marge."));
C.push(B("Le robot ne traite qu'une requête à la fois. Il ne prend donc **aucun scan pendant un pas** (1,4 s au plus) : un obstacle qui apparaît pendant ce temps n'est vu qu'au contrôle suivant, robot arrêté."));
C.push(B("Si **deux recalages de suite sont refusés**, l'exploration s'arrête (« position perdue ») et le robot est arrêté."));
C.push(B("Le bouton **STOP** passe toujours, même pendant une exploration. Le pilotage manuel est refusé tant que l'exploration tourne."));
C.push(H2("4.3 Résultats en simulation"));
C.push(P("Le robot simulé reproduit les défauts du vrai : erreur de rotation de ±5 %, erreur de distance de ±10 %, arrêt seul après 0,7 s sans ordre, et collision détectée à 12 cm d'un mur. La salle de test n'a **jamais servi pendant la mise au point** : deux pièces reliées par une porte, avec une table et une armoire. Critères fixés avant le test final : **aucune collision**, poses à moins de **10 cm et 3°** de la vérité, au moins **80 %** de la salle cartographiée."));
C.push(table(["Tirage", "Scans", "Distance parcourue", "Erreur de pose max", "Collision", "Salle cartographiée"],
  EXPLO.map((r) => [String(r.graine), String(r.scans), fr(r.distance_m) + " m", fr(r.erreur_max_cm) + " cm", r.collision ? "oui" : "non", Math.round(r.couverture * 100) + " %"]),
  [12, 12, 20, 20, 14, 22]));
C.push(space());
C.push(...img("fig_exploration_simulation.png", 640, "Figure 13 — Trois explorations simulées de la salle de test. En vert, la vraie trajectoire ; en rouge, les poses recalées ; le carré noir marque le départ."));
C.push(P("Les trois critères sont atteints : aucune collision, une erreur de pose de **8 cm au plus**, et **95 à 96 %** de la salle cartographiée. Le robot va jusqu'à la porte et cartographie la seconde pièce depuis l'embrasure. Avec le tirage 11, il hésite longtemps devant la porte (53 scans au lieu de 17 à 19) : il fait beaucoup de petits pas avant de trouver un passage assez large pour ses 25 cm de marge. Un dernier test lance le **vrai serveur** avec un faux robot qui répond comme le sketch : l'exploration avance, refuse le pilotage manuel, et STOP arrête tout."));
C.push(H2("4.4 Retrouver où le robot a pris un scan (localisation globale)"));
C.push(P("Question : le robot a pris un scan, mais il **ne sait pas du tout où il est**. Peut-il retrouver sa position à partir de ce seul scan et de la carte ? C'est la **localisation globale** (on parle aussi de robot « kidnappé »). Contrairement au Jour 2, aucune pose de départ n'est donnée : la recherche porte sur **toute la salle et sur 360°**. L'essai a été fait sur les **48 scans réels** de la séance du 10/11, avec les **deux** cartes : la grid map et la carte vectorielle."));
C.push(P("**Protocole, écrit et committé avant la mesure** (`resultats/localisation_globale/version_1/PROTOCOLE.md`) :", { align: AlignmentType.LEFT }));
C.push(B("Pour chaque scan, la grid map et la carte vectorielle sont construites **sans ce scan**, ni les scans pris au même endroit (moins de 15 cm). Sinon le scan serait déjà dans sa propre carte."));
C.push(B("**Candidats** : le scan est comparé à la carte pour tous les angles, de 2° en 2°, par une corrélation calculée par FFT ; on garde les 8 meilleures positions distinctes. Chaque candidat est ensuite **affiné** avec les méthodes du Jour 2 (multi-résolution, puis Gauss-Newton), sur la carte testée."));
C.push(B("**Décision**, avec les règles de Lidar Lab sans aucun seuil nouveau : on garde le candidat qui a la plus grande part p de points à moins de 10 cm d'un mur. Il est **refusé** si p < 35 %, ou si un candidat éloigné obtient un score presque aussi bon (dans l'intervalle à 95 % de p)."));
C.push(B("**Critères** : 0 faux positif (pose acceptée à plus de 30 cm ou 5° de l'Auto-SLAM), et au moins 80 % des scans retrouvés à moins de 30 cm et 5°."));
C.push(table(["Carte", "Concordants (< 10 cm, < 2°)", "Proches (< 30 cm, < 5°)", "Faux positifs", "Refus", "Écart médian", "Temps"], [
  ["Grid map", "42", "1", "**0**", "5", "1,8 cm / 0,29°", "3,3 s"],
  ["Carte vectorielle", "47", "0", "**0**", "1", "2,5 cm / 0,28°", "3,0 s"],
], [18, 16, 15, 13, 9, 16, 13]));
C.push(legend("48 scans réels du 10/11 ; écarts mesurés par rapport aux poses de l'Auto-SLAM (pas une vérité terrain)."));
C.push(...img("localisation_globale.png", 620, "Figure 14 — Localisation globale de chaque scan sans pose de départ. Cercle bleu : pose de l'Auto-SLAM ; croix : pose trouvée et acceptée. Un cercle sans croix est un scan refusé."));
C.push(P("**Les deux critères sont atteints, sur les deux cartes.** La **carte vectorielle fait mieux** : 47 scans retrouvés sur 48, contre 43 sur la grid map. L'écart ne vient pas d'un meilleur score en général : la part médiane de points sur les murs est presque la même (0,80 sur la grid map, 0,83 sur la carte vectorielle), et l'avance médiane sur le rival aussi (0,21). La différence se joue sur **quelques scans difficiles** : les scans 1 à 3, pris au point de départ, puis les scans 11 et 25. Une explication possible est que la carte vectorielle donne des distances exactes, alors que la grid map arrondit les murs à 5 cm ; cet essai ne permet pas de le démontrer."));
C.push(P("**Les refus ont joué leur rôle.** Pour les scans 1 à 3 sur la grid map, et pour le scan 40 sur la carte vectorielle, le meilleur candidat était **faux, à plus de 2 m**. Un rival presque aussi bon a déclenché le refus, et aucune de ces poses fausses n'a été acceptée. Les scans 11 et 25 ont été refusés sur la grid map alors que leur pose était juste : c'est le prix de la prudence. Le calcul a été lancé deux fois, avec des résultats identiques."));
C.push(note("**Limites.** (1) La référence est l'Auto-SLAM, qui dérive d'environ 20 cm sur cette séance : on mesure la **cohérence** avec l'Auto-SLAM, pas une précision absolue. (2) L'essai porte sur des scans enregistrés, pas sur le robot en direct. L'essai sur le robot consisterait à le poser n'importe où, idéalement sur un repère mesuré au sol, et à lui demander où il est."));

// ================================================================ BILAN / ÉNONCÉ
C.push(H1("5. Bilan par rapport à l'énoncé"));
C.push(table(["Demande", "Statut", "Où"], [
  ["J1 — Extraction des données du LD06", "Fait", "`carto/scan.py`, `carto/plot_app.py`, sketchs ESP32 (`arduino/`)"],
  ["J1 — Visualisation des nuages de points", "Fait", "Lidar Plot (Python), Lidar Lab (web)"],
  ["J1 — Grid map (création, mise à jour)", "Fait", "`carto/gridmap.py`, Lidar Lab"],
  ["J1 — Segments (extraction, angle, fusion, découpe…)", "Fait", "`carto/segments.py`"],
  ["J1 — Carte vectorielle", "Fait", "`carto/vectormap.py`, `carto/build_map.py`"],
  ["J2 — Localisation sur grid map, carte vectorielle, entre scans", "Fait", "`carto/localisation.py` (7 méthodes)"],
  ["J2 — Évaluation chiffrée (erreurs, temps, réussite, pose initiale)", "Fait (simulation et scans réels)", "`carto/evaluation.py`, `resultats/localisation`"],
  ["J2 — Poses **mesurées** sur le robot et leur incertitude", "**Non fait** : protocole prêt, mesures non réalisées", "`rendu/protocole_phase_1_9`"],
  ["J3 — Cartographie avec le robot", "Fait (2 séances réelles : 40 et 49 scans)", "Lidar Lab, `data/robot_wifi`, `data/mesures_phase19_2026-11-09`"],
  ["Bonus — Exploration automatique", "Fait **en simulation** ; non essayé sur le robot", "`serveur_robot/exploration.js`"],
  ["Bonus — Localisation globale d'un scan (grid map et carte vectorielle)", "Fait sur **48 scans réels** ; critères atteints", "`carto/localisation_globale.py`, `resultats/localisation_globale`"],
  ["Livrable — code avec historique", "Les deux dépôts git sont prêts ; l'archive à rendre reste à faire", "—"],
], [44, 28, 28]));

// ================================================================ LIMITES
C.push(H1("6. Limites et suite"));
C.push(B("**Pas de vérité terrain sur le robot.** Les poses des séances réelles viennent de l'Auto-SLAM. Elles servent de référence de cohérence, mais ne sont pas une mesure. La prochaine étape utile est la campagne de poses mesurées (protocole prêt)."));
C.push(B("**Dérive sans fermeture de boucle.** Sur une grande salle, l'erreur s'accumule le long du trajet (murs doublés de 14 à 23 cm le 10/11). Une fermeture de boucle, ou une optimisation de toutes les poses ensemble, la réduirait."));
C.push(B("**Salles symétriques.** Quand deux poses donnent le même scan, aucune méthode ne peut choisir. Notre réponse est de refuser le scan : c'est plus sûr, mais il faut alors en capturer un autre."));
C.push(B("**Pas d'odométrie.** Une mesure de rotation des roues donnerait une pose prédite. La recherche resterait alors locale, donc plus rapide et moins exposée aux ambiguïtés."));
C.push(B("**Exploration non essayée sur le robot.** Le simulateur reproduit les erreurs de commande, pas les vitres, les personnes, ni les reflets du vrai lidar."));

// ================================================================ CONCLUSION PERSONNELLE
C.push(H1("Conclusion personnelle"));
C.push(P("??Cette partie est à rédiger par l'étudiant, avec ses propres mots.?? Quelques questions pour guider la rédaction :"));
C.push(...N([
  "Qu'avez-vous appris de plus important sur la cartographie et la localisation pendant ce TP ?",
  "Quelle a été la plus grosse difficulté (matériel, Wi-Fi, mesures, algorithmes) et comment l'avez-vous surmontée ?",
  "Entre la simulation et le vrai robot, qu'est-ce qui vous a le plus surpris ?",
  "Que pensez-vous de la règle « fixer les critères avant de regarder les résultats » ? Vous a-t-elle évité une conclusion trop rapide ?",
  "Si vous aviez une séance de plus, que feriez-vous en premier, et pourquoi ?",
  "Quelles vérifications avez-vous faites vous-même pour vous assurer que vos résultats sont justes ?",
]));
C.push(P("??Votre texte ici.??"));

// ================================================================ ANNEXE
C.push(H1("Annexe — Reproduire les résultats"));
C.push(H2("TP-cartographie (Python)"));
C.push(table(["Commande", "Effet"], [
  ["`python -m carto plot`", "Ouvre Lidar Plot pour visualiser et placer des scans"],
  ["`python -m carto assemble <dossier_scans>`", "Assemble les scans et écrit grid map + carte vectorielle dans un nouveau dossier"],
  ["`python -m carto evaluer --reel <dossier>`", "Évaluation complète des méthodes de localisation (Jour 2)"],
  ["`python -m pytest`", "65 tests automatiques"],
], [45, 55]));
C.push(H2("Lidar Lab (codex_lidar)"));
C.push(table(["Commande", "Effet"], [
  ["`node serveur_robot/serveur.js --dossier <nouveau_dossier>`", "Lance le serveur (port 8001) ; ouvrir ensuite la page sur le PC ou le téléphone"],
  ["`node --test tests/*.test.js`", "60 tests automatiques, dont l'exploration simulée (X1 à X6) et les faux positifs"],
  ["`node tests/corpus_faux_positifs.js`", "Refait la mesure des faux positifs (scans simulés)"],
], [45, 55]));
C.push(space());
C.push(P("Les figures nouvelles de ce rapport sont produites par `sources/dump_explo.js` (exploration simulée, tirages 11 à 13) et `sources/gen_figures.py`. Les autres figures sont copiées des comptes rendus précédents et des dossiers de données, sans modification."));

// ================================================================ DOCUMENT
const doc = new Document({
  creator: "Rapport final TP cartographie", title: "Rapport final — Cartographie et localisation (LD06)",
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
      children: [new TextRun({ text: "Rapport final — Cartographie et localisation", size: 16, color: "888888" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: ["Page ", PageNumber.CURRENT, " / ", PageNumber.TOTAL_PAGES], size: 16, color: "888888" })] })] }) },
    children: C,
  }],
});

const outFile = path.join(OUT_DIR, "rapport_final_TP_cartographie_v2.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outFile, buf); console.log("->", outFile); });
