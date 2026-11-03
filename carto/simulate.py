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


def simulate_tp2_session(out_dir="data/repetition_tp2", n_marks=8, repeats=2, seed=1,
                         measure_err=(0.015, 1.5), place_err=(0.01, 1.0)):
    """Répétition de la séance « vrais tests » du TP 2, en simulation :
    repères au sol, robot orienté parallèlement aux murs, `repeats` captures par
    repère (robot reposé entre deux captures : erreur de placement `place_err`),
    positions MESURÉES avec une erreur `measure_err` (m, °) et saisies dans
    poses.json. La vraie pose de chaque capture est dans verite.json.
    Les mêmes scans sont aussi écrits au format RobotControl dans robotcontrol/."""
    from carto.evaluation import random_room_poses
    from carto.scan import Scan, save_poses, save_scan_maptool
    rng = np.random.default_rng(seed)
    out = Path(out_dir)
    (out / "robotcontrol").mkdir(parents=True, exist_ok=True)
    marks = random_room_poses(n_marks - 2, rng, clearance=0.5)
    marks = [Pose(p.x, p.y, np.radians(rng.choice([0, 90, 180, -90]))) for p in marks]
    for base in marks[:2]:  # deux repères à 30 cm d'un autre : localisation entre scans
        marks.append(Pose(base.x + 0.3, base.y, base.theta))
    measured, truth, k = {}, {}, 0
    for mark in marks:
        m = Pose(mark.x + rng.normal(0, measure_err[0]), mark.y + rng.normal(0, measure_err[0]),
                 mark.theta + np.radians(rng.normal(0, measure_err[1])))
        for _ in range(repeats):
            k += 1
            true = Pose(mark.x + rng.normal(0, place_err[0]), mark.y + rng.normal(0, place_err[0]),
                        mark.theta + np.radians(rng.normal(0, place_err[1])))
            n = 450
            ang = (np.arange(n) * 360.0 / n + rng.uniform(0, 0.8)) % 360.0
            r = raycast(true, np.radians(ang))
            r = r + rng.normal(0, 0.03, n) * (r > 0)
            r[rng.random(n) < 0.02] = 0.0
            inten = np.where(r > 0, np.clip(rng.normal(200, 20, n) - 8 * r, 0, 255), 0)
            name = f"scan{k}"
            save_scan_csv(out / f"{name}.csv", ang, r * 1000, inten, meta={"heure": "simulé", "source": "répétition TP2"})
            # même scan, tel que RobotControl l'exporterait (pose saisie = pose mesurée)
            rc = out / "robotcontrol" / f"lidar_scan_{k}.csv"
            rc.write_text(f"# Robot position: x={m.x:.4f}m, y={m.y:.4f}m, theta={np.degrees(m.theta):.2f}deg\n"
                          "angle_deg,distance_m,intensity\n"
                          + "".join(f"{a:.3f},{d:.4f},{int(i)}\n" for a, d, i in zip(ang, r, inten)), "utf-8")
            measured[name], truth[name] = m, true
    save_poses(out / "poses.json", measured)
    save_poses(out / "verite.json", truth)
    return out


# --------------------------------------------------------------------------- exercice d'assemblage
# Salle 7 x 5 m : une porte dans le mur du bas, une armoire (0,6 x 1,6 m) contre le mur de gauche et
# une table (1,4 x 0,8 m) au milieu. Sert à s'entraîner à l'assemblage avec une vérité cachée.
ROOM_EXERCISE = [
    ((0, 0), (3.0, 0)), ((3.9, 0), (7, 0)), ((7, 0), (7, 5)), ((7, 5), (0, 5)), ((0, 5), (0, 0)),
    ((0, 1.6), (0.6, 1.6)), ((0.6, 1.6), (0.6, 3.2)), ((0.6, 3.2), (0, 3.2)),                      # armoire
    ((3.2, 2.0), (4.6, 2.0)), ((4.6, 2.0), (4.6, 2.8)), ((4.6, 2.8), (3.2, 2.8)), ((3.2, 2.8), (3.2, 2.0)),  # table
]
EXERCISE_POSES = [Pose(1.6, 1.0, np.radians(0)), Pose(5.8, 1.0, np.radians(80)), Pose(6.0, 4.0, np.radians(200)),
                  Pose(3.5, 4.2, np.radians(-120)), Pose(1.5, 4.2, np.radians(35)), Pose(3.8, 1.2, np.radians(150)),
                  Pose(5.2, 3.0, np.radians(-20)), Pose(2.0, 2.5, np.radians(260))]


def simulate_exercise(out_dir="data/exercice_assemblage", seed=3):
    """8 scans de la salle d'exercice (positions inconnues de l'élève) + la correction dans `correction/`
    (poses vraies, grid map et carte vectorielle de référence)."""
    from carto.gridmap import build_grid
    from carto.register import clean_scan
    from carto.scan import Scan
    rng = np.random.default_rng(seed)
    out = Path(out_dir)
    (out / "correction").mkdir(parents=True, exist_ok=True)
    pairs = []
    for k, pose in enumerate(EXERCISE_POSES, 1):
        n = 450
        ang = (np.arange(n) * 360.0 / n + rng.uniform(0, 0.8)) % 360.0
        r = raycast(pose, np.radians(ang), walls=ROOM_EXERCISE)
        valid = r > 0
        r = r + rng.normal(0, 0.03, n) * valid
        r[rng.random(n) < 0.02] = 0.0
        inten = np.where(r > 0, np.clip(rng.normal(200, 20, n) - 8 * r, 0, 255), 0)
        save_scan_csv(out / f"scan{k}.csv", ang, r * 1000, inten, meta={"simulated": 1, "speed_dps": 3600})
        pairs.append((clean_scan(Scan("s", np.radians(ang), r, inten)), pose))
    (out / "correction" / "poses_vraies.json").write_text(
        json.dumps({f"scan{k}": p.as_list_deg() for k, p in enumerate(EXERCISE_POSES, 1)}, indent=2), "utf-8")
    grid = build_grid(pairs, resolution=0.05)
    grid.save(out / "correction" / "gridmap_reference.npz")
    (out / "correction" / "carte_vectorielle_reference.txt").write_text(
        "# x1,y1,x2,y2 en mètres (salle d'exercice)\n"
        + "".join(f"{a[0]},{a[1]},{b[0]},{b[1]}\n" for a, b in ROOM_EXERCISE), "utf-8")
    return out
