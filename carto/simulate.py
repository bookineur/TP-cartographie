"""Scans SIMULÉS d'une salle, pour tester les outils sans lidar.

Ne remplace pas les scans réels demandés par le TP : sert à vérifier que
la chaîne fonctionne (on connaît la vérité terrain) avant de passer au réel.
Le simulateur imite le LD06 : ~450 points/tour, bruit ~30 mm, quelques
mesures à 0 (pas d'écho), angles en sens trigo comme la librairie.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from carto.scan import Pose, save_scan_csv

# Salle en L de 8 x 6 m avec une cloison percée d'une porte et un pilier.
ROOM = [
    ((0, 0), (8, 0)), ((8, 0), (8, 3.5)), ((8, 3.5), (5, 3.5)), ((5, 3.5), (5, 6)),
    ((5, 6), (0, 6)), ((0, 6), (0, 0)),
    ((3, 0), (3, 2.0)), ((3, 2.9), (3, 3.6)),                               # cloison + porte
    ((6.2, 1.2), (6.8, 1.2)), ((6.8, 1.2), (6.8, 1.8)), ((6.8, 1.8), (6.2, 1.8)), ((6.2, 1.8), (6.2, 1.2)),  # pilier
]

TRUE_POSES = {"pos1": Pose(1.5, 1.5, np.radians(10)), "pos2": Pose(1.5, 4.5, np.radians(-30)),
              "pos3": Pose(4.2, 2.2, np.radians(95)), "pos4": Pose(6.5, 2.8, np.radians(180))}


def raycast(pose: Pose, angles: np.ndarray, walls=ROOM, max_range=12.0) -> np.ndarray:
    o = np.array([pose.x, pose.y])
    dirs = np.column_stack([np.cos(angles + pose.theta), np.sin(angles + pose.theta)])
    best = np.full(len(angles), np.inf)
    for a, b in walls:
        a, b = np.array(a, float), np.array(b, float)
        s = b - a
        denom = dirs[:, 0] * s[1] - dirs[:, 1] * s[0]
        ao = a - o
        with np.errstate(divide="ignore", invalid="ignore"):
            t = (ao[0] * s[1] - ao[1] * s[0]) / denom
            u = (ao[0] * dirs[:, 1] - ao[1] * dirs[:, 0]) / denom
        ok = (np.abs(denom) > 1e-12) & (t > 0) & (u >= 0) & (u <= 1)
        best = np.where(ok & (t < best), t, best)
    best[best > max_range] = 0.0
    best[~np.isfinite(best)] = 0.0
    return best


def simulate(out_dir="data/sim", n_scans_per_pose=1, seed=0, pose_noise=(0.25, 0.25, 8.0)):
    rng = np.random.default_rng(seed)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    init = {}
    for name, pose in TRUE_POSES.items():
        for k in range(n_scans_per_pose):
            n = 450
            ang = (np.arange(n) * 360.0 / n + rng.uniform(0, 0.8)) % 360.0
            r = raycast(pose, np.radians(ang))
            valid = r > 0
            r = r + rng.normal(0, 0.03, n) * valid  # précision typique de la datasheet : 30 mm
            r[rng.random(n) < 0.02] = 0.0  # pas d'écho
            inten = np.where(r > 0, np.clip(rng.normal(200, 20, n) - 8 * r, 0, 255), 0)
            stem = f"{name}_{k:03d}"
            save_scan_csv(out / f"{stem}.csv", ang, r * 1000, inten,
                          meta={"simulated": 1, "speed_dps": 3600})
            # pose initiale volontairement fausse : à recaler à la main dans le viewer
            noisy = Pose(pose.x + rng.normal(0, pose_noise[0]), pose.y + rng.normal(0, pose_noise[1]),
                         pose.theta + np.radians(rng.normal(0, pose_noise[2])))
            init[stem] = noisy.as_list_deg()
    truth = {f"{n}_{k:03d}": p.as_list_deg() for n, p in TRUE_POSES.items() for k in range(n_scans_per_pose)}
    (out / "poses_truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    (out / "poses_init.json").write_text(json.dumps(init, indent=2), encoding="utf-8")
    return out
