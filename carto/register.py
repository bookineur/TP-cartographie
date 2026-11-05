"""Assemblage de scans pris à des positions INCONNUES (recalage global).

Étapes (cours « Cartographie », §6 Fusion des données : « les mesures devront
être correctement superposées ») :

1. prétraitement de chaque scan (`clean_scan`) : distances hors plage, points
   isolés (aberrants). Remplace le filtre d'intensité quand l'intensité n'a pas
   été transmise (format Teleplot : x, y seulement) ;
2. recalage global d'un scan B sur un scan / une carte A (`match_global`) :
   pour chaque rotation θ (0..360°), on cherche la translation qui superpose le
   mieux les points de B sur un « champ de vraisemblance » de A (grille floutée).
   La recherche de translation se fait d'un coup par corrélation FFT : coût
   O(N² log N) par angle au lieu de O(N² × points). Puis affinage local fin ;
3. graphe des recouvrements : on recale toutes les paires, on garde pour chaque
   scan le meilleur voisin (arbre couvrant de recouvrement maximal) et on
   compose les poses depuis un scan de référence. Les scans sans recouvrement
   suffisant restent à part (signalés).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from carto.scan import Pose, Scan


# ------------------------------------------------------------------ prétraitement
def clean_scan(scan: Scan, min_range=0.10, max_range=10.0, radius=0.15, min_neighbors=2,
               min_intensity=None) -> Scan:
    """Supprime les points peu fiables :
      - distance 0 / trop proche (boîtier, câbles) / trop loin (précision faible) ;
      - intensité trop faible, si elle est disponible (> 0) ;
      - points isolés : moins de `min_neighbors` voisins à moins de `radius` m
        (reflets, poussières, mesures aberrantes)."""
    s = scan.filtered(min_range, max_range)
    if min_intensity is not None and np.any(s.intensities > 0):
        keep = s.intensities >= min_intensity
        s = Scan(s.name, s.angles[keep], s.ranges[keep], s.intensities[keep], dict(s.meta))
    p = s.local_xy()
    if len(p) > 2:
        d = np.hypot(*(p[:, None, :] - p[None, :, :]).transpose(2, 0, 1))
        keep = (d < radius).sum(axis=1) - 1 >= min_neighbors
        s = Scan(s.name, s.angles[keep], s.ranges[keep], s.intensities[keep], dict(s.meta))
    return s


def structural_points(scan: Scan, min_len=0.6, tol=0.06) -> np.ndarray:
    """Ne garde que les points situés sur des segments d'au moins `min_len` m
    (murs, grands meubles), dans le repère du lidar. Utile pour un lidar posé
    au sol : les pieds de chaises / tables (petits amas de points) sont ignorés
    pour le recalage, seuls les murs servent à superposer les scans."""
    from carto.segments import extract_segments
    pts = scan.local_xy()
    segs = [s for s in extract_segments(pts, split_thresh=0.08, gap=0.25, min_points=5) if s.length >= min_len]
    if not segs or len(pts) == 0:
        return np.empty((0, 2))
    keep = np.zeros(len(pts), bool)
    for s in segs:
        d, L = s.direction, s.length
        rel = pts - s.p1
        t = rel @ d
        lat = np.abs(d[0] * rel[:, 1] - d[1] * rel[:, 0])
        keep |= (lat <= tol) & (t >= -tol) & (t <= L + tol)
    return pts[keep]


# ------------------------------------------------------------- champ et corrélation
def _field(points: np.ndarray, res: float, margin: float):
    """Grille « champ de vraisemblance » : 1 sur les points, décroissance gaussienne autour."""
    lo = points.min(axis=0) - margin
    hi = points.max(axis=0) + margin
    shape = np.ceil((hi - lo) / res).astype(int)[::-1] + 1
    g = np.zeros(shape, float)
    c = np.floor((points - lo) / res).astype(int)
    g[c[:, 1], c[:, 0]] = 1.0
    # flou gaussien séparable (σ ≈ 1 cellule) par FFT 1D
    k = np.exp(-0.5 * (np.arange(-3, 4) / 1.0) ** 2)
    k /= k.max()
    g = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 0, g)
    g = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, g)
    return np.minimum(g, 1.0), lo


def _score_points(field, lo, res, pts):
    c = np.floor((pts - lo) / res).astype(int)
    H, W = field.shape
    ok = (c[:, 0] >= 0) & (c[:, 0] < W) & (c[:, 1] >= 0) & (c[:, 1] < H)
    return float(field[c[ok, 1], c[ok, 0]].sum()) / max(len(pts), 1)


@dataclass
class Match:
    pose: Pose          # pose de B dans le repère de A
    score: float        # moyenne du champ sous les points de B (0..1)
    overlap: float      # part des points de B à moins de 10 cm d'un point de A
    second: float       # 2e meilleur score à une pose différente (ambiguïté)


def overlap_points(a: np.ndarray, b: np.ndarray, tol=0.10) -> float:
    """Part des points de b à moins de `tol` d'un point de a (grille de hachage)."""
    if len(a) == 0 or len(b) == 0:
        return 0.0
    cells = {}
    for x, y in np.floor(a / tol).astype(int):
        cells[(x, y)] = True
    cb = np.floor(b / tol).astype(int)
    hit = 0
    for x, y in cb:
        if any((x + dx, y + dy) in cells for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
            hit += 1
    return hit / len(b)


_ANGLE_BATCH = 12  # angles traités ensemble (mémoire : 12 grilles à la fois)


def _fast_len(n: int) -> int:
    """Plus petite taille >= n de la forme 2^a·3^b·5^c (taille où la FFT est rapide)."""
    m = n
    while True:
        k = m
        for p in (2, 3, 5):
            while k % p == 0:
                k //= p
        if k == 1:
            return m
        m += 1


def match_global(a_pts: np.ndarray, b_local: np.ndarray, res=0.10, step_deg=2.0, max_pts=400) -> Match:
    """Pose de B (points dans son repère) qui superpose B sur A (points dans le repère de A)."""
    rng = np.random.default_rng(0)
    b = b_local if len(b_local) <= max_pts else b_local[rng.choice(len(b_local), max_pts, replace=False)]
    reach = np.abs(b).max() + 0.5
    field, lo = _field(a_pts, res, margin=reach)
    H, W = field.shape
    # grille complétée de zéros jusqu'à une taille rapide pour la FFT (produit de 2, 3, 5) :
    # le pic de corrélation est cherché dans la zone d'origine H x W, donc le résultat ne change pas
    Hf, Wf = _fast_len(H), _fast_len(W)
    padded = np.zeros((Hf, Wf))
    padded[:H, :W] = field
    F = np.fft.rfft2(padded)
    results = []
    thetas = np.radians(np.arange(0, 360, step_deg))
    for start in range(0, len(thetas), _ANGLE_BATCH):
        ths = thetas[start:start + _ANGLE_BATCH]
        # images de B tourné, une par angle, calculées et transformées ensemble
        imgs = np.zeros((len(ths), Hf, Wf))
        for n, th in enumerate(ths):
            c, s = np.cos(th), np.sin(th)
            rb = b @ np.array([[c, s], [-s, c]])
            # image de B centrée sur l'origine de la grille (indices modulo = translation circulaire)
            ci = np.round(rb / res).astype(int)
            np.add.at(imgs[n], (ci[:, 1] % Hf, ci[:, 0] % Wf), 1.0)
        corr = np.fft.irfft2(F * np.conj(np.fft.rfft2(imgs)), s=(Hf, Wf))[:, :H, :W]
        for n, th in enumerate(ths):
            k = int(np.argmax(corr[n]))
            iy, ix = divmod(k, W)
            results.append((corr[n].flat[k] / len(b), th, ix, iy))
    results.sort(key=lambda r: -r[0])
    best = results[0]
    # translation : un point de B à l'origine tombe dans la cellule (ix, iy) de la grille
    tx, ty = lo + (np.array([best[2], best[3]]) + 0.5) * res
    # 2e meilleur à un angle nettement différent (> 10°) : mesure d'ambiguïté
    second = next((r[0] for r in results[1:]
                   if abs((np.degrees(r[1] - best[1]) + 180) % 360 - 180) > 10), 0.0)
    pose = refine(a_pts, b_local, Pose(tx, ty, best[1]))
    world = pose.transform(b_local)
    fine_field, flo = _field(a_pts, 0.05, margin=reach)
    return Match(pose, _score_points(fine_field, flo, 0.05, world), overlap_points(a_pts, world), second)


def refine(a_pts, b_local, pose: Pose, iters=30) -> Pose:
    """Affinage ICP point-à-point (plus proche voisin + Procuste), avec rejet des
    appariements lointains : corrige les derniers cm / dixièmes de degré."""
    p = Pose(pose.x, pose.y, pose.theta)
    cells = {}
    for i, (x, y) in enumerate(np.floor(a_pts / 0.2).astype(int)):
        cells.setdefault((x, y), []).append(i)
    for it in range(iters):
        w = p.transform(b_local)
        src, dst = [], []
        max_d = 0.4 if it < 10 else 0.15
        for q, (x, y) in zip(w, np.floor(w / 0.2).astype(int)):
            cand = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cells.get((x + dx, y + dy), ())]
            if not cand:
                continue
            d = np.hypot(*(a_pts[cand] - q).T)
            j = int(np.argmin(d))
            if d[j] < max_d:
                src.append(q)
                dst.append(a_pts[cand[j]])
        if len(src) < 10:
            break
        src, dst = np.array(src), np.array(dst)
        ms, md = src.mean(0), dst.mean(0)
        Hm = (src - ms).T @ (dst - md)
        U, _, Vt = np.linalg.svd(Hm)
        R = Vt.T @ U.T
        if np.linalg.det(R) < 0:
            Vt[-1] *= -1
            R = Vt.T @ U.T
        dth = np.arctan2(R[1, 0], R[0, 0])
        t = md - R @ ms
        # composition : nouvelle pose = (R, t) ∘ ancienne
        nx, ny = R @ np.array([p.x, p.y]) + t
        p = Pose(float(nx), float(ny), float(p.theta + dth))
        if abs(dth) < 1e-5 and np.hypot(*t - (np.eye(2) - R) @ np.zeros(2)) < 1e-4:
            break
    return p


# --------------------------------------------------------------- assemblage complet
def _compose(a: Pose, b: Pose) -> Pose:
    """Pose b exprimée dans le repère a -> repère global (a ∘ b)."""
    c, s = np.cos(a.theta), np.sin(a.theta)
    return Pose(a.x + c * b.x - s * b.y, a.y + s * b.x + c * b.y, a.theta + b.theta)


def assemble(scans: list[Scan], min_overlap=0.45, log=print, points=None):
    """Recale toutes les paires, construit l'arbre de recouvrement maximal et
    renvoie (poses, groupes, matches). Le scan le plus relié de chaque groupe
    sert de référence (pose 0, 0, 0), placé en tête du groupe.
    `points` : nuages à utiliser pour le recalage (par défaut tous les points ;
    p. ex. `structural_points` pour ne recaler que sur les murs)."""
    n = len(scans)
    pts = points if points is not None else [s.local_xy() for s in scans]
    matches = {}
    for i in range(n):
        for j in range(n):
            if i != j:
                m = match_global(pts[i], pts[j])
                matches[(i, j)] = m
        log(f"  scan {i + 1} recalé contre les autres")
    # poids d'une arête = recouvrement symétrique (min des deux sens)
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            w = min(matches[(i, j)].overlap, matches[(j, i)].overlap)
            edges.append((w, i, j))
    edges.sort(reverse=True)
    # Kruskal (arbre couvrant maximal) sur les arêtes assez bonnes
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    tree = {i: [] for i in range(n)}
    for w, i, j in edges:
        if w < min_overlap:
            break
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj
            tree[i].append(j)
            tree[j].append(i)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    groups = sorted(groups.values(), key=len, reverse=True)
    poses = [None] * n
    for gi, g in enumerate(groups):
        # référence du groupe : le scan qui a le plus de voisins recalés (placé en tête du groupe)
        root = max(g, key=lambda k: (len(tree[k]), -k))
        groups[gi] = [root] + [k for k in g if k != root]
        poses[root] = Pose()
        stack = [root]
        while stack:
            i = stack.pop()
            for j in tree[i]:
                if poses[j] is None:
                    poses[j] = _compose(poses[i], matches[(i, j)].pose)
                    stack.append(j)
    return poses, groups, matches
