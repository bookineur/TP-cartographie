"""Analyses utilisées par l'assistant de capture (sans interface, donc testables).

  scan_quality    : un lot de tours pris à une position est-il exploitable ?
  overlap_ratio   : quelle part du scan retombe sur des murs déjà connus ?
                    (recouvrement ; sert aussi à vérifier la pose saisie)
  refine_pose     : recalage automatique de la pose (recherche par corrélation)
  suggest_next    : où se placer pour voir ce qui manque (frontières libre/inconnu)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from carto.gridmap import OccupancyGrid
from carto.scan import Pose, Scan

OK, WARN, ERROR = "ok", "warn", "error"
_RANK = {OK: 0, WARN: 1, ERROR: 2}

# Seuils de recouvrement (part des points à <= 2 cellules d'un mur connu).
# En simulation : pose exacte -> 95-100 %, pose mesurée au mètre (±6 cm, ±3°)
# -> 30-65 %, pose fausse -> < 30 %. Une position qui découvre beaucoup de
# zones nouvelles a aussi un recouvrement plus faible : d'où « à vérifier ».
OVERLAP_OK, OVERLAP_MIN = 0.70, 0.30


def overlap_level(ov: float) -> str:
    return OK if ov >= OVERLAP_OK else WARN if ov >= OVERLAP_MIN else ERROR


@dataclass
class Report:
    messages: list[tuple[str, str]] = field(default_factory=list)  # (niveau, texte)
    stats: dict = field(default_factory=dict)

    def add(self, level, text):
        self.messages.append((level, text))

    @property
    def level(self):
        return max((m[0] for m in self.messages), key=_RANK.get, default=OK)


def dilate(mask: np.ndarray, r: int) -> np.ndarray:
    """Dilatation binaire carrée de rayon r cellules (numpy pur)."""
    if r <= 0:
        return mask.copy()
    H, W = mask.shape
    p = np.pad(mask, r)
    out = np.zeros_like(mask)
    for dy in range(2 * r + 1):
        for dx in range(2 * r + 1):
            out |= p[dy:dy + H, dx:dx + W]
    return out


# =================================================================== qualité

def _nearest_diff(a: Scan, b: Scan, max_dang=np.radians(1.0)):
    """|r_a - r_b| pour les points de a dont b a un voisin angulaire proche."""
    va, vb = a.ranges > 0, b.ranges > 0
    if vb.sum() < 10 or va.sum() < 10:
        return np.array([])
    ang_b, r_b = b.angles[vb], b.ranges[vb]
    idx = np.searchsorted(ang_b, a.angles[va]).clip(1, len(ang_b) - 1)
    left, right = ang_b[idx - 1], ang_b[idx]
    pick = np.where(np.abs(a.angles[va] - left) < np.abs(right - a.angles[va]), idx - 1, idx)
    ok = np.abs(ang_b[pick] - a.angles[va]) <= max_dang
    return np.abs(a.ranges[va][ok] - r_b[pick][ok])


def scan_quality(scans: list[Scan]) -> Report:
    rep = Report()
    if not scans:
        rep.add(ERROR, "Aucun tour reçu.")
        return rep
    n_pts = np.mean([len(s) for s in scans])
    allr = np.concatenate([s.ranges for s in scans])
    alli = np.concatenate([s.intensities for s in scans])
    valid = allr > 0.05
    invalid = 1 - valid.mean()
    near = ((allr > 0) & (allr < 0.15)).mean()
    far = (allr[valid] > 8).mean() if valid.any() else 0
    weak = (alli[valid] < 50).mean() if valid.any() else 0
    rep.stats.update(points_par_tour=round(float(n_pts)), invalides=round(float(invalid), 3),
                     proches=round(float(near), 3), lointains=round(float(far), 3), faibles=round(float(weak), 3))

    if n_pts < 300:
        rep.add(ERROR, f"Tours incomplets ({n_pts:.0f} points au lieu de ~450) : paquets perdus "
                       "(débit série ? câble ?) ou lidar qui tourne trop vite.")
    elif n_pts < 400:
        rep.add(WARN, f"{n_pts:.0f} points par tour (attendu ~450) : quelques paquets perdus.")
    else:
        rep.add(OK, f"{n_pts:.0f} points par tour.")

    if invalid > 0.30:
        rep.add(ERROR, f"{invalid:.0%} de mesures sans écho : lidar masqué, vitres/surfaces noires, "
                       "ou murs hors de portée.")
    elif invalid > 0.10:
        rep.add(WARN, f"{invalid:.0%} de mesures sans écho (vitres, objets noirs, ouvertures ?).")
    if near > 0.02:
        rep.add(WARN, f"{near:.0%} de points à moins de 15 cm : câble, main ou pied de table "
                      "contre le lidar ? Ils cachent une partie de la salle.")
    if far > 0.20:
        rep.add(WARN, f"{far:.0%} des points au-delà de 8 m : précision plus faible, "
                      "rapprochez-vous de ces murs.")
    if weak > 0.20:
        rep.add(WARN, f"{weak:.0%} de points de faible intensité (<50) : surfaces sombres ou reflets.")

    speeds = [s.meta.get("speed_dps") for s in scans]
    speeds = [float(v) for v in speeds if v not in (None, "", 0, "0")]
    if speeds:
        hz = np.mean(speeds) / 360
        rep.stats["tours_par_s"] = round(hz, 1)
        if not 5 <= hz <= 13:
            rep.add(WARN, f"Vitesse de rotation {hz:.1f} tr/s hors plage 5-13 Hz de la datasheet.")

    if len(scans) >= 2:
        diffs = [_nearest_diff(scans[k], scans[k + 1]) for k in range(len(scans) - 1)]
        diffs = np.concatenate([d for d in diffs if len(d)]) if any(len(d) for d in diffs) else np.array([])
        if len(diffs):
            med, moving = float(np.median(diffs)), float((diffs > 0.20).mean())
            rep.stats.update(ecart_median_m=round(med, 3), points_mobiles=round(moving, 3))
            if med > 0.05:
                rep.add(ERROR, f"Les tours ne se ressemblent pas (écart médian {med * 100:.0f} cm) : "
                               "le lidar a bougé pendant la capture.")
            elif moving > 0.10:
                rep.add(WARN, f"{moving:.0%} des points changent de plus de 20 cm d'un tour à l'autre : "
                              "quelqu'un passait ? Reprendre quand la zone est vide.")
            else:
                rep.add(OK, f"Tours stables (écart médian {med * 1000:.0f} mm).")
    return rep


def live_check(scan: Scan) -> list[tuple[str, str]]:
    """Contrôle rapide d'UN tour en direct (avant de capturer) : seulement les
    problèmes, pour pouvoir les corriger avant d'appuyer sur « Capturer »."""
    return [m for m in scan_quality([scan]).messages if m[0] != OK]


def dominant_wall_angle(scan: Scan) -> float | None:
    """Orientation principale des murs vus par le scan, dans le repère du
    lidar, modulo 90° (les murs d'une salle sont en général perpendiculaires).
    Moyenne circulaire des orientations des segments, pondérée par leur
    longueur, sur l'angle 4·phi (période 90°). Renvoie un angle dans
    [-45°, 45°[ en radians, ou None s'il n'y a pas assez de murs."""
    from carto.segments import extract_segments
    segs = [s for s in extract_segments(scan.filtered().local_xy()) if s.length >= 0.5]
    if sum(s.length for s in segs) < 2.0:
        return None
    w = np.array([s.length for s in segs])
    phi = np.array([s.orientation for s in segs])
    c, s = (w * np.cos(4 * phi)).sum(), (w * np.sin(4 * phi)).sum()
    if np.hypot(c, s) < 0.5 * w.sum():  # murs pas orthogonaux entre eux : pas de direction nette
        return None
    return float(np.arctan2(s, c) / 4)


def theta_aligned_on_walls(scan: Scan, theta: float) -> float | None:
    """θ le plus proche de `theta` qui rend les murs parallèles aux axes x/y."""
    a = dominant_wall_angle(scan)
    if a is None:
        return None
    # direction d'un mur dans le repère carte = a + theta ; on la veut multiple de 90°
    corr = -((a + theta + np.pi / 4) % (np.pi / 2) - np.pi / 4)
    return theta + corr


# ============================================================ recouvrement

def likelihood_field(grid: OccupancyGrid) -> np.ndarray:
    """1 sur les cellules occupées, 0.5 à 1 cellule, 0.25 à 2 cellules, 0 ailleurs."""
    occ = grid.logodds > 0
    d1, d2 = dilate(occ, 1), dilate(occ, 2)
    return occ * 1.0 + (d1 & ~occ) * 0.5 + (d2 & ~d1) * 0.25


def overlap_ratio(grid: OccupancyGrid | None, scan: Scan, pose: Pose, field_=None) -> float | None:
    """Part des points du scan qui tombent à <= 2 cellules d'un mur déjà connu."""
    if grid is None:
        return None
    f = likelihood_field(grid) if field_ is None else field_
    pts = scan.filtered().world_xy(pose)
    if len(pts) == 0:
        return 0.0
    c = grid.world_to_cell(pts)
    H, W = f.shape
    ok = (c[:, 0] >= 0) & (c[:, 0] < W) & (c[:, 1] >= 0) & (c[:, 1] < H)
    hit = np.zeros(len(pts), bool)
    hit[ok] = f[c[ok, 1], c[ok, 0]] > 0
    return float(hit.mean())


def _score(f, grid, local, pose_xy, thetas, offsets):
    """Score de corrélation pour chaque (theta, décalage entier en cellules)."""
    H, W = f.shape
    best = (-1.0, 0.0, (0, 0))
    for th in thetas:
        c, s = np.cos(th), np.sin(th)
        pts = local @ np.array([[c, s], [-s, c]]) + pose_xy
        cells = grid.world_to_cell(pts)
        cx = cells[None, :, 0] + offsets[:, None, 0]
        cy = cells[None, :, 1] + offsets[:, None, 1]
        ok = (cx >= 0) & (cx < W) & (cy >= 0) & (cy < H)
        vals = np.where(ok, f[cy.clip(0, H - 1), cx.clip(0, W - 1)], 0.0).sum(axis=1)
        k = int(np.argmax(vals))
        if vals[k] > best[0]:
            best = (float(vals[k]), th, tuple(offsets[k]))
    return best


def refine_pose(grid: OccupancyGrid, scan: Scan, pose: Pose, max_xy=0.4, max_theta_deg=8.0):
    """Recale la pose saisie sur la carte existante (recherche exhaustive
    grossière puis fine sur theta, décalages entiers de cellules en x, y).
    Renvoie (pose_proposée, recouvrement_avant, recouvrement_après)."""
    f = likelihood_field(grid)
    local = scan.filtered().local_xy()
    if len(local) < 20:
        return pose, None, None
    n = int(round(max_xy / grid.res))
    r = np.arange(-n, n + 1)
    offsets = np.array([(i, j) for i in r for j in r])
    xy = np.array([pose.x, pose.y])
    _, th, off = _score(f, grid, local, xy, pose.theta + np.radians(np.arange(-max_theta_deg, max_theta_deg + 1e-9, 1.0)), offsets)
    _, th, off2 = _score(f, grid, local, xy + np.array(off) * grid.res,
                         th + np.radians(np.arange(-1, 1 + 1e-9, 0.1)), np.array([(i, j) for i in (-1, 0, 1) for j in (-1, 0, 1)]))
    total = np.array(off) + np.array(off2)
    new = Pose(pose.x + total[0] * grid.res, pose.y + total[1] * grid.res, float(th))
    return new, overlap_ratio(grid, scan, pose, f), overlap_ratio(grid, scan, new, f)


# ============================================================== suggestions

def _components(mask: np.ndarray) -> list[np.ndarray]:
    """Composantes 8-connexes d'un masque booléen -> liste de tableaux (iy, ix)."""
    seen = np.zeros_like(mask)
    comps = []
    H, W = mask.shape
    for y0, x0 in zip(*np.nonzero(mask)):
        if seen[y0, x0]:
            continue
        stack, cells = [(y0, x0)], []
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            cells.append((y, x))
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        comps.append(np.array(cells))
    return comps


@dataclass
class Suggestion:
    x: float
    y: float
    frontier_m: float   # longueur de la frontière visée
    target: tuple       # centre de la zone inconnue visée


def frontier_mask(grid: OccupancyGrid) -> np.ndarray:
    """Cellules libres au bord d'une zone jamais vue.
    On « bouche » d'abord les trous dus à l'écartement des rayons par une
    FERMETURE morphologique (dilatation puis érosion de 2 cellules : les trous
    disparaissent sans que la zone vue grossisse), pour ne pas prendre ces
    stries pour de l'inconnu, et on ignore ce qui touche les murs."""
    free, occ = grid.logodds < 0, grid.logodds > 0
    seen = ~dilate(~dilate(free | occ, 2), 2)
    return free & ~dilate(occ, 1) & dilate(~seen, 1)


def suggest_next(grid: OccupancyGrid, poses: list[Pose], max_suggestions=3,
                 min_frontier_m=0.4, wall_clearance=0.35, min_dist_to_poses=0.6) -> list[Suggestion]:
    res = grid.res
    comps = [c for c in _components(frontier_mask(grid)) if len(c) * res >= min_frontier_m]
    comps.sort(key=len, reverse=True)
    free, occ = grid.logodds < 0, grid.logodds > 0
    safe = free & ~dilate(occ, int(np.ceil(wall_clearance / res)))
    sy, sx = np.nonzero(safe)
    if len(sx) == 0:
        return []
    safe_xy = grid.origin + (np.column_stack([sx, sy]) + 0.5) * res
    if poses:
        P = np.array([[p.x, p.y] for p in poses])
        far = np.min(np.hypot(*(safe_xy[:, None, :] - P[None, :, :]).transpose(2, 0, 1)), axis=1) >= min_dist_to_poses
        safe_xy = safe_xy[far] if far.any() else safe_xy
    out = []
    for c in comps[:max_suggestions]:
        centre = grid.origin + (c[:, ::-1].mean(axis=0) + 0.5) * res
        k = int(np.argmin(np.hypot(*(safe_xy - centre).T)))
        out.append(Suggestion(float(safe_xy[k, 0]), float(safe_xy[k, 1]), len(c) * res, tuple(centre)))
    return out
