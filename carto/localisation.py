"""Localisation par scan matching (TP Jour 2).

On cherche la pose (x, y, θ) du robot qui superpose le mieux un scan sur une
RÉFÉRENCE. Trois types de référence (document « Scan matching ») :

  GridRef    grid map : distance de chaque point à la cellule occupée la plus
             proche, lue dans un « champ de distance » calculé une fois sur la
             grille (interpolation bilinéaire -> valeur ET gradient) ;
  VectorRef  carte vectorielle : distance exacte point -> segment le plus proche ;
  CloudRef   scan de référence : distance au point le plus proche (point-à-point)
             ou à la droite locale du scan de référence (point-à-droite).

Toutes les références offrent la même opération `query(points)` -> distance d
et direction g (vecteur unitaire qui éloigne le point de la référence), ce qui
permet d'écrire chaque méthode de recherche UNE fois pour les trois :

  brute_force     recherche exhaustive sur une fenêtre (x, y, θ) autour de la
                  pose initiale ;
  multi_resolution  même recherche, d'abord à pas grossier avec un score
                  « flou » (σ large), puis de plus en plus fine autour du
                  meilleur résultat ;
  gauss_newton    descente de gradient (Gauss-Newton amorti, type
                  Levenberg-Marquardt) sur la somme des distances au carré,
                  avec pondération robuste (points aberrants ignorés) ;
  icp             ICP : à chaque itération, appariement au point le plus proche
                  puis calcul DIRECT de la meilleure rotation + translation
                  (SVD, problème de Procuste) ;
  particules      méthode probabiliste : nuage de poses tirées autour de la
                  pose initiale, pondérées par la vraisemblance du scan,
                  rééchantillonnées en resserrant le bruit (filtre particulaire) ;
  direct_murs     calcul direct sur carte vectorielle : θ par l'orientation des
                  murs (modulo 90°), puis translation par moindres carrés
                  linéaires point -> droite ;
  direct_moments  calcul direct entre scans : moments géométriques (centre de
                  gravité + axe principal d'inertie des deux nuages).

Pose : p_carte = R(θ) p_lidar + (x, y)  (même convention que carto.scan.Pose).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from carto.gridmap import OccupancyGrid
from carto.scan import Pose
from carto.segments import Segment

D_MAX = 1.0       # distance renvoyée hors de la zone couverte par la référence (m)
SIGMA = 0.05      # écart-type du score de vraisemblance (m), ~ précision du LD06 + cellule


# ======================================================================= outils
def _rot(th):
    c, s = np.cos(th), np.sin(th)
    return np.array([[c, -s], [s, c]])


def _transform_many(local: np.ndarray, poses: np.ndarray) -> np.ndarray:
    """local (N, 2), poses (P, 3) -> points carte (P, N, 2)."""
    c, s = np.cos(poses[:, 2])[:, None], np.sin(poses[:, 2])[:, None]
    x = c * local[None, :, 0] - s * local[None, :, 1] + poses[:, 0:1]
    y = s * local[None, :, 0] + c * local[None, :, 1] + poses[:, 1:2]
    return np.stack([x, y], axis=-1)


def _subsample(local: np.ndarray, n: int) -> np.ndarray:
    """1 point sur k (déterministe) pour garder la recherche rapide."""
    if len(local) <= n:
        return local
    return local[np.linspace(0, len(local) - 1, n).astype(int)]


def wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def _nearest_index_field(lo, shape, res, dist_to_all, chunk=4000):
    """Pour chaque cellule d'une grille fine, indice de la primitive la plus
    proche (point ou segment). `dist_to_all(pts)` -> distances (n, M)."""
    H, W = shape
    iy, ix = np.mgrid[0:H, 0:W]
    centres = lo + (np.column_stack([ix.ravel(), iy.ravel()]) + 0.5) * res
    idx = np.empty(len(centres), np.int32)
    for k in range(0, len(centres), chunk):
        idx[k:k + chunk] = np.argmin(dist_to_all(centres[k:k + chunk]), axis=1)
    return idx.reshape(H, W)


# ================================================================== références
class Reference:
    """Interface commune : query(pts (N, 2)) -> (d (N,), g (N, 2))."""
    kind = "?"

    def query(self, pts):
        raise NotImplementedError

    def distance(self, pts):
        return self.query(pts)[0]

    def score_many(self, local, poses, sigma=SIGMA, chunk=2000):
        """Vraisemblance moyenne exp(-d²/2σ²) pour un lot de poses (P, 3)."""
        out = np.empty(len(poses))
        for k in range(0, len(poses), chunk):
            w = _transform_many(local, poses[k:k + chunk])
            d = self.distance(w.reshape(-1, 2)).reshape(w.shape[:2])
            out[k:k + chunk] = np.exp(-0.5 * (d / sigma) ** 2).mean(axis=1)
        return out


class _IndexedRef(Reference):
    """Référence faite de primitives (points ou segments) : un champ « indice de
    la primitive la plus proche » sur une grille fine sert d'index spatial, puis
    la distance est calculée EXACTEMENT à cette primitive."""

    def _build_index(self, bbox_lo, bbox_hi, res, margin=1.0):
        self.res = res
        self.lo = np.asarray(bbox_lo, float) - margin
        hi = np.asarray(bbox_hi, float) + margin
        W, H = np.ceil((hi - self.lo) / res).astype(int)
        self.index = _nearest_index_field(self.lo, (H, W), res, self._dist_all)

    def _lookup(self, pts):
        c = np.floor((pts - self.lo) / self.res).astype(int)
        H, W = self.index.shape
        ok = (c[:, 0] >= 0) & (c[:, 0] < W) & (c[:, 1] >= 0) & (c[:, 1] < H)
        j = np.zeros(len(pts), np.int32)
        j[ok] = self.index[c[ok, 1], c[ok, 0]]
        return j, ok


class GridRef(Reference):
    """Grid map : champ de distance aux cellules occupées (p > 0,65), calculé
    une fois ; lecture par interpolation bilinéaire, qui donne aussi le
    gradient (utile pour Gauss-Newton)."""
    kind = "grid map"

    def __init__(self, grid: OccupancyGrid, occ_thresh=0.65):
        self.grid = grid
        occ = grid.probability() > occ_thresh
        oy, ox = np.nonzero(occ)
        if len(ox) == 0:
            raise ValueError("grid map sans cellule occupée")
        self.res, self.origin = grid.res, np.asarray(grid.origin, float)
        occ_xy = self.origin + (np.column_stack([ox, oy]) + 0.5) * self.res
        H, W = occ.shape
        iy, ix = np.mgrid[0:H, 0:W]
        centres = self.origin + (np.column_stack([ix.ravel(), iy.ravel()]) + 0.5) * self.res
        D = np.empty(len(centres))
        for k in range(0, len(centres), 4000):  # distance exacte au centre occupé le plus proche
            diff = centres[k:k + 4000, None, :] - occ_xy[None, :, :]
            D[k:k + 4000] = np.sqrt((diff ** 2).sum(-1).min(axis=1))
        self.D = np.minimum(D.reshape(H, W), D_MAX)
        self.occ_xy = occ_xy

    def query(self, pts):
        # coordonnées continues dans la grille des CENTRES de cellules
        u = (pts - self.origin) / self.res - 0.5
        H, W = self.D.shape
        i0 = np.floor(u).astype(int)
        ok = (i0[:, 0] >= 0) & (i0[:, 0] < W - 1) & (i0[:, 1] >= 0) & (i0[:, 1] < H - 1)
        d = np.full(len(pts), D_MAX)
        g = np.zeros((len(pts), 2))
        if ok.any():
            x0, y0 = i0[ok, 0], i0[ok, 1]
            fx, fy = u[ok, 0] - x0, u[ok, 1] - y0
            d00, d10 = self.D[y0, x0], self.D[y0, x0 + 1]
            d01, d11 = self.D[y0 + 1, x0], self.D[y0 + 1, x0 + 1]
            d[ok] = (d00 * (1 - fx) * (1 - fy) + d10 * fx * (1 - fy) + d01 * (1 - fx) * fy + d11 * fx * fy)
            gx = ((d10 - d00) * (1 - fy) + (d11 - d01) * fy) / self.res
            gy = ((d01 - d00) * (1 - fx) + (d11 - d10) * fx) / self.res
            n = np.hypot(gx, gy)
            g[ok] = np.column_stack([gx, gy]) / np.where(n > 1e-9, n, 1)[:, None]
        return d, g


class VectorRef(_IndexedRef):
    """Carte vectorielle : distance exacte au segment le plus proche."""
    kind = "carte vectorielle"

    def __init__(self, segments: list[Segment], index_res=0.02):
        if not segments:
            raise ValueError("carte vectorielle vide")
        self.segments = segments
        self.A = np.array([s.p1 for s in segments], float)
        self.B = np.array([s.p2 for s in segments], float)
        allp = np.vstack([self.A, self.B])
        self._build_index(allp.min(0), allp.max(0), index_res)

    def _closest(self, pts, A, B):
        ab = B - A
        L2 = np.maximum((ab ** 2).sum(-1), 1e-12)
        t = np.clip(((pts - A) * ab).sum(-1) / L2, 0, 1)
        return A + t[..., None] * ab

    def _dist_all(self, pts):
        q = self._closest(pts[:, None, :], self.A[None], self.B[None])
        return np.hypot(*(pts[:, None, :] - q).transpose(2, 0, 1))

    def query(self, pts):
        j, ok = self._lookup(pts)
        q = self._closest(pts, self.A[j], self.B[j])
        v = pts - q
        d = np.hypot(v[:, 0], v[:, 1])
        g = v / np.maximum(d, 1e-9)[:, None]
        d = np.where(ok, np.minimum(d, D_MAX), D_MAX)
        g[~ok] = 0
        return d, g


class CloudRef(_IndexedRef):
    """Scan de référence (nuage de points, repère carte). `point_to_line` :
    distance à la droite locale (normale estimée sur les voisins) au lieu du
    point le plus proche — converge mieux le long des murs."""
    kind = "scan de référence"

    def __init__(self, points: np.ndarray, point_to_line=False, index_res=0.02, k=6):
        self.P = np.asarray(points, float)
        if len(self.P) < 10:
            raise ValueError("scan de référence trop petit")
        self.point_to_line = point_to_line
        self._build_index(self.P.min(0), self.P.max(0), index_res)
        # normales : axe de plus petite variance des k voisins (ACP locale)
        d2 = ((self.P[:, None, :] - self.P[None, :, :]) ** 2).sum(-1)
        nb = np.argsort(d2, axis=1)[:, :k]
        self.N = np.zeros_like(self.P)
        for i, idx in enumerate(nb):
            q = self.P[idx] - self.P[idx].mean(0)
            self.N[i] = np.linalg.eigh(q.T @ q)[1][:, 0]

    def _dist_all(self, pts):
        return ((pts[:, None, :] - self.P[None, :, :]) ** 2).sum(-1)

    def query(self, pts):
        j, ok = self._lookup(pts)
        v = pts - self.P[j]
        if self.point_to_line:
            r = (v * self.N[j]).sum(-1)
            d, g = np.abs(r), self.N[j] * np.sign(r)[:, None]
        else:
            d = np.hypot(v[:, 0], v[:, 1])
            g = v / np.maximum(d, 1e-9)[:, None]
        d = np.where(ok, np.minimum(d, D_MAX), D_MAX)
        g[~ok] = 0
        return d, g


# ==================================================================== résultat
@dataclass
class Result:
    pose: Pose
    score: float              # vraisemblance moyenne finale (0..1)
    time_s: float
    method: str
    n_eval: int = 0           # nombre de poses évaluées (coût)
    info: dict = field(default_factory=dict)


def _finish(ref, local, pose_arr, t0, method, n_eval, **info):
    p = Pose(float(pose_arr[0]), float(pose_arr[1]), float(wrap(pose_arr[2])))
    sc = float(ref.score_many(local, np.array([[p.x, p.y, p.theta]]))[0])
    return Result(p, sc, time.perf_counter() - t0, method, n_eval, info)


# ==================================================================== méthodes
def _grid_search(ref, local, centre, half_xy, half_th, step_xy, step_th, sigma):
    r = np.arange(-half_xy, half_xy + 1e-9, step_xy)
    a = np.arange(-half_th, half_th + 1e-9, step_th)
    X, Y, T = np.meshgrid(centre[0] + r, centre[1] + r, centre[2] + a, indexing="ij")
    poses = np.column_stack([X.ravel(), Y.ravel(), T.ravel()])
    sc = ref.score_many(local, poses, sigma)
    return poses[int(np.argmax(sc))], len(poses)


def brute_force(ref, local, init: Pose, half_xy=0.5, half_th_deg=15.0, step_xy=0.04, step_th_deg=1.5,
                max_pts=150) -> Result:
    """Recherche exhaustive : toutes les poses d'une grille (x, y, θ) autour de
    la pose initiale. Précision limitée par le pas (± pas/2)."""
    t0 = time.perf_counter()
    sub = _subsample(local, max_pts)
    best, n = _grid_search(ref, sub, [init.x, init.y, init.theta], half_xy, np.radians(half_th_deg),
                           step_xy, np.radians(step_th_deg), max(SIGMA, step_xy))
    return _finish(ref, local, best, t0, "brute force", n)


# pas (m, °) et σ du score à chaque niveau : grossier/flou -> fin/net
LEVELS = [(0.10, 4.0, 0.15), (0.03, 1.0, 0.05), (0.01, 0.25, 0.03)]


def multi_resolution(ref, local, init: Pose, half_xy=0.5, half_th_deg=15.0, levels=LEVELS,
                     max_pts=150) -> Result:
    """Recherche exhaustive grossière sur toute la fenêtre avec un score flou
    (σ large : le bassin d'attraction est large), puis recherches de plus en
    plus fines autour du meilleur résultat (fenêtre = 2 pas du niveau précédent)."""
    t0 = time.perf_counter()
    sub = _subsample(local, max_pts)
    best = np.array([init.x, init.y, init.theta])
    hx, ht, n = half_xy, np.radians(half_th_deg), 0
    for step_xy, step_th, sigma in levels:
        best, k = _grid_search(ref, sub, best, hx, ht, step_xy, np.radians(step_th), sigma)
        n += k
        hx, ht = 2 * step_xy, np.radians(2 * step_th)
    return _finish(ref, local, best, t0, "multi-résolution", n)


def _robust_weights(d, scale):
    """Poids de Cauchy : ~1 pour d << scale, -> 0 pour les points aberrants
    (porte ouverte, personne, zone absente de la référence)."""
    return 1.0 / (1.0 + (d / scale) ** 2)


def gauss_newton(ref, local, init: Pose, iters=40, scale0=0.30, scale_min=0.05, lam0=1e-3) -> Result:
    """Descente de gradient de type Gauss-Newton amorti (Levenberg-Marquardt) sur
    E(x, y, θ) = Σ w_i d_i², où d_i = distance du point i à la référence.
    Jacobien d'un point : ∂d/∂(x, y, θ) = g · [1, 0, -(p_y - y) ; 0, 1, p_x - x]
    (g = direction de la distance). L'échelle robuste diminue au fil des
    itérations : on attire d'abord de loin, puis on ne garde que les bons points."""
    t0 = time.perf_counter()
    x = np.array([init.x, init.y, init.theta], float)
    lam, scale = lam0, scale0
    cost_of = lambda d, s: float((_robust_weights(d, s) * d ** 2).sum())
    for it in range(iters):
        p = Pose(*x).transform(local)
        d, g = ref.query(p)
        w = _robust_weights(d, scale) * (d < D_MAX)
        J = np.column_stack([g[:, 0], g[:, 1], -g[:, 0] * (p[:, 1] - x[1]) + g[:, 1] * (p[:, 0] - x[0])])
        Hm = (J * w[:, None]).T @ J
        b = (J * w[:, None]).T @ d
        cost = cost_of(d, scale)
        for _ in range(8):  # amortissement : on refuse un pas qui augmente le coût
            dx = -np.linalg.solve(Hm + lam * np.diag(np.diag(Hm) + 1e-9), b)
            xn = x + dx
            dn = ref.distance(Pose(*xn).transform(local))
            if cost_of(dn, scale) <= cost:
                x, lam = xn, max(lam / 3, 1e-7)
                break
            lam *= 4
        else:
            dx = np.zeros(3)
        scale = max(scale * 0.8, scale_min)
        if np.hypot(dx[0], dx[1]) < 1e-5 and abs(dx[2]) < 1e-6 and scale == scale_min:
            break
    return _finish(ref, local, x, t0, "Gauss-Newton", it + 1)


def icp(ref, local, init: Pose, iters=60, max_d0=0.5, max_d_min=0.10) -> Result:
    """ICP : point le plus proche de la référence (q = p - d·g), puis rotation +
    translation calculées DIRECTEMENT (SVD) ; on recommence jusqu'à convergence.
    Les appariements plus lointains que max_d sont rejetés ; le seuil suit
    l'erreur (3 x la distance médiane), pour ne pas rejeter trop tôt les points
    encore loin de leur mur."""
    t0 = time.perf_counter()
    x = np.array([init.x, init.y, init.theta], float)
    max_d = max_d0
    for it in range(iters):
        p = Pose(*x).transform(local)
        d, g = ref.query(p)
        keep = d < max_d
        if keep.sum() < 10:
            break
        src, dst = p[keep], p[keep] - d[keep, None] * g[keep]
        ms, md = src.mean(0), dst.mean(0)
        U, _, Vt = np.linalg.svd((src - ms).T @ (dst - md))
        R = Vt.T @ U.T
        if np.linalg.det(R) < 0:
            Vt[-1] *= -1
            R = Vt.T @ U.T
        dth = np.arctan2(R[1, 0], R[0, 0])
        t = md - R @ ms
        x = np.array([*(R @ x[:2] + t), x[2] + dth])
        max_d = float(np.clip(3 * np.median(d[keep]), max_d_min, max_d0))
        if abs(dth) < 1e-6 and np.hypot(*(R @ ms + t - ms)) < 1e-5:
            break
    return _finish(ref, local, x, t0, "ICP", it + 1)


def particles(ref, local, init: Pose, n=400, iters=15, sigma0=(0.25, 0.25, 8.0), shrink=0.75, seed=0,
              max_pts=150) -> Result:
    """Méthode probabiliste (filtre particulaire « statique ») : n poses tirées
    autour de la pose initiale ; poids = vraisemblance du scan ; on
    rééchantillonne selon les poids, on ajoute un bruit qui diminue à chaque
    itération ; résultat = moyenne pondérée des meilleures particules."""
    t0 = time.perf_counter()
    rng = np.random.default_rng(seed)
    sub = _subsample(local, max_pts)
    s = np.array([sigma0[0], sigma0[1], np.radians(sigma0[2])])
    P = np.array([init.x, init.y, init.theta]) + rng.normal(0, 1, (n, 3)) * s
    for it in range(iters):
        sigma = max(SIGMA, 2 * s[0] / 3)  # score plus flou tant que le nuage est large
        sc = ref.score_many(sub, P, sigma)
        w = np.exp((sc - sc.max()) * 40)   # « température » : accentue les meilleures
        w /= w.sum()
        P = P[rng.choice(n, n, p=w)]
        s = np.maximum(s * shrink, [0.003, 0.003, np.radians(0.1)])
        P = P + rng.normal(0, 1, (n, 3)) * s
    sc = ref.score_many(sub, P)
    top = np.argsort(sc)[-n // 10:]
    best = P[top].mean(0)
    best[2] = np.arctan2(np.sin(P[top, 2]).mean(), np.cos(P[top, 2]).mean())
    return _finish(ref, local, best, t0, "particules", n * (iters + 1))


def _wall_angle(segs) -> float | None:
    """Orientation dominante modulo 90° (moyenne circulaire de 4φ pondérée par la longueur)."""
    segs = [s for s in segs if s.length >= 0.5]
    if not segs:
        return None
    w = np.array([s.length for s in segs])
    phi = np.array([s.orientation for s in segs])
    return float(np.arctan2((w * np.sin(4 * phi)).sum(), (w * np.cos(4 * phi)).sum()) / 4)


def direct_murs(ref: VectorRef, local, init: Pose) -> Result:
    """Calcul direct sur carte vectorielle (sans itération) :
    1) θ : orientation des murs du scan comparée à celle des murs de la carte
       (modulo 90°, on prend la solution la plus proche de θ initial) ;
    2) (x, y) : avec θ fixé, la distance point -> droite est LINÉAIRE en (x, y) :
       une seule résolution des moindres carrés, segments associés à la pose
       initiale corrigée en θ."""
    from carto.segments import extract_segments
    t0 = time.perf_counter()
    a_scan = _wall_angle(extract_segments(local))
    a_map = _wall_angle(ref.segments)
    th = init.theta
    if a_scan is not None and a_map is not None:
        corr = wrap(4 * (a_map - (a_scan + init.theta))) / 4  # écart modulo 90°, dans [-45°, 45°]
        th = init.theta + corr
    x = np.array([init.x, init.y, th])
    p = Pose(*x).transform(local)
    d, g = ref.query(p)
    keep = d < 0.5
    if keep.sum() >= 10:
        # d_i(x+δ) ≈ d_i + g_i·δ, exact pour une droite : on résout g δ = -d
        G, r = g[keep], d[keep]
        w = _robust_weights(r, 0.15)
        delta = np.linalg.lstsq(G * w[:, None], -r * w, rcond=None)[0]
        x[:2] += delta
    return _finish(ref, local, x, t0, "direct (murs)", 1)


def direct_moments(ref: CloudRef, local, init: Pose) -> Result:
    """Calcul direct entre scans par moments géométriques : on aligne le centre
    de gravité et l'axe principal d'inertie (moments d'ordre 1 et 2) du scan
    sur ceux du scan de référence. Exact si les deux scans voient la même
    chose, faussé dès qu'une zone n'est vue que par l'un des deux."""
    t0 = time.perf_counter()

    def moments(P):
        c = P.mean(0)
        q = P - c
        cov = q.T @ q / len(P)
        return c, 0.5 * np.arctan2(2 * cov[0, 1], cov[0, 0] - cov[1, 1])

    c_ref, a_ref = moments(ref.P)
    c_loc, a_loc = moments(local)
    th = a_ref - a_loc
    # l'axe d'inertie est défini à 180° près : solution la plus proche de θ initial
    th = init.theta + wrap(2 * (th - init.theta)) / 2
    t = c_ref - _rot(th) @ c_loc
    return _finish(ref, local, np.array([t[0], t[1], th]), t0, "direct (moments)", 1)


METHODS = {
    "brute force": brute_force,
    "multi-résolution": multi_resolution,
    "Gauss-Newton": gauss_newton,
    "ICP": icp,
    "particules": particles,
}


def methods_for(ref) -> dict:
    m = dict(METHODS)
    if isinstance(ref, VectorRef):
        m["direct (murs)"] = direct_murs
    if isinstance(ref, CloudRef):
        m["direct (moments)"] = direct_moments
    return m


def localise(ref, local, init: Pose, method="multi-résolution", **kw) -> Result:
    return methods_for(ref)[method](ref, local, init, **kw)


def pose_covariance(ref, local, pose: Pose, scale=0.05):
    """Incertitude (écarts-types x, y, θ) d'une pose recalée : approximation de
    Laplace autour du minimum, Σ = s² (JᵀWJ)⁻¹ avec s² = variance résiduelle."""
    p = pose.transform(local)
    d, g = ref.query(p)
    w = _robust_weights(d, scale) * (d < D_MAX)
    J = np.column_stack([g[:, 0], g[:, 1], -g[:, 0] * (p[:, 1] - pose.y) + g[:, 1] * (p[:, 0] - pose.x)])
    H = (J * w[:, None]).T @ J
    s2 = float((w * d ** 2).sum() / max(w.sum() - 3, 1))
    try:
        cov = s2 * np.linalg.inv(H)
    except np.linalg.LinAlgError:
        return None
    return np.sqrt(np.abs(np.diag(cov)))


def load_reference(path, ref_pose: Pose | None = None) -> Reference:
    """Référence lue dans un fichier : grid map (.npz), carte vectorielle
    (.txt, ou CSV dont l'en-tête commence par x1,y1,x2,y2 : vector_map.txt du
    MapTool, carte_vectorielle.txt, segments.csv) ou scan de référence (CSV,
    placé à `ref_pose`, sinon à la position du robot écrite dans le fichier,
    sinon à l'origine)."""
    from pathlib import Path
    from carto.scan import load_scan_file
    path = Path(path)
    if path.suffix.lower() == ".npz":
        return GridRef(OccupancyGrid.load(path))
    rows = [l for l in path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
            if l.strip() and not l.lstrip().startswith("#")]
    if path.suffix.lower() == ".txt" or (rows and rows[0].replace(" ", "").lower().startswith("x1,y1,x2,y2")):
        segs = []
        for l in rows:
            try:
                x1, y1, x2, y2 = map(float, l.replace(";", ",").split(",")[:4])
            except ValueError:
                continue  # en-tête
            segs.append(Segment((x1, y1), (x2, y2)))
        return VectorRef(segs)
    s = load_scan_file(path)[0]
    source = "argument" if ref_pose else "fichier" if s.meta.get("robot_pose") else None
    pose = ref_pose or s.meta.get("robot_pose")
    if pose is None:  # scan d'une session Lidar Plot : sa pose est dans poses.json, à côté
        pj = path.parent / "poses.json"
        if pj.exists():
            from carto.scan import load_poses
            pose = load_poses(pj).get(path.stem)
            source = "poses.json" if pose is not None else None
    ref = CloudRef(s.filtered().world_xy(pose or Pose()), point_to_line=True)
    ref.pose_source = source or "origine"   # "origine" : pose inconnue, scan placé en (0, 0, 0)
    ref.pose = pose or Pose()
    return ref
