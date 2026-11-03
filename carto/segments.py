"""Segments 2D : extraction depuis un nuage de points et opérations géométriques.

Tolérances numériques
---------------------
TOL = 1e-6 m (1 µm) : tolérance de POSITION. Bien en dessous de la résolution
du LD06 (15 mm) mais bien au-dessus des erreurs d'arrondi des flottants
(~1e-15 relatif, soit ~1e-14 m pour des coordonnées de l'ordre de 10 m).
Elle sert à décider « ce point est sur le segment », « l'intersection tombe
sur une extrémité », « les deux côtés ont la même longueur ».

PARALLEL_EPS = 1e-9 : deux directions sont parallèles si |sin(angle)| <= 1e-9.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TOL = 1e-6
PARALLEL_EPS = 1e-9


def _cross(a, b) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


@dataclass
class Segment:
    p1: np.ndarray
    p2: np.ndarray
    n_obs: int = 1  # nombre d'observations fusionnées (propriété de la carte vectorielle)

    def __post_init__(self):
        self.p1 = np.asarray(self.p1, float).copy()
        self.p2 = np.asarray(self.p2, float).copy()

    @property
    def vec(self) -> np.ndarray:
        return self.p2 - self.p1

    @property
    def length(self) -> float:
        return float(np.hypot(*self.vec))

    @property
    def direction(self) -> np.ndarray:
        L = self.length
        return self.vec / L if L > 0 else np.array([1.0, 0.0])

    @property
    def midpoint(self) -> np.ndarray:
        return (self.p1 + self.p2) / 2

    @property
    def orientation(self) -> float:
        """Orientation de la DROITE support, dans [0, pi)."""
        return float(np.arctan2(self.vec[1], self.vec[0]) % np.pi)

    def line_distance(self, p) -> float:
        """Distance de p à la droite support."""
        return abs(_cross(self.direction, np.asarray(p, float) - self.p1))

    def point_distance(self, p) -> float:
        """Distance de p au segment (pas à la droite)."""
        p = np.asarray(p, float)
        L2 = float(self.vec @ self.vec)
        if L2 == 0:
            return float(np.hypot(*(p - self.p1)))
        t = np.clip((p - self.p1) @ self.vec / L2, 0.0, 1.0)
        return float(np.hypot(*(p - (self.p1 + t * self.vec))))

    def contains_point(self, p, tol=TOL) -> bool:
        return self.point_distance(p) <= tol

    def __repr__(self):
        return (f"Segment(({self.p1[0]:.3f}, {self.p1[1]:.3f}) -> "
                f"({self.p2[0]:.3f}, {self.p2[1]:.3f}), L={self.length:.3f})")


# ============================================================== 4.2 angle

def angle_between(s1: Segment, s2: Segment, oriented: bool = False) -> float:
    """Angle entre deux segments, en radians.

    oriented=False : angle entre les DROITES, dans [0, pi/2] (ce qu'on veut
                     pour comparer des murs : un segment A->B et B->A sont
                     le même mur).
    oriented=True  : angle signé de s1.direction vers s2.direction, ]-pi, pi].
    """
    d1, d2 = s1.direction, s2.direction
    a = float(np.arctan2(_cross(d1, d2), d1 @ d2))
    if oriented:
        return a
    a = abs(a) % np.pi
    return min(a, np.pi - a)


# ============================================================== 4.3 proches

def are_close(s1: Segment, s2: Segment, angle_tol=np.radians(8), dist_tol=0.05,
              gap_tol=0.10) -> bool:
    """Deux segments sont « proches » si :
      * angulairement : angle entre droites <= angle_tol ;
      * latéralement  : les extrémités du plus court sont à <= dist_tol de la
                        droite du plus long ;
      * longitudinalement : projetés sur le plus long, ils se recouvrent ou le
                        trou entre eux est <= gap_tol.
    """
    if angle_between(s1, s2) > angle_tol:
        return False
    ref, other = (s1, s2) if s1.length >= s2.length else (s2, s1)
    if max(ref.line_distance(other.p1), ref.line_distance(other.p2)) > dist_tol:
        return False
    d, L = ref.direction, ref.length
    t = sorted([(other.p1 - ref.p1) @ d, (other.p2 - ref.p1) @ d])
    gap = max(0.0, t[0] - L, -t[1])
    return gap <= gap_tol


# ============================================================== 4.4 fusion

def merge(s1: Segment, s2: Segment) -> Segment:
    """Fusionne deux segments proches en un seul.

    Direction = moyenne des directions pondérée par les longueurs (après avoir
    aligné le sens de s2 sur s1) ; la droite passe par le barycentre des
    milieux pondéré par les longueurs ; les extrémités sont les projections
    extrêmes des 4 extrémités sur cette droite. Le sens de s1 est conservé.
    """
    L1, L2 = s1.length, s2.length
    d1, d2 = s1.direction, s2.direction
    if d1 @ d2 < 0:
        d2 = -d2
    d = L1 * d1 + L2 * d2
    d = d / np.hypot(*d) if np.hypot(*d) > 0 else d1
    w = L1 + L2
    c = (L1 * s1.midpoint + L2 * s2.midpoint) / w if w > 0 else s1.midpoint
    t = [(p - c) @ d for p in (s1.p1, s1.p2, s2.p1, s2.p2)]
    return Segment(c + min(t) * d, c + max(t) * d, s1.n_obs + s2.n_obs)


# ============================================================== 4.5 intersection

def intersection(s1: Segment, s2: Segment, tol=TOL):
    """Point d'intersection des deux segments, ou None.

    On résout p1 + t*r = q1 + u*s. Le point est accepté s'il est sur les deux
    segments à `tol` mètres près (extrémités incluses).
    Segments parallèles ou colinéaires -> None (pas de point unique).
    """
    p, r = s1.p1, s1.vec
    q, s = s2.p1, s2.vec
    Lr, Ls = s1.length, s2.length
    if Lr <= tol or Ls <= tol:
        return None
    denom = _cross(r, s)
    if abs(denom) <= PARALLEL_EPS * Lr * Ls:
        return None
    qp = q - p
    t = _cross(qp, s) / denom
    u = _cross(qp, r) / denom
    if -tol / Lr <= t <= 1 + tol / Lr and -tol / Ls <= u <= 1 + tol / Ls:
        return p + t * r
    return None


# ============================================================== 4.6 découpe

def cut(target: Segment, cutter: Segment, tol=TOL) -> tuple[Segment, bool]:
    """Découpe `target` traversé par `cutter` et garde le plus long côté.

    Règles :
      * il faut une intersection située sur les DEUX segments ;
      * elle doit être STRICTEMENT à l'intérieur de `target` (à plus de tol de
        ses extrémités) ; à une extrémité -> rien ne change ;
      * segments colinéaires / parallèles -> pas de découpe ;
      * longueurs égales à tol près -> on garde le côté qui contient target.p1.
    Renvoie (segment_résultat, a_été_coupé).
    """
    x = intersection(target, cutter, tol)
    if x is None:
        return target, False
    d1 = float(np.hypot(*(x - target.p1)))
    d2 = float(np.hypot(*(x - target.p2)))
    if d1 <= tol or d2 <= tol:
        return target, False
    if d2 > d1 + tol:
        return Segment(x, target.p2, target.n_obs), True
    return Segment(target.p1, x, target.n_obs), True  # d1 plus long, ou égalité -> côté de p1


# ============================================================== 4.1 extraction

def fit_line(points: np.ndarray) -> Segment:
    """Moindres carrés TOTAUX (ACP) : minimise la distance orthogonale, donc
    marche aussi pour les murs verticaux (contrairement à y = ax + b).
    Les extrémités sont les projections du 1er et du dernier point."""
    c = points.mean(axis=0)
    _, _, vt = np.linalg.svd(points - c, full_matrices=False)
    d = vt[0]
    t0, t1 = (points[0] - c) @ d, (points[-1] - c) @ d
    return Segment(c + t0 * d, c + t1 * d, 1)


def _split(points: np.ndarray, i: int, j: int, thresh: float, out: list):
    """Split récursif (Iterative End-Point Fit / Douglas-Peucker)."""
    if j - i < 2:
        out.append((i, j))
        return
    a, b = points[i], points[j]
    ab = b - a
    L = np.hypot(*ab)
    rel = points[i + 1:j] - a
    if L < 1e-12:
        dist = np.hypot(rel[:, 0], rel[:, 1])
    else:
        dist = np.abs(ab[0] * rel[:, 1] - ab[1] * rel[:, 0]) / L
    k = int(np.argmax(dist))
    if dist[k] > thresh:
        k += i + 1
        _split(points, i, k, thresh, out)
        _split(points, k, j, thresh, out)
    else:
        out.append((i, j))


def split_clusters(points: np.ndarray, gap: float) -> list[np.ndarray]:
    """Coupe le nuage ORDONNÉ (par angle) là où deux points consécutifs sont
    à plus de `gap` m. Le scan étant circulaire, on fait démarrer la liste au
    plus grand trou pour ne pas couper un mur en deux au passage 360° -> 0°."""
    n = len(points)
    if n == 0:
        return []
    jumps = np.hypot(*(np.roll(points, -1, axis=0) - points).T)  # i -> i+1 (circulaire)
    start = (int(np.argmax(jumps)) + 1) % n
    pts = np.roll(points, -start, axis=0)
    jumps = np.roll(jumps, -start)[:-1]
    cuts = np.where(jumps > gap)[0] + 1
    return [c for c in np.split(pts, cuts) if len(c)]


def _max_residual(points: np.ndarray, seg: Segment) -> float:
    rel = points - seg.p1
    d = seg.direction
    return float(np.max(np.abs(d[0] * rel[:, 1] - d[1] * rel[:, 0])))


def _split_merge(cl: np.ndarray, thresh: float) -> list[tuple[int, int]]:
    ranges = []
    _split(cl, 0, len(cl) - 1, thresh, ranges)
    merged = []
    for i, j in ranges:
        if merged:
            i0 = merged[-1][0]
            if _max_residual(cl[i0:j + 1], fit_line(cl[i0:j + 1])) <= thresh:
                merged[-1] = (i0, j)
                continue
        merged.append((i, j))
    return merged


def extract_segments(points: np.ndarray, split_thresh=0.10, gap=0.20, min_points=6,
                     min_length=0.15) -> list[Segment]:
    """Nuage de points ordonné -> segments (Split-and-Merge).

    1. clusters : coupure aux trous > gap ;
    2. split    : dans chaque cluster, on coupe au point le plus loin de la
                  corde tant que cette distance > split_thresh ;
    3. merge    : deux morceaux consécutifs sont réunis si la droite ajustée
                  sur l'UNION de leurs points reste à <= split_thresh de tous
                  les points (le bruit crée des coupures parasites que l'on
                  annule ainsi ; un vrai coin, lui, donne un gros résidu) ;
    4. fit      : droite des moindres carrés totaux sur chaque morceau final ;
    5. filtre   : on jette les morceaux trop courts / avec trop peu de points.

    split_thresh doit être nettement plus grand que le bruit du capteur :
    la datasheet du LD06 donne une précision de 30 mm (typique), 45 mm (max)
    -> 0.10 m ≈ 3 sigma. Mesuré en simulation avec 30 mm de bruit : 5 cm
    donne 67 morceaux pour 11 murs réels, 8 cm en donne 19, 10 cm en donne 11.
    """
    segs = []
    points = np.asarray(points, float)
    clusters = split_clusters(points, gap)
    for cl in clusters:
        if len(cl) < min_points:
            continue
        merged = _split_merge(cl, split_thresh)
        if len(clusters) == 1 and len(merged) > 1:
            # contour fermé (pièce vue en entier, aucun trou) : le point de
            # départ est arbitraire et coupe un mur en deux. On redémarre sur
            # une vraie cassure (fin du 1er morceau) et on recommence.
            cl = np.roll(cl, -merged[0][1], axis=0)
            merged = _split_merge(cl, split_thresh)
        for i, j in merged:
            if j - i + 1 >= min_points:
                segs.append(fit_line(cl[i:j + 1]))
    return [s for s in segs if s.length >= min_length]
