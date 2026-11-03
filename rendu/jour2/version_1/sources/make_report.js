// Compte rendu TP Jour 2 — génération du .docx (docx-js)
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, Table, TableRow, TableCell,
  WidthType, ShadingType, ImageRun, LevelFormat, Footer, Header, PageNumber, BorderStyle, PageBreak,
  TableOfContents,
} = require("docx");

const OUT_DIR = String.raw`C:\Users\HP\TP-cartographie\rendu\jour2\version_1`;
const FIG = path.join(OUT_DIR, "figures");
const D = JSON.parse(fs.readFileSync(path.join(OUT_DIR, "sources", "donnees.json"), "utf8"));
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

const COMP_H = ["Référence", "Méthode", "Réussite", "Erreur position médiane (cm)", "Erreur angle médiane (°)", "Temps moyen (ms)"];
const COMP_W = [24, 18, 11, 17, 16, 14];
const comp = (jeu, refs) => table(COMP_H, D.comparaison[jeu].filter((r) => refs.includes(r[0])), COMP_W);
const sens = (jeu) => table(["Référence", "Méthode", ...D.levels], D.sensibilite[jeu], [23, 17, 12, 12, 12, 12, 12]);
const ALL = ["grid map", "carte vectorielle", "entre scans (point-à-point)", "entre scans (point-à-droite)"];
const legend = (t) => P(t, { align: AlignmentType.CENTER, run: { italics: true, size: 18, color: "555555" } });

// ---------------------------------------------------------------- page de titre
C.push(new Paragraph({ spacing: { before: 2600, after: 200 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Compte rendu de TP — Jour 2", size: 30, color: "555555" })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
  children: [new TextRun({ text: "Localisation par scan matching", bold: true, size: 52, color: ACCENT })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 700 },
  children: [new TextRun({ text: "sur grid map, carte vectorielle et entre scans", size: 34, color: ACCENT })] }));
C.push(...img("exemples_reel.png", 620));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 500, after: 100 },
  children: [new TextRun({ text: "Module : Cartographie et localisation appliquée à la robotique mobile", size: 22 })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
  children: [new TextRun({ text: "Étudiant : ", size: 22 }), new TextRun({ text: "Nom Prénom (à compléter)", size: 22, highlight: "yellow", bold: true })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Séance du 3 novembre 2026", size: 22 })] }));

// ---------------------------------------------------------------- sommaire
C.push(new Paragraph({ children: [new PageBreak()] }));
C.push(new Paragraph({ children: [new TextRun({ text: "Sommaire", bold: true, size: 32, color: ACCENT })], spacing: { after: 200 } }));
C.push(new TableOfContents("Sommaire", { hyperlink: true, headingStyleRange: "1-2" }));

// ================================================================ INTRODUCTION
C.push(H1("Introduction"));
C.push(P("Au Jour 1, nous avons construit une **grid map** et une **carte vectorielle** de la salle à partir de scans du lidar LD06. Le Jour 2 traite le problème inverse : connaissant une carte, **retrouver où se trouve le robot**. C'est la **localisation par scan matching** : on cherche la pose (x, y, θ) qui superpose le mieux le scan courant sur une référence."));
C.push(P("La pose transforme chaque point du scan, mesuré dans le repère du lidar, en un point de la carte : **p_carte = R(θ) · p_lidar + (x, y)**. Une bonne pose place les points du scan sur les murs de la référence ; une mauvaise pose les place à côté. Toutes les méthodes cherchent donc la pose qui rend la **distance entre les points du scan et la référence** la plus petite possible."));
C.push(H2("Ce que demande l'énoncé"));
C.push(B("**Trois types de référence** : localisation sur une grid map, sur une carte vectorielle, et entre deux scans (le scan à comparer est pris près de la position du scan de référence)."));
C.push(B("**Plusieurs familles de méthodes** : recherche exhaustive (brute force), descente de gradient, multi-résolution, méthodes probabilistes, et calcul direct."));
C.push(B("**Une évaluation chiffrée** : mêmes scans et mêmes poses initiales pour toutes les méthodes ; erreur de position (m), erreur angulaire (°), temps de calcul et taux de réussite selon des seuils explicites ; variation de la pose initiale ; poses connues en simulation ; incertitude des références mesurées sur le robot."));
C.push(H2("Ce qui a été réalisé"));
C.push(P("Nous avons programmé, en Python (numpy), **sept méthodes** qui fonctionnent sur les trois références, puis un **banc d'évaluation** qui les compare automatiquement. Il a été lancé sur une salle simulée, où la vraie pose est connue exactement, et sur les 9 scans réels de la salle enregistrés au Jour 1."));
C.push(table(["Fichier", "Rôle"], [
  ["`carto/localisation.py`", "Les trois références et les sept méthodes de localisation"],
  ["`carto/evaluation.py`", "Banc d'évaluation : jeux de test, poses initiales, mesures, tableaux et figures"],
  ["`python -m carto evaluer`", "Lance toute l'évaluation (environ 9 minutes) et écrit un nouveau dossier `resultats/localisation/version_N`"],
  ["`python -m carto localiser`", "Localise un scan sur une référence donnée (grid map, carte vectorielle ou scan)"],
  ["`tests/test_localisation.py`", "19 tests automatiques : chaque méthode sur chaque référence, distances exactes"],
], [35, 65]));

// ================================================================ 1. PRINCIPE
C.push(H1("1. Principe commun : mesurer l'écart à la référence"));
C.push(P("Pour comparer un scan à une référence, il faut une mesure de l'écart. Nous utilisons pour les trois références la même mesure : pour chaque point du scan, la **distance d** à la référence et la **direction g** dans laquelle cette distance augmente. Ce choix permet d'écrire chaque méthode **une seule fois** et de l'appliquer aux trois références, ce qui rend la comparaison équitable."));
C.push(table(["Référence", "Distance d d'un point du scan", "Comment elle est calculée"], [
  ["Grid map", "Distance à la cellule occupée la plus proche", "Un **champ de distance** est calculé une fois sur toute la grille ; on le lit par interpolation bilinéaire, ce qui donne aussi la pente (gradient)"],
  ["Carte vectorielle", "Distance exacte au segment le plus proche", "Projection du point sur le segment, bornée à ses extrémités"],
  ["Entre scans (point-à-point)", "Distance au point le plus proche du scan de référence", "Recherche du plus proche voisin"],
  ["Entre scans (point-à-droite)", "Distance à la droite locale du scan de référence", "La normale est estimée sur les 6 voisins du point de référence"],
], [20, 32, 48]));
C.push(...img("fig_references.png", 640, "Figure 1 — Les trois références (salle simulée). En rouge, un scan placé avec une pose fausse ; en orange, la distance de chaque point à la référence. La bonne pose rend toutes ces distances petites."));
C.push(P("Pour aller vite, la carte vectorielle et le scan de référence utilisent un **index spatial** : une grille fine (2 cm) qui mémorise, pour chaque case, le segment ou le point le plus proche. La distance est ensuite calculée exactement à ce segment ou à ce point."));
C.push(H2("Le score d'une pose"));
C.push(P("Les méthodes de recherche (brute force, multi-résolution, particules) comparent des poses entre elles grâce à un **score de vraisemblance** : la moyenne de exp(−d² / 2σ²) sur les points du scan. Un point posé sur un mur vaut 1, un point loin de tout mur vaut 0. Avec σ = 5 cm (la précision du LD06, 30 mm, plus une demi-cellule), le score vaut environ 0,8 pour une bonne pose."));
C.push(P("Ce score est **robuste** : un point qui ne correspond à rien dans la référence (une personne, une porte ouverte, une zone absente de la carte) ajoute simplement 0. Il ne fausse pas le résultat, contrairement à une somme de distances au carré."));

// ================================================================ 2. METHODES
C.push(H1("2. Les méthodes de recherche"));
C.push(table(["Méthode", "Famille (énoncé)", "Réglages"], [
  ["Brute force", "Recherche exhaustive", "±0,5 m et ±15° autour de la pose initiale, pas de 4 cm et 1,5° (14 196 poses)"],
  ["Multi-résolution", "Multi-résolution", "3 niveaux : 10 cm / 4° (σ = 15 cm), puis 3 cm / 1° (σ = 5 cm), puis 1 cm / 0,25° (σ = 3 cm)"],
  ["Gauss-Newton", "Descente de gradient", "Gauss-Newton amorti (Levenberg-Marquardt), poids robustes de Cauchy, 40 itérations au plus"],
  ["ICP", "Calcul direct itéré", "Plus proche point, puis rotation et translation exactes par SVD ; 60 itérations au plus"],
  ["Particules", "Probabiliste", "400 poses, 15 itérations, bruit initial 25 cm / 8°, resserré de 25 % à chaque itération"],
  ["Direct (murs)", "Calcul direct", "Carte vectorielle seulement : orientation des murs, puis une résolution de moindres carrés"],
  ["Direct (moments)", "Calcul direct", "Entre scans seulement : centre de gravité et axe principal d'inertie"],
], [20, 22, 58]));
C.push(H2("2.1 Recherche exhaustive (brute force)"));
C.push(P("On calcule le score de **toutes les poses** d'une grille régulière autour de la pose initiale et on garde la meilleure. La méthode ne peut pas se « tromper de sommet » à l'intérieur de sa fenêtre, mais elle a deux défauts : sa **précision est limitée par le pas** (au mieux ± la moitié du pas, soit 2 cm et 0,75°), et son **coût** croît comme le produit des trois dimensions. Diviser le pas par 2 multiplie le nombre de poses par 8. Elle échoue aussi si la vraie pose est hors de la fenêtre."));
C.push(H2("2.2 Multi-résolution"));
C.push(P("On fait d'abord une recherche exhaustive **grossière** sur toute la fenêtre, avec un score « flou » (σ grand). Puis on recommence avec un pas plus fin, seulement autour du meilleur résultat, et ainsi de suite. Le flou est essentiel : avec un σ de 15 cm, le score varie doucement et son sommet est assez large pour être trouvé avec un pas de 10 cm. Avec un σ de 3 cm, il est précis mais très étroit (figure 2). On obtient la précision du pas fin pour environ la moitié du coût de la brute force."));
C.push(...img("fig_paysage_score.png", 600, "Figure 2 — Score de la grid map autour de la vraie pose (au centre). À gauche, un σ large donne un grand bassin qu'une recherche grossière trouve facilement ; à droite, un σ fin donne un sommet précis mais étroit. Les « bras » de la croix montrent qu'un décalage le long d'un mur change peu le score."));
C.push(H2("2.3 Descente de gradient (Gauss-Newton)"));
C.push(P("On minimise E(x, y, θ) = Σ wᵢ dᵢ². Pour un petit déplacement de la pose, la distance d'un point varie de **g · dp**, où dp est le déplacement du point. La dérivée par rapport à la pose est donc la ligne de Jacobien **Jᵢ = [gₓ, g_y, −gₓ (p_y − y) + g_y (p_x − x)]**. À chaque itération, on résout le système linéaire (JᵀWJ + λ·diag) δ = −JᵀW d, puis on applique le pas δ s'il fait baisser le coût. Sinon, on augmente l'amortissement λ, ce qui raccourcit le pas : c'est la méthode de Levenberg-Marquardt."));
C.push(P("Les poids wᵢ = 1 / (1 + (dᵢ/c)²) (fonction de Cauchy) écartent les points aberrants. L'échelle c part de 30 cm, pour attirer les points encore loin de leur mur, et diminue jusqu'à 5 cm. La méthode est très rapide (environ 15 itérations, moins de 10 ms), mais **locale** : partie trop loin, elle peut s'arrêter sur un mauvais minimum."));
C.push(...img("fig_convergence_gn.png", 470, "Figure 3 — Convergence de Gauss-Newton sur la grid map, départ à 35 cm et 12° de la vraie pose. Les seuils de réussite (pointillés) sont franchis en 4 itérations ; l'erreur finale est d'environ 3 mm et 0,2°."));
C.push(H2("2.4 ICP (Iterative Closest Point)"));
C.push(P("À chaque itération, on associe chaque point du scan au **point le plus proche** de la référence (q = p − d·g). Avec ces paires, la meilleure rotation et la meilleure translation se calculent **directement**, sans approximation, par une décomposition SVD (problème de Procuste). On recommence jusqu'à ce que la pose ne bouge plus. Les paires trop éloignées sont rejetées ; le seuil vaut 3 fois la distance médiane et reste compris entre 10 et 50 cm."));
C.push(P("Une première version réduisait ce seuil d'un facteur fixe à chaque itération. Sur les scans réels, il devenait trop petit avant que le scan soit arrivé sur ses murs, et l'ICP se bloquait (11 % de réussite au lieu de 89 %). Le seuil qui suit l'erreur médiane a corrigé ce problème."));
C.push(H2("2.5 Méthode probabiliste : filtre à particules"));
C.push(P("On tire 400 poses (« particules ») autour de la pose initiale. Chacune reçoit un poids qui augmente avec son score. On en retire 400 au hasard selon ces poids : les bonnes poses sont dupliquées, les mauvaises disparaissent. On ajoute un petit bruit, réduit à chaque itération, et on recommence. Après 15 itérations, le résultat est la moyenne des 10 % meilleures particules. Comme la brute force, la méthode explore largement ; comme la multi-résolution, elle concentre ses calculs là où le score est bon. Elle ne dépend pas d'un pas de grille."));
C.push(H2("2.6 Calculs directs"));
C.push(P("**Sur la carte vectorielle**, on calcule l'orientation dominante des murs du scan et celle des murs de la carte : c'est la moyenne circulaire de 4φ, pondérée par la longueur des segments, car les murs d'une salle sont perpendiculaires. Leur différence donne θ, à 90° près ; on garde la solution la plus proche de θ initial. Une fois θ fixé, la distance d'un point à une droite est **linéaire** en (x, y), et la translation s'obtient en **une seule** résolution de moindres carrés, sans itérer."));
C.push(P("**Entre scans**, on utilise les **moments géométriques**. Les moments d'ordre 1 donnent le centre de gravité, ceux d'ordre 2 l'axe principal d'inertie de chaque nuage. On aligne les deux centres et les deux axes. C'est exact si les deux scans voient exactement la même chose."));

// ================================================================ 3. PROTOCOLE
C.push(H1("3. Protocole d'évaluation"));
C.push(H2("3.1 Jeux de test"));
C.push(P("**Simulation**, avec une vérité terrain exacte. La salle simulée est en L (8 × 6 m), avec une cloison percée d'une porte et un pilier. Les scans imitent le LD06 : 450 points par tour, bruit de 30 mm comme dans la datasheet, 2 % de mesures sans écho."));
C.push(B("La grid map (cellules de 5 cm) et la carte vectorielle sont **construites avec nos outils du Jour 1**, à partir de 4 scans simulés (positions pos1 à pos4). Ce ne sont pas des cartes parfaites."));
C.push(B("Scans à localiser sur ces cartes : **12 poses tirées au hasard** dans la salle, à plus de 40 cm des murs. Leurs scans sont simulés indépendamment des cartes (autre tirage du bruit)."));
C.push(B("Entre scans : chacun des 4 scans pos1 à pos4 sert de référence ; on localise 3 scans pris **à 30 cm et ±10°** de sa position, soit 12 cas."));
C.push(P("**Scans réels** : les scans 1 à 9 de la salle (Jour 1). Les scans 10 à 14, pris le lidar posé au sol, ne voient presque pas de murs et ont été écartés."));
C.push(B("Pour un scan donné, la grid map et la carte vectorielle sont construites **sans ce scan**, à partir des 8 autres. Sinon le scan se retrouverait dans sa propre carte, et la localisation serait faussement facile."));
C.push(B("Entre scans : chaque scan est localisé par rapport au scan dont la position est la plus proche."));
C.push(B("Pour le réel, chaque cas est tiré 2 fois par niveau d'erreur initiale, soit 18 essais par méthode et par niveau."));
C.push(H2("3.2 Poses initiales"));
C.push(P("On part de la vraie pose et on la décale de **75 à 100 % de d** mètres dans une direction au hasard, et de **75 à 100 % de a** degrés, avec un signe au hasard. Cinq niveaux (d ; a) sont testés : " + D.levels.join(", ") + ". Le tirage est fait **une seule fois par cas et par niveau**, puis la même pose initiale est donnée à toutes les méthodes."));
C.push(P("L'amplitude varie entre 75 et 100 % pour une raison précise. Avec un décalage exact de 8°, multiple du pas de 0,25° de la multi-résolution, la recherche retombait exactement sur la vraie pose et donnait une erreur nulle artificielle."));
C.push(H2("3.3 Mesures et seuils"));
C.push(B("**Erreur de position** : distance entre la position trouvée et la vraie position (m)."));
C.push(B("**Erreur angulaire** : écart entre θ trouvé et θ vrai, ramené dans [0°, 180°]."));
C.push(B("**Temps de calcul** de la localisation seule, en Python + numpy sur un PC portable. La référence (champ de distance, index) est construite une fois, avant les essais."));
C.push(B("**Réussite** : erreur de position **< 5 cm et** erreur angulaire **< 2°**."));
C.push(note("**Pourquoi ces seuils ?** 5 cm, c'est une cellule de la grid map et environ 1,5 fois la précision du LD06 (30 mm) : on ne peut pas exiger beaucoup mieux du capteur. 2° décale un mur situé à 3 m de 10 cm : au-delà, une carte construite avec cette pose « bave » visiblement. Une localisation réussie est donc assez précise pour ajouter le scan à la carte."));
C.push(P("La fenêtre des méthodes globales (brute force, multi-résolution) est fixée **à l'avance** à ±0,5 m et ±15°, sans connaître l'erreur réelle. Au dernier niveau (jusqu'à 20°), la vraie pose peut donc sortir de la fenêtre : c'est voulu, pour montrer cette limite."));

// ================================================================ 4. RESULTATS SIMULATION
C.push(H1("4. Résultats en simulation"));
C.push(P(`Les tableaux suivants comparent les méthodes au niveau intermédiaire d'erreur initiale (${D.levels[2]}), qui correspond à une pose estimée à l'œil ou par une odométrie médiocre. Chaque ligne porte sur ${D.n_cas["simulation"]} scans.`));
C.push(H2("4.1 Localisation sur grid map"));
C.push(comp("simulation", ["grid map"]));
C.push(space());
C.push(P("Toutes les méthodes réussissent. Gauss-Newton et ICP sont les plus précis (8 mm, 0,1°) et les plus rapides (moins de 20 ms). La brute force est limitée par son pas de 4 cm (2 cm d'erreur médiane) et coûte 60 fois plus de temps. La précision est un peu moins bonne que sur la carte vectorielle, car les murs de la grid map sont « crénelés » à 5 cm."));
C.push(H2("4.2 Localisation sur carte vectorielle"));
C.push(comp("simulation", ["carte vectorielle"]));
C.push(space());
C.push(P("C'est la référence la plus précise : **4 mm et 0,06°** pour Gauss-Newton en 6 ms. La distance à un segment est exacte et continue, sans discrétisation. Le calcul direct par les murs réussit lui aussi à ce niveau (2,9 cm, en 2 ms), mais il ne fait qu'**un** calcul de translation, avec des associations point-segment choisies à la pose initiale : il est moins précis que les méthodes itératives."));
C.push(H2("4.3 Localisation entre scans"));
C.push(comp("simulation", ["entre scans (point-à-point)", "entre scans (point-à-droite)"]));
C.push(space());
C.push(P("Les méthodes itératives atteignent 4 à 8 mm. La variante point-à-droite est un peu plus précise en angle : elle ne pénalise pas un glissement le long d'un mur, qui n'est qu'un effet de l'écart entre les points des deux scans. Les **moments géométriques échouent systématiquement** (18 cm, 5°). Les deux scans, pris à 30 cm l'un de l'autre, ne voient pas exactement les mêmes zones : le centre de gravité et l'axe d'inertie se déplacent avec ce qui est vu, pas seulement avec le robot."));
C.push(H2("4.4 Sensibilité à la pose initiale"));
C.push(P("Taux de réussite selon l'erreur de la pose initiale :"));
C.push(sens("simulation"));
C.push(space());
C.push(...img("sensibilite_simulation.png", 640, "Figure 4 — Taux de réussite en fonction de l'erreur de la pose initiale (simulation)."));
C.push(B("Gauss-Newton, ICP, multi-résolution et particules réussissent **100 %** des cas jusqu'à 50 cm / 20°."));
C.push(B("La brute force tombe à 42-50 % au dernier niveau, quand l'erreur d'angle (15 à 20°) sort de sa fenêtre de ±15°. La multi-résolution, qui a la même fenêtre, réussit quand même : son premier niveau, plus flou, trouve un bon sommet même légèrement en bord de fenêtre, et les niveaux suivants corrigent le reste."));
C.push(B("Le calcul direct par les murs ne supporte qu'une petite erreur initiale : 25 % de réussite à 35 cm, 0 % à 50 cm. Les associations faites à la pose initiale sont alors fausses, et il n'y a pas d'itération pour les corriger."));
C.push(...img("precision_temps_simulation.png", 520, "Figure 5 — Précision et coût de chaque méthode (simulation, " + D.levels[2] + ")."));
C.push(...img("exemples_simulation.png", 640, "Figure 6 — Exemples en simulation : scan à la pose initiale (rouge) et à la pose trouvée par Gauss-Newton (vert)."));

// ================================================================ 5. RESULTATS REELS
C.push(H1("5. Résultats sur les scans réels"));
C.push(H2("5.1 Pose de référence et incertitude"));
C.push(P("Pendant la capture du Jour 1, les positions du lidar **n'ont pas été mesurées** sur le robot (toutes les poses étaient à 0). La pose de référence de chaque scan est donc celle trouvée par l'**assemblage** du Jour 1 (recalage global puis ICP). C'est elle-même une estimation, ce qui limite la précision qu'on peut vérifier."));
C.push(P("Nous avons estimé son incertitude de deux façons :"));
C.push(B("**Approximation de Laplace** : autour de la pose de référence, la covariance vaut Σ = s² (JᵀWJ)⁻¹, où s² est la variance des distances entre le scan et la carte vectorielle construite sans lui. Résultat : σx ≈ 3,5 mm, σy ≈ 4,0 mm, σθ ≈ 0,08° (tableau A)."));
C.push(B("**Écart entre méthodes** (tableau B) : la médiane des erreurs de toutes les méthodes itératives reste de **1 à 3 cm** pour 7 scans sur 9. L'incertitude réelle des références est donc plutôt de l'ordre du **centimètre et de quelques dixièmes de degré**. L'approximation de Laplace est optimiste : elle suppose un bruit indépendant d'un point à l'autre et ignore les erreurs de l'assemblage lui-même et les objets déplacés entre scans."));
C.push(table(["Scan", "σx", "σy", "σθ"], D.incertitude.map((r) => r.map((c) => c.replace(".", ","))), [25, 25, 25, 25]));
C.push(legend("Tableau A — Incertitude des poses de référence (approximation de Laplace)."));
C.push(table(["Scan", "Grid map", "Carte vectorielle", "Scans (point-à-point)", "Scans (point-à-droite)"],
  D.par_scan.map((r) => r.map((c) => c.replace(".", ","))), [16, 21, 21, 21, 21]));
C.push(legend("Tableau B — Erreur de position médiane par rapport à la référence, sur toutes les méthodes itératives et toutes les poses initiales."));
C.push(P("Les **scans 7 et 9** s'écartent d'environ 5 cm de leur référence, avec **toutes** les méthodes et sur toutes les références. Quand toutes les méthodes s'accordent sur une pose différente de la référence, c'est la référence qui est probablement décalée, pas la localisation. Ces deux scans expliquent l'essentiel des « échecs » du réel. Le scan 9 est aussi celui dont l'incertitude de Laplace est la plus grande (6 mm, 0,17°)."));
C.push(note("Mesurer la pose du lidar au mètre ruban et au rapporteur donnerait une référence à environ **±2 cm et ±2°** près, donc moins précise que les méthodes testées. Une mesure au sol, par exemple avec des repères au scotch et un mètre laser, permettrait de vérifier les poses d'assemblage de façon indépendante. Ce serait utile lors d'une prochaine séance."));
C.push(H2("5.2 Comparaison des méthodes"));
C.push(P(`Niveau d'erreur initiale ${D.levels[2]}, ${D.n_cas["réel"]} essais par méthode :`));
C.push(comp("réel", ALL));
C.push(space());
C.push(P("La réussite est plus faible qu'en simulation (67 à 100 %), et la précision passe de quelques millimètres à **1,5 à 3 cm**. Plusieurs causes s'ajoutent : l'incertitude des références (section 5.1), les tables, chaises et personnes qui ont bougé d'un scan à l'autre, et des cartes construites avec un scan de moins. Les classements restent les mêmes : Gauss-Newton et ICP sont les plus rapides ; le filtre à particules est le plus fiable sur la carte vectorielle (100 %) ; la multi-résolution est la plus fiable entre scans (100 %)."));
C.push(P("Les **calculs directs** échouent presque toujours sur le réel. Par les murs : 11 % de réussite, 8 cm d'erreur, car les nombreux petits segments du mobilier perturbent les associations. Par les moments : 0 % et 67 cm d'erreur, car deux scans réels voisins ne voient jamais exactement la même chose."));
C.push(H2("5.3 Sensibilité à la pose initiale"));
C.push(sens("réel"));
C.push(space());
C.push(...img("sensibilite_reel.png", 640, "Figure 7 — Taux de réussite en fonction de l'erreur de la pose initiale (scans réels)."));
C.push(P("Sur le réel, les méthodes locales (Gauss-Newton, ICP) **décrochent au dernier niveau** (44 à 67 % à 50 cm / 20°) : avec du mobilier partout, le coût a de nombreux minima locaux, et un départ lointain tombe plus souvent dans l'un d'eux. La brute force chute à 28 % (vraie pose hors de sa fenêtre en angle). Seules la **multi-résolution** (83 à 89 %) et les **particules** (78 à 100 %) restent stables : elles explorent largement avant d'affiner."));
C.push(...img("exemples_reel.png", 640, "Figure 8 — Exemples sur les scans réels : pose initiale (rouge) et pose trouvée par Gauss-Newton (vert). Le scan se replace sur les murs de la salle."));

// ================================================================ 6. DISCUSSION
C.push(H1("6. Discussion"));
C.push(H2("6.1 Quelle méthode choisir ?"));
C.push(table(["Situation", "Méthode conseillée", "Raison"], [
  ["Pose initiale bonne (odométrie, < 20 cm / 10°)", "Gauss-Newton", "La plus rapide (< 10 ms) et la plus précise ; idéale en suivi continu"],
  ["Pose initiale médiocre (jusqu'à 50 cm / 20°)", "Multi-résolution ou particules", "Les seules stables au dernier niveau sur le réel"],
  ["Meilleure précision", "Multi-résolution ou particules, puis Gauss-Newton", "On combine la robustesse de la recherche et la précision du gradient"],
  ["Pose totalement inconnue", "Brute force sur 360° accélérée par FFT", "C'est ce que fait l'assemblage du Jour 1 (`register.match_global`)"],
], [33, 27, 40]));
C.push(H2("6.2 Comparaison des références"));
C.push(B("**Carte vectorielle** : la plus précise (distances exactes), la plus légère en mémoire, mais elle dépend de la qualité de l'extraction des segments. Les petits segments du mobilier gênent les calculs directs."));
C.push(B("**Grid map** : la plus simple et la plus robuste, car elle ne demande aucune extraction. Sa précision est limitée par la taille des cellules (5 cm)."));
C.push(B("**Entre scans** : aucune carte n'est nécessaire, ce qui en fait la brique de base de l'odométrie lidar et de l'assemblage. En revanche, les erreurs s'accumulent si l'on enchaîne les scans, et elle n'est valable que pour des scans proches."));
C.push(H2("6.3 Limites"));
C.push(B("Les références réelles viennent de l'assemblage, sans mesure indépendante : la précision réelle des méthodes ne peut pas être vérifiée en dessous des 1,5 à 3 cm observés."));
C.push(B("Les temps sont ceux d'un code Python + numpy ; une implémentation en C++ sur le robot serait 10 à 100 fois plus rapide, mais l'ordre entre les méthodes resterait le même."));
C.push(B("Le décalage le long d'un long mur est mal contraint (« bras » de la figure 2) : un couloir sans repère transversal resterait ambigu pour toutes les méthodes."));
C.push(B("Le résultat du filtre à particules dépend du tirage aléatoire (graine fixe ici, pour la reproductibilité)."));

// ================================================================ CONCLUSION
C.push(H1("Conclusion"));
C.push(P("Nous avons mis en œuvre la localisation par scan matching sur les **trois types de référence** demandés, avec **cinq méthodes communes** (brute force, multi-résolution, Gauss-Newton, ICP, filtre à particules) et **deux calculs directs**. Un banc d'évaluation automatique les compare dans les mêmes conditions."));
C.push(P("En simulation, les méthodes itératives retrouvent la pose à **quelques millimètres et moins de 0,3°** près, jusqu'à 50 cm et 20° d'erreur initiale. Sur les scans réels, la précision est de **1,5 à 3 cm**, de l'ordre de l'incertitude des poses de référence elles-mêmes. Les méthodes locales (Gauss-Newton, ICP) sont les plus rapides, mais elles ont besoin d'une pose initiale assez bonne. Les méthodes qui explorent (multi-résolution, particules) sont plus lentes et plus robustes. Les calculs directs, très rapides, ne suffisent pas seuls sur des scans réels."));
C.push(P("La suite logique est de combiner ces méthodes dans une boucle de **localisation continue** : particules ou multi-résolution pour s'initialiser, puis Gauss-Newton à chaque nouveau scan, à partir de la pose prédite par l'odométrie du robot."));

// ================================================================ ANNEXE
C.push(H1("Annexe — Commandes et tests"));
C.push(table(["Commande", "Effet"], [
  ["`python -m carto evaluer --reel data\\salle_2026-11-02_18h31`", "Évaluation complète, simulation + réel (environ 9 min), dans un nouveau dossier `resultats/localisation/version_N`"],
  ["`python -m carto evaluer --rapide`", "Essai rapide, avec moins de cas"],
  ["`python -m carto localiser <scan.csv> --ref <gridmap.npz | carte_vectorielle.txt | scan_ref.csv> --init x y θ`", "Localise un scan avec toutes les méthodes (ou `--methode Gauss-Newton`)"],
  ["`python -m pytest`", "Les 57 tests automatiques, dont 19 pour la localisation"],
], [55, 45]));
C.push(space());
C.push(P("Les résultats détaillés (une ligne par essai) sont dans `resultats/localisation/version_1/resultats.csv` (séparateur « ; », s'ouvre dans Excel), et la synthèse dans `synthese.md`."));

// ================================================================ DOCUMENT
const doc = new Document({
  creator: "Compte rendu TP cartographie", title: "Compte rendu TP Jour 2 — Localisation par scan matching",
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
      children: [new TextRun({ text: "TP Jour 2 — Localisation par scan matching", size: 16, color: "888888" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: ["Page ", PageNumber.CURRENT, " / ", PageNumber.TOTAL_PAGES], size: 16, color: "888888" })] })] }) },
    children: C,
  }],
});

const outFile = path.join(OUT_DIR, "compte_rendu_TP2_localisation_v1.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outFile, buf); console.log("->", outFile); });
