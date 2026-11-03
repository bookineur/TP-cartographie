"""Scans lidar (polaire) et poses 2D.

Conventions (valables dans tout le projet) :
  * angle en sens TRIGO (anti-horaire), 0 = avant du lidar, comme la sortie
    de la librairie Arduino (qui fait déjà 360 - angle_capteur) ;
  * distances en mètres dans le code, en mm dans les fichiers CSV ;
  * pose = (x, y, theta) du lidar dans le repère carte, theta en radians.

Format CSV écrit par ld06.capture :
    # speed_dps=2152 mode=raw
    angle_deg,distance_mm,intensity
    359.20,1532,210
On sait aussi relire directement le CSV de LD06::printScanCSV
(N,Angle(°),Distance(mm),Intensity,x(mm),y(mm)), éventuellement plusieurs
scans séparés par des lignes vides (copier-coller du moniteur série).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


@dataclass
class Pose:
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0  # rad

    def transform(self, pts: np.ndarray) -> np.ndarray:
        """Repère lidar -> repère carte : p_carte = R(theta) p_lidar + t."""
        c, s = np.cos(self.theta), np.sin(self.theta)
        R = np.array([[c, -s], [s, c]])
        return pts @ R.T + np.array([self.x, self.y])

    def as_list_deg(self):
        return [round(self.x, 4), round(self.y, 4), round(float(np.degrees(self.theta)), 3)]

    @classmethod
    def from_list_deg(cls, v):
        return cls(float(v[0]), float(v[1]), float(np.radians(v[2])))


@dataclass
class Scan:
    name: str
    angles: np.ndarray       # rad, trigo, triés croissants
    ranges: np.ndarray       # m (0 = pas d'écho)
    intensities: np.ndarray  # 0-255
    meta: dict = field(default_factory=dict)

    def __post_init__(self):
        order = np.argsort(self.angles, kind="stable")
        self.angles = np.asarray(self.angles, float)[order]
        self.ranges = np.asarray(self.ranges, float)[order]
        self.intensities = np.asarray(self.intensities, float)[order]

    def __len__(self):
        return len(self.angles)

    def filtered(self, min_range=0.05, max_range=12.0, min_intensity=0) -> "Scan":
        """Supprime les points invalides : distance 0 (pas d'écho), trop proches
        (le boîtier/les câbles), trop loin (au-delà de la portée fiable) ou
        trop faibles en intensité (reflets, vitres)."""
        m = (self.ranges >= min_range) & (self.ranges <= max_range) & (self.intensities >= min_intensity)
        return Scan(self.name, self.angles[m], self.ranges[m], self.intensities[m], dict(self.meta))

    def local_xy(self) -> np.ndarray:
        return np.column_stack([self.ranges * np.cos(self.angles), self.ranges * np.sin(self.angles)])

    def world_xy(self, pose: Pose) -> np.ndarray:
        return pose.transform(self.local_xy())


# --------------------------------------------------------------------------- I/O

def save_scan_csv(path, angle_deg, distance_mm, intensity, meta=None):
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        if meta:
            f.write("# " + " ".join(f"{k}={v}" for k, v in meta.items()) + "\n")
        f.write("angle_deg,distance_mm,intensity\n")
        for a, d, i in zip(angle_deg, distance_mm, intensity):
            f.write(f"{float(a):.2f},{int(round(d))},{int(i)}\n")


def load_scan_file(path) -> list[Scan]:
    """Lit un fichier ; renvoie 1 scan, ou plusieurs si le fichier en contient
    plusieurs séparés par des lignes vides / des en-têtes répétés."""
    path = Path(path)
    blocks, cur, meta, cols = [], [], {}, (0, 1, 2)
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            for kv in line[1:].split():
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    meta[k] = v
            continue
        low = line.lower()
        if not line or low.startswith("angle") or low.startswith("n,"):
            if low.startswith("n,"):
                cols = (1, 2, 3)  # format printScanCSV : N,Angle,Distance,Intensity,x,y
            if cur:
                blocks.append(cur)
                cur = []
            continue
        parts = line.replace(";", ",").split(",")
        try:
            cur.append((float(parts[cols[0]]), float(parts[cols[1]]),
                        float(parts[cols[2]]) if len(parts) > cols[2] else 0.0))
        except (ValueError, IndexError):
            continue
    if cur:
        blocks.append(cur)

    scans = []
    for k, b in enumerate(blocks):
        a = np.array(b)
        name = path.stem if len(blocks) == 1 else f"{path.stem}#{k}"
        scans.append(Scan(name, np.radians(a[:, 0]), a[:, 1] / 1000.0, a[:, 2], dict(meta)))
    return scans


def load_scans(paths) -> list[Scan]:
    out = []
    for p in paths:
        p = Path(p)
        files = sorted(p.glob("*.csv")) if p.is_dir() else [p]
        for f in files:
            out += load_scan_file(f)
    return out


def load_poses(path) -> dict[str, Pose]:
    """JSON {nom_scan: [x_m, y_m, theta_deg]}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return {k: Pose.from_list_deg(v) for k, v in data.items()}


def save_poses(path, poses: dict[str, Pose]):
    Path(path).write_text(json.dumps({k: p.as_list_deg() for k, p in poses.items()}, indent=2),
                          encoding="utf-8")
