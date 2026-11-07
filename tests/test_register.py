import numpy as np

from carto.register import assemble, clean_scan, match_global
from carto.scan import Pose, Scan
from carto.simulate import TRUE_POSES, raycast


def sim(pose, seed=0, noise=0.03):
    rng = np.random.default_rng(seed)
    ang = np.radians(np.arange(0, 360, 0.8))
    r = raycast(pose, ang)
    r = np.where(r > 0, r + rng.normal(0, noise, len(r)), 0)
    return Scan("s", ang, r, np.zeros(len(r)))


def rel(a: Pose, b: Pose) -> Pose:
    c, s = np.cos(-a.theta), np.sin(-a.theta)
    d = np.array([[c, -s], [s, c]]) @ np.array([b.x - a.x, b.y - a.y])
    return Pose(d[0], d[1], b.theta - a.theta)


def test_clean_scan_removes_isolated_points():
    s = sim(TRUE_POSES["pos1"])
    n0 = len(s.filtered())
    ang = np.append(s.angles, [0.123, 2.5])
    r = np.append(s.ranges, [0.7, 1.1])          # deux points isolés au milieu de la pièce
    dirty = Scan("d", ang, r, np.zeros(len(r)))
    c = clean_scan(dirty)
    assert len(c) <= n0 and not np.any(np.isclose(c.ranges, 0.7)) and not np.any(np.isclose(c.ranges, 1.1))


def test_structural_points_keeps_walls_not_legs():
    from carto.register import structural_points
    s = sim(TRUE_POSES["pos1"]).filtered()
    # ajoute 6 « pieds de chaise » : petits amas de 3 points
    rng = np.random.default_rng(3)
    ang, r = list(s.angles), list(s.ranges)
    for c in rng.uniform(0, 2 * np.pi, 6):
        for k in range(3):
            ang.append(c + k * 0.004)
            r.append(0.9)
    legs = Scan("l", np.array(ang), np.array(r), np.zeros(len(r)))
    sp = structural_points(legs)
    d = np.hypot(sp[:, 0], sp[:, 1])
    assert len(sp) > 0.6 * len(s)                    # les murs sont gardés
    assert not np.any(np.abs(d - 0.9) < 0.02)       # les pieds sont écartés


def test_match_global_finds_unknown_pose():
    a, b = TRUE_POSES["pos1"], TRUE_POSES["pos3"]   # ~2.8 m et 85° d'écart, aucune pose fournie
    m = match_global(sim(a).filtered().local_xy(), sim(b, 1).filtered().local_xy())
    t = rel(a, b)
    assert np.hypot(m.pose.x - t.x, m.pose.y - t.y) < 0.08
    assert abs((np.degrees(m.pose.theta - t.theta) + 180) % 360 - 180) < 1.5
    assert m.overlap > 0.5


def test_assemble_four_positions():
    names = ["pos1", "pos2", "pos3", "pos4"]
    scans = [sim(TRUE_POSES[n], k).filtered() for k, n in enumerate(names)]
    poses, groups, _ = assemble(scans, log=lambda *a: None)
    assert len(groups) == 1
    ref = groups[0][0]
    for k, n in enumerate(names):
        t = rel(TRUE_POSES[names[ref]], TRUE_POSES[n])
        assert np.hypot(poses[k].x - t.x, poses[k].y - t.y) < 0.12, n
        assert abs((np.degrees(poses[k].theta - t.theta) + 180) % 360 - 180) < 2.0, n


def test_assemble_successif_four_positions():
    from carto.register import assemble_successif
    names = ["pos1", "pos2", "pos3", "pos4"]
    scans = [sim(TRUE_POSES[n], k).filtered() for k, n in enumerate(names)]
    poses, groups, _ = assemble_successif(scans, log=lambda *a: None)
    # positions éloignées, sans ordre de trajet : un scan sans recalage sûr reste non placé
    # (signalé) plutôt que d'être placé faux ; ceux qui sont placés doivent être justes
    assert groups[0][0] == 0 and len(groups[0]) >= 3    # le premier scan fixe le repère
    for k in groups[0]:
        n = names[k]
        t = rel(TRUE_POSES["pos1"], TRUE_POSES[n])
        assert np.hypot(poses[k].x - t.x, poses[k].y - t.y) < 0.12, n
        assert abs((np.degrees(poses[k].theta - t.theta) + 180) % 360 - 180) < 2.0, n


def test_assemble_successif_salle_symetrique():
    """Salle d'exercice presque symétrique : sans le test d'ambiguïté, le scan 2 se
    plaçait retourné de 180°. Les 8 scans doivent être placés à moins de 10 cm / 1°."""
    from carto.register import assemble_successif
    from carto.simulate import EXERCISE_POSES, ROOM_EXERCISE
    rng = np.random.default_rng(3)
    scans = []
    for p in EXERCISE_POSES:
        ang = np.radians(np.arange(0, 360, 0.8))
        r = raycast(p, ang, walls=ROOM_EXERCISE)
        r = np.where(r > 0, r + rng.normal(0, 0.03, len(r)), 0)
        scans.append(clean_scan(Scan("s", ang, r, np.zeros(len(r)))))
    poses, groups, _ = assemble_successif(scans, log=lambda *a: None)
    assert len(groups) == 1
    for k, p in enumerate(EXERCISE_POSES):
        t = rel(EXERCISE_POSES[0], p)
        assert np.hypot(poses[k].x - t.x, poses[k].y - t.y) < 0.10, k + 1
        assert abs((np.degrees(poses[k].theta - t.theta) + 180) % 360 - 180) < 1.0, k + 1


def test_assemble_successif_trajectoire_robot():
    """Scans pris en roulant (pas de 30 cm) : chaque scan part de la pose du précédent
    (recalage local), tous sont placés, dérive limitée."""
    from carto.register import assemble_successif
    from carto.simulate import ROOM_EXERCISE
    rng = np.random.default_rng(5)
    P, x, y, t = [], 1.2, 1.0, 0.0
    for wx, wy in [(5.8, 1.0), (6.0, 4.2), (1.4, 4.2)]:
        while np.hypot(wx - x, wy - y) > 0.3:
            a = np.arctan2(wy - y, wx - x)
            t += np.clip((a - t + np.pi) % (2 * np.pi) - np.pi, -0.2, 0.2)
            x, y = x + 0.3 * np.cos(a), y + 0.3 * np.sin(a)
            P.append(Pose(x, y, t))
    scans = []
    for p in P:
        ang = np.radians(np.arange(0, 360, 0.8))
        r = raycast(p, ang, walls=ROOM_EXERCISE)
        r = np.where(r > 0, r + rng.normal(0, 0.03, len(r)), 0)
        scans.append(clean_scan(Scan("s", ang, r, np.zeros(len(r)))))
    poses, groups, _ = assemble_successif(scans, log=lambda *a: None)
    assert len(groups) == 1
    err = [np.hypot(poses[k].x - rel(P[0], P[k]).x, poses[k].y - rel(P[0], P[k]).y) for k in range(len(P))]
    assert max(err) < 0.20
