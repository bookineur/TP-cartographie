"""Carte vectorielle 2D : un ensemble de segments mis à jour scan après scan.

Pour chaque nouveau scan + pose :
  1. points du scan -> repère carte (pose) ;
  2. extraction de segments (split-and-merge, carto.segments) ;
  3. (option) nettoyage par les rayons : un rayon lidar qui traverse un
     segment existant prouve qu'il n'y a pas d'obstacle à cet endroit ; on
     découpe ce segment (outil `cut`) en gardant le plus long côté ;
  4. association : chaque nouveau segment est comparé aux segments de la
     carte ; s'il est « proche » (angle + position) d'un ou plusieurs, ils
     sont fusionnés (outil `merge`), sinon il est ajouté ;
  5. consolidation : on refusionne les segments de la carte devenus proches,
     et on supprime ceux qui sont trop courts.
Chaque segment garde n_obs (nombre d'observations fusionnées) : on peut
filtrer les segments vus une seule fois (bruit, personne qui passe...).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field

import numpy as np

from carto.scan import Pose, Scan
from carto.segments import Segment, are_close, cut, extract_segments, merge


@dataclass
class VectorMap:
    angle_tol: float = np.radians(8)
    dist_tol: float = 0.08
    gap_tol: float = 0.20
    min_length: float = 0.15
    extract_kw: dict = field(default_factory=dict)
    ray_cutting: bool = False
    ray_margin: float = 0.15  # on raccourcit les rayons pour ne pas couper le mur visé
    ray_stride: int = 3       # 1 rayon sur N (coût)
    segments: list[Segment] = field(default_factory=list)
    n_scans: int = 0

    def add_scan(self, scan: Scan, pose: Pose) -> list[Segment]:
        pts = scan.world_xy(pose)
        new = extract_segments(pts, **self.extract_kw)
        if self.ray_cutting and self.segments:
            self._cut_with_rays(pts, pose)
        for s in new:
            self._integrate(s)
        self._consolidate()
        self.n_scans += 1
        return new

    def _integrate(self, s: Segment):
        keep = []
        for m in self.segments:
            if are_close(m, s, self.angle_tol, self.dist_tol, self.gap_tol):
                s = merge(m, s)  # le segment de la carte impose son sens
            else:
                keep.append(m)
        keep.append(s)
        self.segments = keep

    def _consolidate(self):
        changed = True
        while changed:
            changed = False
            for i in range(len(self.segments)):
                for j in range(i + 1, len(self.segments)):
                    a, b = self.segments[i], self.segments[j]
                    if are_close(a, b, self.angle_tol, self.dist_tol, self.gap_tol):
                        self.segments[i] = merge(a, b)
                        del self.segments[j]
                        changed = True
                        break
                if changed:
                    break
        self.segments = [s for s in self.segments if s.length >= self.min_length]

    def _cut_with_rays(self, pts: np.ndarray, pose: Pose):
        origin = np.array([pose.x, pose.y])
        for p in pts[::self.ray_stride]:
            v = p - origin
            L = np.hypot(*v)
            if L <= self.ray_margin:
                continue
            ray = Segment(origin, origin + v * (L - self.ray_margin) / L)
            self.segments = [cut(s, ray)[0] for s in self.segments]

    def confirmed(self, min_obs=2) -> list[Segment]:
        return [s for s in self.segments if s.n_obs >= min_obs]

    def save_csv(self, path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["x1", "y1", "x2", "y2", "length", "n_obs"])
            for s in self.segments:
                w.writerow([f"{s.p1[0]:.4f}", f"{s.p1[1]:.4f}", f"{s.p2[0]:.4f}",
                            f"{s.p2[1]:.4f}", f"{s.length:.4f}", s.n_obs])


def build_vector_map(scans_poses, **kw) -> VectorMap:
    vm = VectorMap(**kw)
    for scan, pose in scans_poses:
        vm.add_scan(scan, pose)
    return vm
