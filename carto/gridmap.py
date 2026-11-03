"""Carte d'occupation 2D (grid map) en log-odds.

Démarche :
  1. On discrétise le plan en cellules carrées de `resolution` mètres.
  2. Pour chaque rayon (pose du lidar -> point d'impact) on trace les cellules
     traversées (méthode « supercover », comme le MapTool du prof ; Bresenham
     reste disponible) : elles sont "libres" (le laser y est passé), la cellule
     d'arrivée est "occupée".
  3. Chaque cellule stocke un log-odds l = log(p / (1-p)) ; 0 = inconnu (p=0.5).
     Une observation libre ajoute l_free (<0), une occupée ajoute l_occ (>0).
     Additionner des log-odds = appliquer Bayes en supposant les mesures
     indépendantes ; on borne l pour que la carte reste capable de changer.
  4. Mettre à jour une carte existante = refaire 2-3 avec le nouveau scan et
     sa pose ; la grille s'agrandit si le scan sort des limites.
"""
from __future__ import annotations

import numpy as np

from carto.scan import Pose, Scan


def bresenham(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Cellules entières du segment (x0,y0)->(x1,y1), extrémités incluses."""
    cells = []
    dx, dy = abs(x1 - x0), -abs(y1 - y0)
    sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
    err = dx + dy
    while True:
        cells.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return cells
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def supercover(x0: float, y0: float, x1: float, y1: float, eps: float = 1e-9) -> list[tuple[int, int]]:
    """Toutes les cellules traversées par le segment (x0,y0)->(x1,y1), coordonnées
    exprimées EN CELLULES (réelles, non arrondies). Méthode « supercover »
    (parcours de grille d'Amanatides & Woo), la même que le MapTool du prof :
    contrairement à Bresenham, aucune cellule touchée n'est sautée, et quand le
    rayon passe exactement par un coin, les deux cellules voisines sont marquées.
    La cellule d'arrivée est (floor(x1), floor(y1))."""
    i, j = int(np.floor(x0)), int(np.floor(y0))
    i_end, j_end = int(np.floor(x1)), int(np.floor(y1))
    cells = [(i, j)]
    dx, dy = x1 - x0, y1 - y0
    step_i = 1 if dx > 0 else (-1 if dx < 0 else 0)
    step_j = 1 if dy > 0 else (-1 if dy < 0 else 0)
    if step_i:
        t_max_i = ((i + 1 if step_i > 0 else i) - x0) / dx
        t_delta_i = step_i / dx
    else:
        t_max_i = t_delta_i = float("inf")
    if step_j:
        t_max_j = ((j + 1 if step_j > 0 else j) - y0) / dy
        t_delta_j = step_j / dy
    else:
        t_max_j = t_delta_j = float("inf")
    n_max = abs(i_end - i) + abs(j_end - j) + 2  # garde-fou contre les erreurs d'arrondi
    while (i != i_end or j != j_end) and len(cells) <= 2 * n_max:
        if t_max_i < t_max_j - eps:
            i += step_i
            t_max_i += t_delta_i
            cells.append((i, j))
        elif t_max_j < t_max_i - eps:
            j += step_j
            t_max_j += t_delta_j
            cells.append((i, j))
        else:  # passage exactement par un coin : on marque aussi les deux voisines
            cells.append((i + step_i, j))
            cells.append((i, j + step_j))
            i += step_i
            j += step_j
            t_max_i += t_delta_i
            t_max_j += t_delta_j
            cells.append((i, j))
    return cells


class OccupancyGrid:
    def __init__(self, resolution=0.05, origin=(0.0, 0.0), shape=(1, 1),
                 l_occ=0.85, l_free=-0.4, l_min=-4.0, l_max=4.0, raytrace="supercover"):
        self.raytrace = raytrace  # "supercover" (méthode du prof) ou "bresenham"
        self.res = float(resolution)
        self.origin = np.array(origin, float)  # coin bas-gauche de la cellule [0, 0]
        self.logodds = np.zeros(shape, np.float32)  # indexé [iy, ix]
        self.hits = np.zeros(shape, np.int32)       # nb d'impacts (info complémentaire)
        self.l_occ, self.l_free, self.l_min, self.l_max = l_occ, l_free, l_min, l_max
        self.n_scans = 0

    # -------------------------------------------------------------- géométrie
    @property
    def shape(self):
        return self.logodds.shape

    @property
    def extent(self):
        """(xmin, xmax, ymin, ymax) pour imshow."""
        ny, nx = self.shape
        return (self.origin[0], self.origin[0] + nx * self.res,
                self.origin[1], self.origin[1] + ny * self.res)

    def world_to_cell(self, xy: np.ndarray) -> np.ndarray:
        return np.floor((np.atleast_2d(xy) - self.origin) / self.res).astype(int)  # (ix, iy)

    def cell_center(self, ix, iy):
        return self.origin + (np.array([ix, iy]) + 0.5) * self.res

    def ensure_contains(self, xmin, ymin, xmax, ymax, margin=1.0):
        """Agrandit la grille (en gardant l'alignement des cellules) si besoin."""
        x0, x1, y0, y1 = self.extent
        pad_l = int(np.ceil(max(0.0, x0 - (xmin - margin)) / self.res)) if xmin < x0 else 0
        pad_b = int(np.ceil(max(0.0, y0 - (ymin - margin)) / self.res)) if ymin < y0 else 0
        pad_r = int(np.ceil(max(0.0, (xmax + margin) - x1) / self.res)) if xmax >= x1 else 0
        pad_t = int(np.ceil(max(0.0, (ymax + margin) - y1) / self.res)) if ymax >= y1 else 0
        if pad_l or pad_b or pad_r or pad_t:
            pads = ((pad_b, pad_t), (pad_l, pad_r))
            self.logodds = np.pad(self.logodds, pads)
            self.hits = np.pad(self.hits, pads)
            self.origin -= np.array([pad_l, pad_b]) * self.res

    # ---------------------------------------------------------------- outils
    @classmethod
    def from_scan(cls, scan: Scan, pose: Pose, resolution=0.05, margin=1.0, **kw) -> "OccupancyGrid":
        """Outil 1 : scan + pose -> nouvelle carte d'occupation."""
        pts = scan.world_xy(pose)
        allp = np.vstack([pts, [[pose.x, pose.y]]])
        lo = np.floor((allp.min(0) - margin) / resolution) * resolution
        hi = allp.max(0) + margin
        shape = tuple(np.ceil((hi - lo) / resolution).astype(int)[::-1] + 1)
        grid = cls(resolution, lo, shape, **kw)
        grid.update(scan, pose)
        return grid

    def update(self, scan: Scan, pose: Pose, decay: float = 0.0) -> "OccupancyGrid":
        """Outil 2 : carte existante + scan + pose -> carte mise à jour.

        decay (0..1) : "durée de vie" des cellules ; avant d'intégrer le scan on
        ramène tous les log-odds vers 0 (inconnu) d'un facteur (1 - decay),
        ce qui fait oublier progressivement ce qui n'est plus revu.
        """
        pts = scan.world_xy(pose)
        if len(pts) == 0:
            return self
        allp = np.vstack([pts, [[pose.x, pose.y]]])
        self.ensure_contains(*allp.min(0), *allp.max(0))
        if decay:
            self.logodds *= (1.0 - decay)

        free, occ = set(), set()
        if self.raytrace == "bresenham":
            sx, sy = self.world_to_cell([pose.x, pose.y])[0]
            for ex, ey in self.world_to_cell(pts):
                ray = bresenham(sx, sy, int(ex), int(ey))
                free.update(ray[:-1])
                occ.add(ray[-1])
        else:
            s = (np.array([pose.x, pose.y]) - self.origin) / self.res  # coordonnées en cellules
            for ex, ey in (pts - self.origin) / self.res:
                ray = supercover(s[0], s[1], ex, ey)
                end = (int(np.floor(ex)), int(np.floor(ey)))
                free.update(ray)
                occ.add(end)
        # une cellule vue à la fois libre et occupée dans le même scan : l'impact gagne
        # (les rayons rasants traversent souvent la cellule d'un mur voisin)
        free -= occ
        # chaque cellule n'est mise à jour qu'une fois par scan, sinon les
        # cellules proches du lidar (traversées par des centaines de rayons)
        # deviendraient "sûres" après un seul scan
        if free:
            fx, fy = np.array(list(free)).T
            self.logodds[fy, fx] += self.l_free
        ox, oy = np.array(list(occ)).T
        self.logodds[oy, ox] += self.l_occ
        self.hits[oy, ox] += 1
        np.clip(self.logodds, self.l_min, self.l_max, out=self.logodds)
        self.n_scans += 1
        return self

    # -------------------------------------------------------------- lecture
    def probability(self) -> np.ndarray:
        return 1.0 - 1.0 / (1.0 + np.exp(self.logodds))

    def classify(self, occ_thresh=0.65, free_thresh=0.35) -> np.ndarray:
        """-1 inconnu, 0 libre, 1 occupé."""
        p = self.probability()
        out = np.full(p.shape, -1, np.int8)
        out[p <= free_thresh] = 0
        out[p >= occ_thresh] = 1
        return out

    def save(self, path):
        np.savez_compressed(path, logodds=self.logodds, hits=self.hits, origin=self.origin,
                            res=self.res, params=[self.l_occ, self.l_free, self.l_min, self.l_max])

    @classmethod
    def load(cls, path) -> "OccupancyGrid":
        d = np.load(path)
        l_occ, l_free, l_min, l_max = d["params"]
        g = cls(float(d["res"]), d["origin"], d["logodds"].shape, l_occ, l_free, l_min, l_max)
        g.logodds[:] = d["logodds"]
        g.hits[:] = d["hits"]
        return g


def build_grid(scans_poses, resolution=0.05, decay=0.0, **kw) -> OccupancyGrid:
    """Premier scan -> from_scan, les suivants -> update."""
    grid = None
    for scan, pose in scans_poses:
        if grid is None:
            grid = OccupancyGrid.from_scan(scan, pose, resolution, **kw)
        else:
            grid.update(scan, pose, decay=decay)
    return grid
