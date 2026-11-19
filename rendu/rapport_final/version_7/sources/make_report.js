// Rapport final du TP (jours 1 à 3 + bonus), version 7 — génération du .docx (docx-js)
// Lancer : NODE_PATH=<dossier contenant node_modules/docx> node make_report.js
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, LevelFormat, Footer, Header, PageNumber, BorderStyle, PageBreak,
  TableOfContents, ExternalHyperlink,
} = require("docx");

const OUT_DIR = path.join(__dirname, "..");
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

// extrait de code : police à chasse fixe, fond gris clair
const code = (lines) => lines.map((l, i) => new Paragraph({ spacing: { after: 0, line: 240 }, shading: { type: ShadingType.CLEAR, fill: "F3F4F6" },
  indent: { left: 200, right: 200 }, children: [new TextRun({ text: l || " ", font: "Consolas", size: 17 })] }));
// ================================================================== CONTENU
const C = [];

// ---------------------------------------------------------------- page de titre
C.push(new Paragraph({ spacing: { before: 1500, after: 200 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Rapport final de TP — Jours 1, 2, 3 et bonus", size: 30, color: "555555" })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
  children: [new TextRun({ text: "Cartographie et localisation", bold: true, size: 56, color: ACCENT })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 500 },
  children: [new TextRun({ text: "avec un lidar LD06 : du nuage de points au robot qui se localise et explore", size: 30, color: ACCENT })] }));
C.push(...img("lidarlab_demo_localisation.png", 600));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 400, after: 100 },
  children: [new TextRun({ text: "Module : Cartographie et localisation appliquée à la robotique mobile", size: 22 })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
  children: [new TextRun({ text: "Étudiant : ", size: 22 }), new TextRun({ text: "Nom Prénom (à compléter)", size: 22, highlight: "yellow", bold: true })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Novembre 2026", size: 22 })] }));

// ---------------------------------------------------------------- sommaire
C.push(new Paragraph({ children: [new PageBreak()] }));
C.push(new Paragraph({ children: [new TextRun({ text: "Sommaire", bold: true, size: 32, color: ACCENT })], spacing: { after: 200 } }));
C.push(new TableOfContents("Sommaire", { hyperlink: true, headingStyleRange: "1-2" }));

// ================================================================ INTRODUCTION
C.push(H1("Introduction"));
C.push(P("Ce TP suit le chemin complet d'un robot mobile équipé d'un lidar 2D. Le **Jour 1** transforme les mesures brutes du lidar LD06 en deux cartes de la salle : une **grid map** (carte d'occupation) et une **carte vectorielle** (ensemble de segments). Le **Jour 2** traite le problème inverse : connaissant une carte, **retrouver la pose du robot** (x, y, θ) par **scan matching**. Le **Jour 3** combine les deux pour faire de la **localisation et cartographie simultanées** (début de SLAM) et produire la carte complète de la salle de classe. Le **bonus** rend le robot autonome : il choisit lui-même où aller pour cartographier."));
C.push(H2("Matériel"));
C.push(B("**Lidar LD06** : environ 450 mesures par tour, 10 tours par seconde, portée utile d'environ 12 m, précision annoncée de ±30 mm."));
C.push(B("**Robot** à deux roues motrices piloté par une carte **ESP32**, sans odométrie : sa position ne peut venir que du lidar."));
C.push(B("Un **PC** et un **téléphone** pour piloter le robot et capturer les scans."));
C.push(H2("Démarche"));
C.push(P("Le robot était partagé entre quatre groupes. Chaque idée a donc été préparée et vérifiée **en simulation** (scans LD06 simulés, robot simulé avec ses erreurs de rotation et de distance), puis essayée **sur le robot** dès qu'il était disponible. Les séances réelles utilisées dans ce rapport sont celles du 02/11, du 03/11, du 04/11 et du 10/11."));
C.push(P("Pour chaque évaluation, les seuils et critères de réussite ont été **fixés avant** de regarder les résultats, et écrits dans un protocole committé dans Git. Les résultats simulés et réels sont toujours présentés séparément."));
C.push(note("**Deux outils complémentaires** ont été développés (chapitre 1) : **carto**, une bibliothèque Python avec l'interface **Lidar Plot**, pour l'analyse, les cartes et l'évaluation chiffrée ; et **Lidar Lab**, une application web reliée au robot, pour le pilotage, la cartographie en direct (Auto-SLAM), la localisation et l'exploration automatique."));

// ================================================================ 1. LES DEUX OUTILS
C.push(H1("1. Les deux outils développés"));
C.push(...img("architecture_deux_outils.png", 640, "Figure 1 — Architecture des deux outils. Ils lisent et écrivent les mêmes fichiers : un scan enregistré par le robot s'ouvre dans les deux."));
C.push(H2("1.1 Pourquoi deux outils"));
C.push(P("Le premier outil (**carto**, Python) a servi aux Jours 1 et 2 : il fallait comprendre et mesurer chaque brique (grid map, segments, sept méthodes de localisation) sur des scans enregistrés, avec des tests automatiques et un banc d'évaluation. Le second outil (**Lidar Lab**, web) répond au Jour 3 : il faut une interface qui **parle au robot**, capture un scan à chaque arrêt, le localise aussitôt sur la carte déjà construite et affiche la carte qui grandit. Les deux partagent les mêmes formats de fichiers, ce qui permet de rejouer dans l'outil 1 tout relevé fait avec l'outil 2."));
C.push(table(["", "Outil 1 — carto + Lidar Plot", "Outil 2 — Lidar Lab"], [
  ["Langage", "Python (numpy, matplotlib, tkinter)", "JavaScript (navigateur) + Node.js (serveur), C++ (ESP32)"],
  ["Rôle principal", "Analyse hors ligne, cartes, évaluation chiffrée", "Pilotage du robot, SLAM en direct, démonstration"],
  ["Entrées", "Port série du LD06, fichiers CSV / Teleplot", "Robot en Wi-Fi ou USB, fichiers CSV, MapTool, RobotControl"],
  ["Cartes", "Grid map log-odds, carte vectorielle, rapports PNG + Markdown", "Grid map en direct, carte vectorielle, exports CSV / MapTool / JSON"],
  ["Localisation", "7 méthodes sur 3 références, banc d'évaluation, localisation globale", "Recalage global sur la carte cumulée, refus des poses douteuses, démo « où était le robot ? »"],
  ["Robot", "—", "Pilotage PC et téléphone, Auto-SLAM, exploration automatique"],
  ["Tests", "65 tests (pytest)", "64 tests (node --test), dont robot simulé"],
], [16, 42, 42]));
C.push(space());
C.push(P("**Ce que le second outil apporte.** Il localise chaque nouveau scan sur **toute** la carte (recherche globale sur 360°), refuse un scan plutôt que de le placer au mauvais endroit, enregistre chaque séance sur le disque sans jamais l'écraser, et fonctionne aussi depuis le téléphone. C'est lui qui a produit les cartes réelles du 04/11 et du 10/11."));

C.push(H2("1.2 Outil 1 — carto et Lidar Plot (Python)"));
C.push(table(["Module", "Lignes", "Rôle"], [
  ["`scan.py`", "189", "Scans (polaire), poses 2D, lecture des formats LD06 / Teleplot / CSV, correction du sens de rotation"],
  ["`gridmap.py`", "220", "Grid map en log-odds : création depuis un scan, mise à jour, durée de vie des cellules"],
  ["`segments.py`", "297", "Extraction de segments et opérations : angle, proximité, fusion, intersection, découpe"],
  ["`vectormap.py`, `build_map.py`", "104 + 349", "Carte vectorielle scan après scan ; chaîne complète scans → cartes → rapport"],
  ["`register.py`", "375", "Recalage de scans à positions inconnues : recherche globale par FFT, puis ICP"],
  ["`localisation.py`", "536", "Sept méthodes de localisation sur grid map, carte vectorielle et entre scans"],
  ["`localisation_globale.py`", "175", "Retrouver la pose d'un scan sans pose initiale"],
  ["`evaluation.py`", "689", "Banc d'évaluation : mêmes scans et poses initiales, erreurs, temps, taux de réussite"],
  ["`plot_app.py`, `localise_dialog.py`", "1555 + 428", "Lidar Plot : affichage temps réel, captures, édition des poses, fenêtre Localiser"],
  ["`viewer.py`, `assistant.py`, `guide.py`", "250 + 980 + 297", "Visualiseur de scans, assistant de capture guidée"],
  ["`simulate.py`", "159", "Scans LD06 simulés (vérité connue) pour les tests"],
], [30, 14, 56]));
C.push(space());
C.push(...img("fig_lidarplot.png", 600, "Figure 2 — Lidar Plot : plusieurs scans superposés, une couleur par scan, pose de chaque scan modifiable."));
C.push(P("**Utilisation en ligne de commande** : `python -m carto plot` (Lidar Plot), `python -m carto assemble <dossier>` (cartes d'une séance), `python -m carto grid` et `python -m carto vector` (outils demandés au Jour 1), `python -m carto localiser` et `python -m carto evaluer` (Jour 2)."));
C.push(P("**Extrait de code — mise à jour de la grid map** (`gridmap.py`). Chaque rayon libère les cellules traversées et marque la cellule d'impact. Une cellule n'est comptée qu'une fois par scan, sinon les cellules proches du lidar, traversées par des centaines de rayons, deviendraient « sûres » en un seul scan :"));
C.push(...code([
  "for ex, ey in (pts - self.origin) / self.res:",
  "    ray = supercover(s[0], s[1], ex, ey)      # toutes les cellules traversées",
  "    free.update(ray); occ.add((int(np.floor(ex)), int(np.floor(ey))))",
  "free -= occ                                   # l'impact l'emporte",
  "self.logodds[fy, fx] += self.l_free           # -0,4 : vu libre",
  "self.logodds[oy, ox] += self.l_occ            # +0,85 : vu occupé",
  "np.clip(self.logodds, self.l_min, self.l_max, out=self.logodds)",
]));

C.push(H2("1.3 Outil 2 — Lidar Lab (web, serveur, robot)"));
C.push(...img("lidarlab_vue_ensemble.png", 640, "Figure 3 — Interface de Lidar Lab avec la séance réelle du 10/11 chargée : chargement et connexion à gauche, carte au centre, exports en haut."));
C.push(P("**Fonctionnement d'une capture en Auto-SLAM.** Le robot s'arrête ; le serveur lit un tour complet du lidar ; `lidar_core.js` cherche la pose de ce scan sur la grid map construite avec les scans précédents ; si la pose est fiable, le scan est ajouté et la carte est mise à jour ; sinon il est mis en attente et réessayé plus tard. Tout est enregistré dans un dossier de séance (scans CSV, `poses.json`, `grid_map.csv`, `seance.json`)."));
C.push(table(["Module", "Lignes", "Rôle"], [
  ["`lidar_core.js`", "745", "Cœur de calcul, testable sans navigateur : lecture des CSV, filtres, grid map, localisation globale, choix du candidat, assemblage d'une séance"],
  ["`index.html`", "—", "Interface : chargement, couches (points, grid map, vectorielle), localisation, comparaisons, exports"],
  ["`serveur_robot/serveur.js`", "495", "Serveur Node.js : relais vers le robot, séances sur disque, Auto-SLAM, exploration"],
  ["`serveur_robot/pilote_lidar_lab.js`", "354", "Panneau de pilotage dans l'interface : boutons, clavier, capture, exploration"],
  ["`serveur_robot/exploration.js`", "355", "Exploration automatique par frontières (bonus)"],
  ["`serveur_robot/telephone.html`", "228", "Version téléphone, reliée à la même séance que le PC"],
  ["`demo_localisation.js`", "244", "Démo « où le robot a-t-il pris ce scan ? »"],
], [32, 12, 56]));
C.push(space());
C.push(P("La carte s'affiche avec trois couches : les **points** des scans (une couleur par scan), la **grid map** et la **carte vectorielle**."));
C.push(...img("grid_map_propre_10_11_sombre.png", 330, "Figure 4 — Grid map de la séance du 10/11 (48 scans, cellules de 5 cm) : blanc = occupé, bleu-gris = libre, noir = inconnu ; vue tournée pour aligner les murs, quadrillage d'un mètre."));
C.push(...img("carte_vectorielle_propre_10_11_sombre.png", 330, "Figure 5 — Carte vectorielle de la même séance, nettoyée : 58 segments vus au moins deux fois, murs proches fusionnés ; vue tournée pour aligner les murs, quadrillage d'un mètre."));
C.push(...img("lidarlab_panneau_robot.png", 230, "Figure 6 — Panneau « Robot Wi-Fi » : pilotage, STOP, rotations de 15° et 45°, Auto-SLAM, exploration."));
C.push(P("**Extrait de code — décision d'acceptation** (`lidar_core.js`, résumé). La recherche produit plusieurs poses candidates sur toute la carte ; la meilleure n'est acceptée que si elle est à la fois bien recouverte et non ambiguë :"));
C.push(...code([
  "const r = locateScanOnGrid(points, grille, { minOverlap: 0.35, overlapAmbiguity: true });",
  "// r.ok = false si :",
  "//  - moins de 35 % des points tombent sur des murs déjà cartographiés (recouvrement),",
  "//  - ou un candidat éloigné (> 0,6 m ou > 0,4 rad) recouvre la carte presque autant :",
  "//    recouvrement rival ≥ p − 2·√(p(1−p)/N)  (intervalle à 95 % d'une proportion)",
  "if (r.ok) { scan.pose = r.pose; ajouterALaCarte(scan); } else mettreEnAttente(scan);",
]));

C.push(H2("1.4 Programme embarqué de l'ESP32"));
C.push(P("Plusieurs versions du programme de l'ESP32 ont été écrites (dossier `arduino/`, versions 1 à 7, toutes conservées dans l'historique). La **version 5** (`ESP32_robot_wifi_v5`) est la version retenue : c'est celle qui a fonctionné le plus régulièrement pendant les essais, notamment avec le partage de connexion du téléphone."));
C.push(B("**Réseau** : le robot rejoint le Wi-Fi défini dans `wifi_secrets.h` (box ou partage de connexion du téléphone). Sans réponse en 15 s, il crée son propre réseau de secours (192.168.4.1). Il répond aussi au nom `robot-lidar.local`. Le mot de passe n'est jamais dans le dépôt (`wifi_secrets.h` est ignoré par Git ; un modèle est fourni)."));
C.push(B("**Lidar** : le LD06 est lu sur GPIO33 (PWM sur GPIO32) ; le dernier tour complet est servi par `/scan` au format CSV (angle, distance, intensité), avec un indicateur « robot en mouvement »."));
C.push(B("**Moteurs** : `/drive` (vitesse des deux roues, rampe de démarrage), `/turn` (rotation d'un angle donné, durée renvoyée), `/stop`."));
C.push(B("**Sécurité** : sans ordre depuis 0,5 s, le robot ralentit et s'arrête tout seul (perte du Wi-Fi, téléphone fermé)."));

// ================================================================ 2. JOUR 1
C.push(H1("2. Jour 1 — Construire les cartes"));
C.push(H2("2.1 Extraction des données du lidar"));
C.push(P("Le LD06 envoie sur sa liaison série des **paquets de 47 octets** : un en-tête, la vitesse de rotation, l'angle de début, 12 mesures (distance en mm et intensité), l'angle de fin, un horodatage et un code de contrôle (CRC). L'angle de chaque mesure est interpolé entre l'angle de début et l'angle de fin ; un tour complet est reconstitué quand l'angle repasse par zéro, puis enregistré en CSV (angle, distance, intensité)."));
C.push(P("**Difficulté** : le LD06 tourne dans le **sens horaire**. Sans correction, la carte est le miroir de la salle. Le sens est corrigé une fois pour toutes à la lecture."));
C.push(...img("fig_scan_polaire_cartesien.png", 560, "Figure 7 — Un scan en coordonnées polaires (tel que mesuré), puis en cartésien : x = d·cos θ, y = d·sin θ."));
C.push(H2("2.2 Visualisation et superposition des scans"));
C.push(P("Les deux outils affichent plusieurs scans dans un repère commun, une couleur par scan, avec une pose (x, y, θ) modifiable pour chacun : à la souris (glisser pour déplacer, clic droit pour tourner) ou en saisissant les valeurs. Comme les positions n'étaient pas mesurées, un **recalage automatique** a été ajouté : recherche sur 360° par corrélation (FFT), puis affinage par ICP."));
C.push(...img("1_assemblage.png", 360, "Figure 8 — Les scans du 02/11 superposés dans le repère commun après recalage."));
C.push(H2("2.3 Grid map"));
C.push(P("La salle est découpée en **cellules de 5 cm**. Pour chaque point, le rayon du lidar est tracé jusqu'au point par l'algorithme **supercover** (variante de Bresenham qui ne saute aucune cellule) : les cellules traversées sont **libres**, la cellule du point est **occupée**. Les observations sont cumulées en **log-odds** (logarithme du rapport de probabilités), ce qui transforme la mise à jour bayésienne en addition. Les deux outils demandés existent : **création** d'une carte à partir d'un scan et d'une pose, et **mise à jour** d'une carte existante."));
C.push(B("**Choix** : +0,85 pour un impact, −0,4 pour un passage libre (on croit plus un impact qu'un passage), valeurs bornées à ±4 pour que la carte reste capable de changer."));
C.push(B("**Propriétés ajoutées** : durée de vie des cellules (oubli progressif), filtrage des points isolés, filtre temporel des retours non confirmés (personnes qui passent)."));
C.push(B("**Limites** : la qualité dépend de la justesse des poses ; les vitres et surfaces noires renvoient peu ou pas d'écho."));
C.push(...img("fig_grid_etapes.png", 600, "Figure 9 — Grid map créée avec un scan, puis mise à jour avec 3 puis 9 scans (noir : occupé, blanc : libre, gris : inconnu)."));
C.push(H2("2.4 Segments"));
C.push(P("Chaque scan est découpé en groupes de points voisins, puis chaque groupe est approché par des segments (**split-and-merge**, Douglas-Peucker). Les opérations demandées sont toutes programmées et testées :"));
C.push(table(["Opération", "Méthode et choix"], [
  ["Nuage → segments", "Groupes de points voisins (trou ≤ 20 cm), puis découpe récursive au point le plus éloigné (seuil 10 cm) ; dans la carte, segments de 15 cm minimum"],
  ["Angle entre deux segments", "Angle non orienté entre leurs directions, dans [0°, 90°]"],
  ["Segments « proches »", "Angle ≤ tolérance ET écart latéral ≤ tolérance ET trou le long du mur ≤ tolérance"],
  ["Fusion", "Direction moyenne pondérée par les longueurs, extrémités = projections extrêmes, nombre d'observations additionné"],
  ["Intersection", "Résolution paramétrique ; parallèles et colinéaires traités à part"],
  ["Découpe", "Intersection exigée sur les deux segments et strictement à l'intérieur du segment coupé ; colinéaires non découpés ; longueurs égales à la tolérance près : on garde le côté du premier point. Tolérance de position 1e-6 m (1 µm) ; parallélisme si |sin| ≤ 1e-9 ; cas limites testés"],
], [26, 74]));
C.push(space());
C.push(...img("fig_segments_operations.png", 580, "Figure 10 — Les opérations sur les segments : extraction, angle, proximité, fusion, intersection, découpe."));
C.push(H2("2.5 Carte vectorielle"));
C.push(P("La carte vectorielle est construite scan après scan avec ces fonctions : les segments du nouveau scan sont placés dans le repère de la carte, puis chaque segment proche d'un segment existant est **fusionné** avec lui (son nombre d'observations augmente), les autres sont ajoutés. En option, un rayon du lidar qui traverse un ancien segment le **découpe** (une porte qui s'est ouverte). La carte obtenue est compacte et précise : quelques dizaines de segments au lieu de dizaines de milliers de cellules."));
C.push(H2("2.6 Les cartes de toutes les séances réelles"));
C.push(P("Les figures suivantes montrent, pour chaque séance réelle, la grid map et la carte vectorielle calculées avec les mêmes outils et les mêmes réglages. L'épaisseur d'un segment indique combien de fois il a été vu."));
C.push(...img("carte_02_11.png", 640, "Figure 11 — Séance du 02/11 (9 scans) : grid map et carte vectorielle (82 segments)."));
C.push(...img("carte_03_11.png", 640, "Figure 12 — Séance du 03/11, relevés combinés (39 scans) : grid map et carte vectorielle (359 segments)."));
C.push(...img("carte_04_11.png", 640, "Figure 13 — Séance du robot du 04/11 (35 scans recalés par l'Auto-SLAM) : grid map et carte vectorielle (81 segments)."));
C.push(...img("carte_10_11.png", 640, "Figure 14 — Séance du robot du 10/11 (48 scans recalés) : la salle complète, environ 13 × 10 m, avec la table et l'armoire au centre (166 segments)."));
C.push(P("**Grid map ou carte vectorielle ?** La grid map dit aussi où est l'espace **libre** et l'**inconnu**, ce qui sert à la navigation et à l'exploration ; elle ne demande aucune extraction. La carte vectorielle est plus **compacte** et donne des distances **exactes** aux murs, ce qui la rend plus précise pour se localiser (chapitre 3) ; en revanche le mobilier produit beaucoup de petits segments, qu'il faut filtrer (chapitre 4)."));

// ================================================================ 3. JOUR 2
C.push(H1("3. Jour 2 — Se localiser par scan matching"));
C.push(P("Se localiser, c'est chercher la pose (x, y, θ) qui pose le mieux le scan courant sur une **référence**. Les trois références demandées sont traitées par le **même code** grâce à une interface commune : chaque référence donne, pour un point, sa distance à la référence et la direction de cette distance."));
C.push(table(["Référence", "Distance d'un point à la référence"], [
  ["Grid map", "Distance à la cellule occupée la plus proche, lue dans un champ de distance (interpolation bilinéaire)"],
  ["Carte vectorielle", "Distance exacte au segment le plus proche"],
  ["Entre scans", "Distance au point le plus proche (point-à-point) ou à la droite locale (point-à-droite) du scan de référence"],
], [24, 76]));
C.push(space());
C.push(...img("fig_references.png", 600, "Figure 15 — Les trois références. En rouge, un scan à une pose fausse ; en orange, la distance de chaque point à la référence."));
C.push(H2("3.1 Méthodes"));
C.push(table(["Méthode", "Famille", "Idée"], [
  ["Brute force", "Recherche exhaustive", "Toutes les poses d'une grille ±0,5 m / ±15°, pas de 4 cm et 1,5°"],
  ["Multi-résolution", "Multi-résolution", "Recherche grossière avec un score « flou », puis de plus en plus fine"],
  ["Gauss-Newton", "Descente de gradient", "Moindres carrés pondérés (poids de Cauchy), amortissement de Levenberg-Marquardt"],
  ["ICP", "Calcul direct itéré", "Plus proche point puis rotation et translation exactes (SVD)"],
  ["Filtre à particules", "Probabiliste", "400 poses pondérées par leur score, ré-échantillonnées 15 fois"],
  ["Murs / moments", "Calcul direct", "Orientation dominante des murs, ou centre et axe d'inertie du nuage"],
], [22, 22, 56]));
C.push(space());
C.push(P("**Extrait de code — un pas de Gauss-Newton** (`localisation.py`). Pour un petit déplacement de la pose, la distance d'un point varie de g · dp ; la ligne de Jacobien d'un point est donc [gx, gy, −gx(py − y) + gy(px − x)] :"));
C.push(...code([
  "d, g = ref.query(points_monde)                       # distance et direction",
  "J = np.column_stack([g[:, 0], g[:, 1], -g[:, 0] * (p[:, 1] - y) + g[:, 1] * (p[:, 0] - x)])",
  "w = 1 / (1 + (d / echelle) ** 2)                    # poids robustes de Cauchy",
  "dx = -np.linalg.solve(J.T @ (J * w[:, None]) + lam * diag, J.T @ (w * d))",
]));
C.push(H2("3.2 Protocole d'évaluation"));
C.push(B("**Mêmes scans et mêmes poses initiales** pour toutes les méthodes ; pose initiale décalée de 5 niveaux d'erreur, jusqu'à 50 cm et 20°."));
C.push(B("**Réussite** : erreur de position < 5 cm **et** erreur d'angle < 2° (une cellule de grid map, et un mur à 3 m décalé de 10 cm au plus). On mesure aussi les erreurs médianes et le temps de calcul."));
C.push(B("**Simulation** : la vraie pose est connue exactement. **Réel** : chaque scan est localisé sur une carte construite **sans lui**."));
C.push(H2("3.3 Résultats"));
C.push(B("**Simulation** : les méthodes itératives retrouvent la pose à quelques millimètres et moins de 0,3° près ; la meilleure est Gauss-Newton sur la carte vectorielle : **4 mm et 0,06° en 6 ms**."));
C.push(B("**Scans réels** : **1,5 à 3 cm**, l'ordre de grandeur de l'incertitude des poses de référence."));
C.push(B("**Robustesse** : jusqu'à 50 cm et 20° d'erreur initiale, seules la **multi-résolution** et les **particules** restent fiables sur le réel (83 à 89 %). Gauss-Newton et ICP sont les plus rapides (moins de 20 ms) mais locaux."));
C.push(B("**Incertitude des références** : approximation de Laplace, environ 4 mm et 0,1° ; écart entre méthodes, 1 à 3 cm (valeur plus réaliste)."));
C.push(...img("sensibilite_reel.png", 620, "Figure 16 — Taux de réussite selon l'erreur de la pose initiale, sur les scans réels."));
C.push(H2("3.4 Retrouver où le robot était, sans aucune pose de départ"));
C.push(P("Pour aller plus loin, chaque scan de la séance du 10/11 a été cherché **sur toute la salle et sur 360°**, sans pose de départ, sur la grid map **et** sur la carte vectorielle construites sans ce scan. Méthode : candidats trouvés par corrélation (FFT), affinés par multi-résolution puis Gauss-Newton ; refus si le recouvrement est insuffisant ou si un autre candidat est presque aussi bon."));
C.push(table(["Référence", "Retrouvés (< 10 cm, < 2°)", "Proches (< 30 cm, < 5°)", "Fausses poses", "Refus", "Écart médian"], [
  ["Grid map", "42 / 48", "1", "**0**", "5", "1,8 cm / 0,29°"],
  ["Carte vectorielle", "**47 / 48**", "0", "**0**", "1", "2,5 cm / 0,28°"],
], [20, 18, 17, 14, 11, 20]));
C.push(...img("localisation_globale.png", 620, "Figure 17 — Chaque scan du 10/11 localisé sans pose initiale (cercle : pose de l'Auto-SLAM ; croix : pose trouvée)."));
C.push(P("Aucune pose fausse n'a été acceptée : quand la meilleure pose était fausse (scans pris au point de départ, à plus de 2 m), un rival presque aussi bon a déclenché le refus. La **carte vectorielle** retrouve un scan de plus que la grid map, avec ses distances exactes aux murs."));

// ================================================================ 4. JOUR 3
C.push(H1("4. Jour 3 — SLAM et carte complète de la salle"));
C.push(H2("4.1 Auto-SLAM : la carte construite pendant le trajet"));
C.push(P("Le robot n'a pas d'odométrie : chaque nouveau scan est localisé **sur la grid map déjà construite** avec les scans précédents (Jour 2), puis ajouté à la carte (Jour 1). C'est la boucle de localisation et cartographie simultanées. Le scan n'est accepté que si au moins 35 % de ses points tombent sur des murs connus et si la pose n'est pas ambiguë ; sinon il est mis en attente et réessayé quand la carte a grandi."));
C.push(H2("4.2 Assembler une séance après coup et éviter les fausses poses"));
C.push(P("Le bouton **« Localiser et construire la carte »** assemble après coup des scans enregistrés : chaque scan est cherché près du précédent puis sur toute la carte. Une salle presque rectangulaire et vide a un piège : une pose tournée de 90° ou de 180° peut donner presque le même scan. Plusieurs règles ont été ajoutées et mesurées sur un corpus de 600 scans simulés jamais utilisés pour régler les seuils :"));
C.push(table(["Étape", "Règle ajoutée", "Résultat"], [
  ["1", "Recherche près du scan précédent, puis globale", "Séance réelle du 04/11 : 40/40 placés, mais 9 scans tournés de 90°"],
  ["3", "Ambiguïté jugée aussi sur le **recouvrement** (intervalle à 95 %)", "Fausses poses : **255 → 48** ; réel : **0 scan à 90°**, 31/32 à moins de 10 cm de l'Auto-SLAM"],
  ["4", "Refus si la pose met trop de points dans un espace déjà vu libre (14,2 %)", "Fausses poses : **48 → 2** sur 600"],
], [8, 46, 46]));
C.push(space());
C.push(...img("comparaison_autoslam_vs_assemblage.png", 540, "Figure 18 — Séance du 04/11 avant correction : à gauche l'Auto-SLAM, à droite l'assemblage, dont une partie était tournée de 90°."));
C.push(...img("fig_faux_positifs.png", 580, "Figure 19 — Nombre de fausses poses acceptées après chaque étape (scans simulés, tirages jamais utilisés pour régler les seuils)."));
C.push(H2("4.3 La carte complète de la salle (10/11)"));
C.push(P("Le 10/11, de 13 h 31 à 14 h 01, le robot a parcouru la salle, piloté en Wi-Fi depuis le téléphone : **49 scans** capturés, **48** recalés par l'Auto-SLAM. La grid map montre une salle d'environ **13 × 10 m** (13,0 × 10,3 m mesurés sur les murs de la carte vectorielle), avec la table et l'armoire au centre (figure 14)."));
C.push(P("La carte vectorielle brute contient 166 segments, dont beaucoup de petits objets vus une seule fois (pieds de chaises, personnes). Elle a été nettoyée en trois versions, chacune dans un nouveau dossier, avec une règle fixée avant le calcul :"));
C.push(table(["Version", "Règle", "Segments"], [
  ["Brute", "Tous les segments des 48 scans", "166"],
  ["Filtrée", "Segments vus au moins 2 fois", "59"],
  ["Fusionnée", "Fusion si angle ≤ 5°, écart ≤ 10 cm, trou ≤ 30 cm", "58"],
  ["Affichage", "Même fusion avec un écart ≤ 25 cm", "53"],
], [16, 64, 20]));
C.push(space());
C.push(...img("s10_comparaison_filtree.png", 600, "Figure 20 — Carte vectorielle du 10/11 avant et après filtrage (segments vus au moins deux fois)."));
C.push(...img("carte_vectorielle_propre_10_11_claire.png", 470, "Figure 21 — Carte vectorielle fusionnée du 10/11 (58 segments, 85 m de murs) : salle de 13,0 × 10,3 m mesurée sur les murs, mobilier au centre."));
C.push(...img("s10_comparaison_affichage.png", 600, "Figure 22 — Version d'affichage : les murs doublés sont fusionnés."));
C.push(P("**Ce que montre la fusion.** Plusieurs murs apparaissent en double, décalés de 14 à 23 cm : c'est le même mur vu depuis des poses légèrement différentes, la **dérive** qui s'accumule le long du trajet sans odométrie. La version fusionnée garde cette information ; la version d'affichage la masque et sert seulement à illustrer."));
C.push(H2("4.4 Démonstration : où le robot a-t-il pris ce scan ?"));
C.push(P("Dans Lidar Lab, un panneau de démonstration tire un scan **au hasard**, le retire de la carte, puis le cherche sur toute la grid map, sur 360°, sans position de départ. Il affiche la position trouvée et l'écart avec la pose de l'Auto-SLAM. Sur les 48 scans du 10/11 : **42 retrouvés, aucune fausse position**, écart médian **2,5 cm** ; les 6 autres sont refusés comme ambigus. La vidéo `demo_localisation_scan_v2.mp4` montre trois tirages."));
C.push(...img("lidarlab_demo_localisation.png", 620, "Figure 23 — La démo : en jaune, le scan tiré au hasard posé à la position trouvée ; en haut à gauche, ce que voyait le robot."));
C.push(P("**La vidéo de la démonstration** (76 s) montre trois tirages à la suite : la carte de départ, le scan tiré au hasard, la recherche, puis la position trouvée. Les écarts avec la pose de l'Auto-SLAM sont de 2,5 cm, 0,0 cm et 2,5 cm. La planche ci-dessous en reprend les étapes."));
C.push(...img("planche_video_demo.png", 640, "Figure 24 — Étapes de la vidéo de démonstration (images extraites de la vidéo)."));
C.push(new Paragraph({ spacing: { before: 120, after: 80 }, alignment: AlignmentType.LEFT, children: [
  new TextRun({ text: "Vidéo : " , bold: true }),
  new ExternalHyperlink({ link: "video/demo_localisation_scan.mp4", children: [new TextRun({ text: "video/demo_localisation_scan.mp4", style: "Hyperlink", color: "0563C1", underline: {} })] }),
  new TextRun({ text: " (lien vers le fichier fourni avec ce rapport). Dans la version Word, la vidéo est aussi intégrée ci-dessous : double-cliquer sur l'icône pour la lancer." }),
] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "[[VIDEO]]" })] }));

// ================================================================ 5. BONUS
C.push(H1("5. Bonus — Exploration automatique"));
C.push(H2("5.1 Principe"));
C.push(P("Le robot alterne : il **regarde** (scan + recalage), puis il **avance d'un petit pas**. Il cherche la **frontière** la plus proche (cellule libre voisine de l'inconnu), calcule un chemin pour l'atteindre (parcours en largeur sur la grille, obstacles gonflés de 25 cm), pivote et avance d'au plus 35 cm. L'exploration s'arrête quand il n'y a plus de frontière accessible."));
C.push(H2("5.2 Sécurité"));
C.push(B("Avant chaque pas, le couloir devant le robot est vérifié **à l'arrêt** : il faut au moins la longueur du pas plus 35 cm de libre."));
C.push(B("Deux recalages refusés de suite : arrêt « position perdue » et robot arrêté."));
C.push(B("STOP passe toujours ; le pilotage manuel est refusé pendant l'exploration ; le robot s'arrête seul sans ordre."));
C.push(B("Nombre de pas maximum réglable, et mesure du déplacement réel de chaque pas par le recalage, pour étalonner la vitesse."));
C.push(H2("5.3 Validation"));
C.push(P("Le robot simulé reproduit les défauts du vrai : erreur de rotation de ±5 %, erreur de distance de ±10 %, arrêt seul après 0,7 s sans ordre, collision détectée à 12 cm d'un mur."));
C.push(table(["Essai", "Résultat"], [
  ["Salle de test jamais vue (deux pièces, table, armoire), 3 tirages", "0 collision, poses à 8 cm au plus, **95 à 96 %** de la salle cartographiée"],
  ["Salle réelle du 10/11 reconstruite (166 segments), 3 départs", "0 collision, **87 %, 87 % et 57 %** de la salle ; dérive jusqu'à 25 cm sur 50 m de trajet"],
  ["Décisions rejouées sur les 48 scans réels du 10/11 et les 35 du 04/11", "Deux défauts trouvés et corrigés : le lidar voit une partie du robot (points à 11 cm, avant droit) ; pas de demi-tour dans un recoin"],
  ["Vrai serveur relié à un faux robot qui répond comme le sketch", "L'exploration avance, refuse le pilotage manuel, STOP arrête tout"],
], [46, 54]));
C.push(space());
C.push(...img("fig_exploration_simulation.png", 640, "Figure 25 — Explorations de la salle de test : vraie trajectoire en vert, poses recalées en rouge."));
C.push(...img("partie_b_exploration.png", 640, "Figure 26 — Exploration dans la salle du 10/11 reconstruite à partir de ses murs réels."));
C.push(P("Une fiche d'essai sur le robot est prête (`rendu/essai_exploration_robot/version_3`) : un pas, puis trois, puis dix à vingt, avec des critères fixés avant l'essai et des tableaux de relevés."));

// ================================================================ 6. SYNTHÈSE PAR OUTIL
C.push(H1("6. Synthèse par outil"));
C.push(P("Pour chaque outil : les résultats visuels obtenus, les choix effectués, les fonctionnalités intégrées et les méthodes implémentées."));
C.push(table(["Outil", "Résultats visuels", "Choix et fonctionnalités", "Méthodes"], [
  ["Extraction LD06 (sketchs ESP32, `scan.py`)", "Figure 7", "Correction du sens de rotation ; CSV angle / distance / intensité ; robot en Wi-Fi (V5) avec réseau de secours", "Décodage des paquets de 47 octets, interpolation des angles"],
  ["Visualisation (Lidar Plot, Lidar Lab)", "Figures 2, 3, 8", "Une couleur par scan, pose modifiable à la souris ou au clavier, recalage automatique", "Corrélation par FFT sur 360°, ICP"],
  ["Grid map", "Figures 4, 9, 11 à 14", "Cellules de 5 cm ; création et mise à jour ; durée de vie, filtres", "Supercover, log-odds"],
  ["Segments", "Figure 10", "Six opérations, tolérances et cas limites testés", "Split-and-merge, géométrie paramétrique"],
  ["Carte vectorielle", "Figures 5, 11 à 14, 20 à 22", "Fusion scan après scan, découpe par les rayons, versions filtrée et fusionnée", "Fusion pondérée par les longueurs"],
  ["Localisation (Jour 2)", "Figures 15 à 17", "Trois références, banc d'évaluation, localisation sans pose initiale", "Brute force, multi-résolution, Gauss-Newton, ICP, particules, calculs directs"],
  ["SLAM (Lidar Lab)", "Figures 14, 18, 19, 23, 24", "Pilotage PC et téléphone, séances enregistrées, refus des poses douteuses, démo", "Localisation globale sur carte cumulée, ambiguïté sur le recouvrement"],
  ["Exploration (bonus)", "Figures 25, 26", "Pas courts, contrôle à l'arrêt, STOP prioritaire, demi-tour", "Frontières, parcours en largeur sur grille gonflée"],
], [18, 15, 36, 31]));

// ================================================================ 7. LIMITES
C.push(H1("7. Limites et perspectives"));
C.push(B("**Dérive sans fermeture de boucle** : l'erreur s'accumule le long du trajet (murs doublés de 14 à 23 cm le 10/11). Une fermeture de boucle, ou une optimisation de toutes les poses ensemble, la réduirait."));
C.push(B("**Pas d'odométrie** : une mesure de rotation des roues donnerait une pose prédite ; la recherche resterait locale, donc plus rapide et moins exposée aux ambiguïtés."));
C.push(B("**Poses de référence** : les poses des séances réelles viennent de l'Auto-SLAM ; une campagne de poses mesurées au sol (protocole prêt) permettrait de chiffrer la précision réelle."));
C.push(B("**Refus « espace libre » (étape 4)** : son seuil, réglé sur la séance du 04/11, refuse beaucoup de bonnes poses sur celle du 10/11, où des objets ont bougé pendant le relevé ; il est à revoir."));
C.push(B("**Salles symétriques** : quand deux poses donnent le même scan, aucune méthode ne peut choisir ; la bonne réponse est de refuser et de capturer un autre scan."));

// ================================================================ CONCLUSION PERSONNELLE
C.push(H1("Conclusion personnelle"));
C.push(P("??À rédiger avec vos propres mots.?? L'énoncé demande un court récapitulatif de ce que vous retenez du module."));
C.push(P("**Ce que j'ai apprécié.** Pistes : voir la carte apparaître, piloter le robot, comparer les méthodes, retrouver la position d'un scan…"));
C.push(P("??Votre texte ici.??"));
C.push(P("**Ce que j'ai moins apprécié.** Pistes : matériel partagé entre quatre groupes, Wi-Fi, temps de calcul, prises de mesures…"));
C.push(P("??Votre texte ici.??"));
C.push(P("**Ce que j'améliorerais.** Pistes : dans le module (organisation, matériel) ou dans votre travail (mesurer les poses au sol, fermeture de boucle, odométrie…)."));
C.push(P("??Votre texte ici.??"));

// ================================================================ ANNEXE
C.push(H1("Annexe — Contenu du livrable et instructions"));
C.push(H2("Contenu du dossier .zip"));
C.push(table(["Élément", "Contenu"], [
  ["`rapport_final_TP_cartographie.docx` / `.pdf`", "Ce rapport"],
  ["`video/demo_localisation_scan.mp4`", "Démo : un scan tiré au hasard, retrouvé sur la grid map"],
  ["`depots/TP-cartographie/`", "Copie du dépôt Git de l'outil 1, avec tout son historique (`git log`)"],
  ["`depots/lidar_lab/`", "Copie du dépôt Git de l'outil 2, avec tout son historique"],
  ["`LISEZMOI.txt`", "Comment installer et tester chaque outil"],
], [42, 58]));
C.push(H2("Tester les outils"));
C.push(table(["Commande", "Effet"], [
  ["`pip install -r requirements.txt` puis `python -m pytest`", "Outil 1 : 65 tests automatiques"],
  ["`python -m carto plot`", "Ouvre Lidar Plot (scans en direct ou fichiers)"],
  ["`python -m carto assemble data/salle_2026-11-02_18h31`", "Assemble une séance et écrit grid map + carte vectorielle dans un nouveau dossier"],
  ["`python -m carto evaluer --rapide`", "Banc d'évaluation de la localisation (version courte)"],
  ["`node --test tests/*.test.js` (dans `lidar_lab`)", "Outil 2 : 64 tests automatiques"],
  ["`node serveur_robot/serveur.js --dossier <nouveau_dossier>`", "Lance Lidar Lab ; ouvrir http://localhost:8000 (avec ou sans robot)"],
  ["Ouvrir `index.html` dans Chrome ou Edge", "Lidar Lab sans serveur : charger des CSV de `data/`"],
], [50, 50]));
C.push(space());
C.push(P("Les deux dépôts sont versionnés avec Git, avec un commit par modification et un message qui explique le changement. Les données enregistrées ne sont jamais modifiées : chaque nouveau calcul écrit dans un nouveau dossier `version_N`."));

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

const outFile = path.join(OUT_DIR, "rapport_final_TP_cartographie_v7.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outFile, buf); console.log("->", outFile); });
