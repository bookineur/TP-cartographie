"""Construit les cartes d'une pièce à partir des scans d'une session Lidar Plot.

    python -m carto assemble data/salle_2026-11-02_18h31 --scans 1-9

Chaîne (document « Construction d'une carte vectorielle 2D », §2 à §6) :
  1. lecture des scans (coordonnées polaires du lidar) ;
  2. prétraitement : distances hors plage + points isolés (et intensité faible si
     elle a été transmise) ;
  3. assemblage : positions des scans retrouvées par recalage global (si elles
     n'ont pas été mesurées) -> coordonnées globales P = R(θ)·P_local + T ;
  4. grid map (carte d'occupation, log-odds, Bresenham) ;
  5. carte vectorielle (segments : clusterisation, split-and-merge, fusion) ;
  6. export : images, poses, segments (x1, y1, x2, y2), rapport.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from carto import theme
from carto.gridmap import build_grid
from carto.register import assemble, clean_scan, overlap_points, structural_points
from carto.scan import Pose, load_scan_file, save_poses, save_scan_csv
from carto.theme import C, SCAN_COLORS
from carto.vectormap import VectorMap


def parse_selection(text: str | None, available: list[int]) -> list[int]:
    """'1-9', '1,2,5-7' -> [1, 2, 5, 6, 7] ; None -> tout."""
    if not text:
        return available
    out = []
    for part in text.split(","):
        a, _, b = part.strip().partition("-")
        out += list(range(int(a), int(b) + 1)) if b else [int(a)]
    return [k for k in out if k in available]


def _wall_alignment(pairs) -> float:
    """Rotation (rad) qui rend les murs parallèles aux axes : moyenne circulaire de
    4·orientation des segments (période 90°), pondérée par la longueur."""
    from carto.segments import extract_segments
    segs = [sg for scan, pose in pairs for sg in extract_segments(scan.world_xy(pose)) if sg.length > 0.5]
    if not segs:
        return 0.0
    w = np.array([sg.length for sg in segs])
    phi = np.array([sg.orientation for sg in segs])
    a = np.arctan2((w * np.sin(4 * phi)).sum(), (w * np.cos(4 * phi)).sum()) / 4
    return float(-a)


def _fig(title):
    fig = Figure(figsize=(10, 9), dpi=140, facecolor="white")
    FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.set_title(title, loc="left", fontsize=12, weight="bold", color=C["text"])
    return fig, ax


def _save(fig, path: Path):
    """Enregistre ; si le fichier est verrouillé (ouvert dans une visionneuse), écrit
    à côté avec un suffixe plutôt que d'interrompre toute la construction."""
    try:
        fig.savefig(path)
        return path
    except OSError:
        alt = path.with_name(f"{path.stem}_{time.strftime('%H%M%S')}{path.suffix}")
        fig.savefig(alt)
        print(f"  ⚠ {path.name} est ouvert dans un autre programme : image écrite dans {alt.name}")
        return alt


def _finish(fig, ax, path):
    ax.set_aspect("equal")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    fig.tight_layout()
    _save(fig, path)


def next_version_dir(base: Path) -> Path:
    """base/version_N avec N = 1 + la plus grande version existante (rien n'est écrasé)."""
    nums = [int(p.name.split("_")[1]) for p in base.glob("version_*") if p.name.split("_")[1].isdigit()]
    return base / f"version_{max(nums, default=0) + 1}"


def build(session: Path, selection: str | None = None, out: Path | None = None, use_saved_poses=False,
          res=0.05, log=print, excluded: str | None = None, align_walls=True, max_range=10.0) -> dict:
    """`excluded` : scans volontairement écartés de la carte (ex. « 10-14 ») mais
    présentés dans le rapport (figure et explication).
    Sans `out`, chaque exécution écrit dans un NOUVEAU dossier <session>/carte/version_N :
    les versions précédentes sont conservées."""
    session = Path(session)
    files = {int(f.stem[4:]): f for f in session.glob("scan*.csv") if f.stem[4:].isdigit()}
    ex_ks = parse_selection(excluded, sorted(files)) if excluded else []
    ks = [k for k in parse_selection(selection, sorted(files)) if k not in ex_ks]
    out = Path(out) if out else next_version_dir(session / "carte")
    out.mkdir(parents=True, exist_ok=True)
    log(f"sortie : {out}")
    names = [f"scan{k}" for k in ks]
    n_used = len(ks)
    ks = ks + ex_ks  # les écartés sont lus et nettoyés (pour le rapport) mais pas assemblés
    names += [f"scan{k}" for k in ex_ks]

    # 1-2. lecture + prétraitement
    raw = [load_scan_file(files[k])[0] for k in ks]
    has_intensity = any(np.any(s.intensities > 0) for s in raw)
    clean = [clean_scan(s, max_range=max_range, min_intensity=50 if has_intensity else None) for s in raw]
    log(f"{len(ks)} scans, {sum(map(len, raw))} points -> {sum(map(len, clean))} après prétraitement")

    # 3. positions : mesurées (poses.json) ou retrouvées par recalage global
    saved = {}
    if use_saved_poses and (session / "poses.json").exists():
        saved = {k: Pose.from_list_deg(v) for k, v in json.loads((session / "poses.json").read_text("utf-8")).items()}
    if saved and all(n in saved for n in names[:n_used]):
        poses, groups = [saved[n] for n in names[:n_used]], [list(range(n_used))]
        log("positions : celles de poses.json")
    else:
        log("positions inconnues : recalage global de toutes les paires (peut prendre quelques minutes)…")
        t0 = time.time()
        poses, groups, _ = assemble(clean[:n_used], log=lambda m: None)
        log(f"  fait en {time.time() - t0:.0f} s")
    poses = list(poses) + [None] * len(ex_ks)
    if ex_ks:
        groups = groups + [[n_used + j] for j in range(len(ex_ks))]
    main = groups[0]
    placed = [i for i in main]
    # redressement : le repère vient du scan de référence, souvent un peu tourné.
    # On fait tourner toute la carte pour que les murs soient parallèles aux axes x / y.
    rot = _wall_alignment([(clean[i], poses[i]) for i in placed]) if align_walls else 0.0
    if rot:
        c, s = np.cos(rot), np.sin(rot)
        for i in placed:
            p = poses[i]
            poses[i] = Pose(c * p.x - s * p.y, s * p.x + c * p.y, p.theta + rot)
        log(f"carte redressée de {np.degrees(rot):+.1f}° (murs parallèles aux axes)")
    left_out = [names[i] for g in groups[1:] for i in g]
    if left_out:
        log(f"scans non rattachés (recouvrement insuffisant) : {', '.join(left_out)}")

    # qualité : recouvrement de chaque scan avec les AUTRES scans placés
    world = {i: clean[i].world_xy(poses[i]) for i in placed}
    consistency = {}
    for i in placed:
        others = np.vstack([world[j] for j in placed if j != i]) if len(placed) > 1 else world[i]
        consistency[names[i]] = overlap_points(others, world[i])

    # 4. grid map
    grid = build_grid([(clean[i], poses[i]) for i in placed], resolution=res)
    grid.save(out / "gridmap.npz")
    cls = grid.classify()

    # 5. carte vectorielle
    vm = VectorMap()
    for i in placed:
        vm.add_scan(clean[i], poses[i])
    vm.save_csv(out / "segments.csv")
    (out / "carte_vectorielle.txt").write_text(
        "# Carte vectorielle (segments) : x1,y1,x2,y2 en mètres\n"
        + "".join(f"{s.p1[0]:.3f},{s.p1[1]:.3f},{s.p2[0]:.3f},{s.p2[1]:.3f}\n" for s in vm.segments), "utf-8")

    # 6. images
    fig, ax = _fig(f"Assemblage — {len(placed)} scans superposés (une couleur par scan)")
    ax.grid(True, color="#E5E7EB")
    ax.set_axisbelow(True)
    for n, i in enumerate(placed):
        col = SCAN_COLORS[n % len(SCAN_COLORS)]
        ax.scatter(world[i][:, 0], world[i][:, 1], s=3, color=col, lw=0, label=names[i])
        p = poses[i]
        ax.plot([p.x, p.x + 0.4 * np.cos(p.theta)], [p.y, p.y + 0.4 * np.sin(p.theta)], color=col, lw=2.5)
        ax.plot(p.x, p.y, "o", ms=8, color=col, mec="white", mew=1.5)
        ax.text(p.x + 0.12, p.y + 0.12, str(ks[i]), fontsize=8, weight="bold", color=col)
    ax.legend(loc="upper right", fontsize=8, markerscale=4, ncol=2, framealpha=0.95)
    _finish(fig, ax, out / "1_assemblage.png")

    fig, ax = _fig(f"Grid map — cellules de {res * 100:.0f} cm (noir = occupé, blanc = libre, gris = inconnu)")
    ax.imshow(grid.probability(), cmap=theme.OCC_CMAP, origin="lower", vmin=0, vmax=1, extent=grid.extent,
              interpolation="nearest")
    for i in placed:
        ax.plot(poses[i].x, poses[i].y, "o", ms=6, color=C["pose"], mec="white")
    _finish(fig, ax, out / "2_grid_map.png")

    fig, ax = _fig(f"Carte vectorielle — {len(vm.segments)} segments (épaisseur = nb d'observations)")
    ax.grid(True, color="#E5E7EB")
    ax.set_axisbelow(True)
    allw = np.vstack([world[i] for i in placed])
    ax.scatter(allw[:, 0], allw[:, 1], s=1.5, color="#CBD5E1", lw=0)
    for sg in vm.segments:
        ax.plot([sg.p1[0], sg.p2[0]], [sg.p1[1], sg.p2[1]], "-", color=C["wall"],
                lw=1.0 + min(sg.n_obs, 5) * 0.5, solid_capstyle="round")
    for i in placed:
        ax.plot(poses[i].x, poses[i].y, "o", ms=6, color=C["pose"], mec="white")
    _finish(fig, ax, out / "3_carte_vectorielle.png")

    # part des points sur des structures longues (murs) : explique les scans écartés
    struct = {names[i]: len(structural_points(clean[i])) / max(len(clean[i]), 1) for i in range(len(ks))}
    left_idx = [i for g in groups[1:] for i in g]
    if left_idx:
        ref = main[0]
        cols = min(len(left_idx), 3) + 1
        fig = Figure(figsize=(5 * cols, 5.2), dpi=120, facecolor="white")
        FigureCanvasAgg(fig)
        for c_, i in enumerate([ref] + left_idx[:3]):
            ax = fig.add_subplot(1, cols, c_ + 1)
            a, sp = clean[i].local_xy(), structural_points(clean[i])
            ax.scatter(a[:, 0], a[:, 1], s=2, color="#94A3B8", lw=0, label="autres points")
            ax.scatter(sp[:, 0], sp[:, 1], s=3, color=C["error"], lw=0, label="structures longues (murs)")
            ax.plot(0, 0, ">", ms=9, color=C["pose"])
            kind = "utilisé" if i == ref else "écarté"
            ax.set_title(f"{names[i]} ({kind}) : {struct[names[i]]:.0%} de points sur des murs", fontsize=10)
            ax.set_aspect("equal")
            ax.grid(True, color="#E5E7EB")
            if c_ == 0:
                ax.legend(fontsize=8, markerscale=4, loc="upper right")
        fig.tight_layout()
        _save(fig, out / "4_scans_ecartes.png")

    # session assemblée, ouvrable dans Lidar Plot (« Ouvrir… ») et avec python -m carto view
    sess = out / "session_assemblee"
    sess.mkdir(exist_ok=True)
    for i in placed:
        s = raw[i]
        save_scan_csv(sess / f"{names[i]}.csv", np.degrees(s.angles), s.ranges * 1000, s.intensities,
                      meta={"heure": s.meta.get("heure", ""), "source": s.meta.get("source", "")})
    save_poses(sess / "poses.json", {names[i]: poses[i] for i in placed})
    save_poses(out / "poses_assemblees.json", {names[i]: poses[i] for i in placed})

    info = {"scans": names, "placed": [names[i] for i in placed], "left_out": left_out,
            "poses": {names[i]: poses[i].as_list_deg() for i in placed}, "consistency": consistency,
            "points_raw": int(sum(map(len, raw))), "points_clean": int(sum(map(len, clean))),
            "has_intensity": bool(has_intensity), "grid_shape": grid.shape, "res": res,
            "occ_m2": float((cls == 1).sum() * res ** 2), "free_m2": float((cls == 0).sum() * res ** 2),
            "segments": len(vm.segments), "confirmed": len(vm.confirmed(2)),
            "wall_length": float(sum(s.length for s in vm.segments)), "structure": struct}
    (out / "rapport_carte.md").write_text(_report(info, raw, clean, names), "utf-8")
    log(f"-> {out}")
    return info


def _report(info, raw, clean, names) -> str:
    L = ["# Cartographie de la pièce — grid map et carte vectorielle", "",
         f"Généré le {time.strftime('%d/%m/%Y %H:%M')}.", "",
         "## 1. Données", "",
         f"Scans utilisés : {', '.join(info['placed'])}. "
         + (f"Scans écartés : {', '.join(info['left_out'])} (aucun recouvrement fiable avec la pièce)."
            if info["left_out"] else ""), "",
         "Chaque scan est un tour du LD06 : environ 450 points (angle, distance) à 10 tr/s, plus "
         "de 1 000 points quand le lidar tourne plus lentement. Les scans ont été reçus au format "
         "Teleplot (`printScanTeleplot`), qui transmet x et y mais **pas l'intensité**.", "",
         "## 2. Prétraitement (§2 du document)", "",
         "- points à moins de 10 cm (boîtier, câbles) ou à plus de 10 m (précision dégradée) supprimés ;",
         "- points **isolés** supprimés (moins de 2 voisins à moins de 15 cm) : reflets, poussières, "
         "mesures aberrantes ;",
         ("- intensité < 50 supprimée." if info["has_intensity"] else
          "- **filtrage par intensité impossible ici** : l'intensité n'est pas transmise par le format "
          "Teleplot. Pour l'appliquer, il faut l'activer sur le robot "
          "(`ld06.enableFiltering(); ld06.setIntensityThreshold(seuil);`) ou envoyer les scans en CSV "
          "(`printScanCSV`), qui contient l'intensité."), "",
         f"Bilan : {info['points_raw']} points bruts → {info['points_clean']} points conservés.", "",
         "| scan | points bruts | conservés | sur des murs (segments ≥ 60 cm) | utilisé |", "|---|---|---|---|---|"]
    L += [f"| {n} | {len(r)} | {len(c)} | {info['structure'][n]:.0%} | {'oui' if n in info['placed'] else 'non'} |"
          for n, r, c in zip(names, raw, clean)]
    L += ["", "## 3. Assemblage des scans (superposition dans un repère commun)", "",
          "Les positions du robot n'ayant pas été mesurées, elles ont été retrouvées par **recalage** :",
          "",
          "1. pour chaque paire de scans (A, B) et chaque rotation θ de 0 à 360° (pas de 2°), la "
          "translation qui superpose le mieux B sur A est cherchée par corrélation (FFT) entre les "
          "points de B et une grille floutée des points de A ;",
          "2. la meilleure pose est affinée par **ICP** (Iterative Closest Point, cité dans le cours "
          "pour la détection de boucle) ;",
          "3. le **recouvrement** (part des points de B à moins de 10 cm d'un point de A) mesure la "
          "qualité ; on garde les meilleures liaisons (arbre couvrant de recouvrement maximal) et on "
          "compose les poses depuis un scan de référence (pose 0, 0, 0).", "",
          "Formule appliquée à chaque point : P_global = R(θ)·P_local + T(x, y).", "",
          "| scan | x (m) | y (m) | θ (°) | recouvrement avec les autres scans |", "|---|---|---|---|---|"]
    for n in info["placed"]:
        x, y, t = info["poses"][n]
        L.append(f"| {n} | {x:.2f} | {y:.2f} | {((t + 180) % 360) - 180:.1f} | {info['consistency'][n]:.0%} |")
    L += ["", "![assemblage](1_assemblage.png)", "",
          "## 4. Grid map (carte d'occupation)", "",
          f"Cellules de {info['res'] * 100:.0f} cm, log-odds : chaque rayon (Bresenham) rend libres les "
          "cellules traversées et occupée la cellule d'impact.", "",
          f"- surface libre : {info['free_m2']:.1f} m², occupée : {info['occ_m2']:.1f} m²", "",
          "![grid map](2_grid_map.png)", "",
          "## 5. Carte vectorielle (§3 et §4 du document)", "",
          "- **segmentation** : rupture de cluster quand deux points successifs sont à plus de 20 cm ;",
          "- **reconnaissance géométrique** : simplification polygonale (Douglas-Peucker, seuil 10 cm), "
          "puis droite des moindres carrés totaux sur chaque morceau ;",
          "- **mise à jour** : un segment proche d'un segment existant (angle < 8°, écart latéral "
          "< 8 cm, trou < 20 cm) est **fusionné**, sinon **ajouté** ; chaque segment compte ses "
          "observations (confiance) ;",
          "- **nettoyage** : segments de moins de 15 cm supprimés.", "",
          f"Résultat : {info['segments']} segments, dont {info['confirmed']} vus au moins 2 fois, "
          f"{info['wall_length']:.1f} m de murs.", "",
          "![carte vectorielle](3_carte_vectorielle.png)", "",
          "Fichier `carte_vectorielle.txt` : une ligne `x1,y1,x2,y2` par segment (format du document).", "",
          ]
    if info["left_out"]:
        L += ["## 6. Scans écartés", "",
              f"Les scans {', '.join(info['left_out'])} n'ont pas pu être rattachés de façon fiable. Ils "
              "contiennent surtout de **petits amas de points** (pieds de chaises, de tables, objets bas, "
              "personnes) et **peu de structures longues** (murs) : le recalage n'a presque rien de "
              "commun et de stable à superposer. Une seule ligne droite commune ne suffit pas non plus : "
              "le scan peut « glisser » le long d'elle.", "",
              "C'est typiquement le cas d'un lidar **posé au sol** : un lidar 2D ne voit que dans "
              "**un seul plan** (cours, §5), et à quelques centimètres du sol ce plan coupe surtout des "
              "pieds de meubles. Placé plus haut (sur une table, sur le robot), il voit les murs et les "
              "plateaux. Les personnes qui se déplacent pendant la capture ajoutent des points différents "
              "d'un scan à l'autre (objets mobiles, §5 du document).", "",
              "![scans écartés](4_scans_ecartes.png)", ""]
    L += ["## 7. Limites", "",
          "- pas d'intensité : les reflets et surfaces sombres ne peuvent pas être filtrés par qualité ;",
          "- les positions sont estimées par recalage : une pièce très symétrique ou très encombrée "
          "peut donner un recalage faux (c'est pourquoi certains scans ont été écartés) ;",
          "- le lidar voit dans un seul plan (hauteur du capteur) : tables, chaises et pieds de meubles "
          "apparaissent comme des points ou de petits segments ;",
          "- objets mobiles (personnes) : vus dans un seul scan, ils donnent des segments à 1 observation.",
          ""]
    return "\n".join(L)
