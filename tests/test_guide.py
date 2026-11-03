import numpy as np
import pytest

from carto.gridmap import OccupancyGrid
from carto.guide import (ERROR, OK, WARN, live_check, overlap_ratio, refine_pose, scan_quality, suggest_next,
                         theta_aligned_on_walls)
from carto.scan import Pose, Scan
from carto.simulate import TRUE_POSES, raycast
from ld06.sources import ArduinoCSVAssembler, classify_stream


def sim(pose, noise=0.03, seed=0, n=450):
    rng = np.random.default_rng(seed)
    ang = np.radians((np.arange(n) * 360 / n + rng.uniform(0, 0.8)) % 360)
    r = raycast(pose, ang)
    r = np.where(r > 0, r + rng.normal(0, noise, n), 0)
    return Scan("s", ang, r, np.full(n, 200.0), {"speed_dps": "3600"})


def test_quality_good_and_moved():
    p = TRUE_POSES["pos1"]
    rep = scan_quality([sim(p, seed=k) for k in range(3)])
    assert rep.level == OK, rep.messages
    moved = Pose(p.x + 0.3, p.y, p.theta + 0.2)
    assert scan_quality([sim(p), sim(moved, seed=1)]).level == ERROR


def test_quality_incomplete_and_masked():
    s = sim(TRUE_POSES["pos1"], n=250)
    assert scan_quality([s]).level == ERROR
    s = sim(TRUE_POSES["pos1"])
    s.ranges[:200] = 0
    assert scan_quality([s]).level == ERROR
    s = sim(TRUE_POSES["pos1"])
    s.ranges[:20] = 0.08
    assert any("15 cm" in t for lvl, t in scan_quality([s]).messages if lvl == WARN)


def test_overlap_and_refine():
    p1, p3 = TRUE_POSES["pos1"], TRUE_POSES["pos3"]
    g = OccupancyGrid.from_scan(sim(p1).filtered(), p1)
    s3 = sim(p3, seed=3)
    good = overlap_ratio(g, s3, p3)
    wrong = Pose(p3.x + 0.25, p3.y - 0.2, p3.theta + np.radians(6))
    bad = overlap_ratio(g, s3, wrong)
    assert good > 0.3 and bad < good
    new, before, after = refine_pose(g, s3, wrong)
    assert after > before
    assert np.hypot(new.x - p3.x, new.y - p3.y) < 0.08
    assert abs(np.degrees(new.theta - p3.theta)) < 1.0


def test_suggest_points_to_unseen_area():
    p1 = TRUE_POSES["pos1"]  # pièce de gauche (x < 3) : la partie droite n'est vue que par la porte
    g = OccupancyGrid.from_scan(sim(p1).filtered(), p1)
    sug = suggest_next(g, [p1])
    assert sug
    assert any(s.x > 2.5 for s in sug)   # vers la porte / la pièce de droite
    # la salle vue depuis les 4 positions : beaucoup moins de frontière
    for name in ("pos2", "pos3", "pos4"):
        g.update(sim(TRUE_POSES[name]).filtered(), TRUE_POSES[name])
    after = sum(s.frontier_m for s in suggest_next(g, list(TRUE_POSES.values())))
    assert after < sum(s.frontier_m for s in sug)


def test_theta_aligned_on_walls():
    true = TRUE_POSES["pos1"]                     # salle aux murs parallèles aux axes
    s = sim(true)
    for err in (-20, -4, 7, 30):
        guess = true.theta + np.radians(err)
        th = theta_aligned_on_walls(s, guess)
        assert th is not None
        assert abs(np.degrees(th - true.theta)) < 1.0, err


def test_live_check_and_stream_detection():
    assert live_check(sim(TRUE_POSES["pos1"])) == []
    bad = sim(TRUE_POSES["pos1"], n=200)
    assert any(l == ERROR for l, _ in live_check(bad))
    from ld06.protocol import Packet, encode_packet
    csv = b"N,Angle(\xc2\xb0),Distance(mm),Intensity,x(mm),y(mm)\r\n" + b"".join(
        f"{i},{i * 0.8:.2f},1000,200,0,0\r\n".encode() for i in range(20))
    raw = b"\x00\x12" + encode_packet(Packet(3600, 10.0, 18.0, [1000] * 12, [200] * 12, 0)) * 3
    assert classify_stream(csv, b"") == "arduino"
    assert classify_stream(b"\x54\x2c\xff\x00garbage", raw) == "raw"
    assert classify_stream(b"", b"\x01\x02\x03" * 100) is None


def test_teleplot_parsing_and_mirror():
    from ld06.sources import TextSerialSource, parse_teleplot_line, xy_mm_to_scan
    assert parse_teleplot_line(">speed:3600") == ("var", "speed", 3600.0)
    assert parse_teleplot_line(">t:1627551892437:12.5") == ("var", "t", 12.5)
    kind, name, pts = parse_teleplot_line(">lidar:1000:0;0:-2000;-1500:0;|xy")
    assert kind == "xy" and name == "lidar" and pts == [(1000, 0), (0, -2000), (-1500, 0)]
    assert parse_teleplot_line("0,0.50,623,12,622,5") is None
    # la librairie : y = -d·sin(angle_trigo) -> un point à 90° trigo (à gauche) arrive avec y < 0
    s = xy_mm_to_scan([(0, -2000)], mirror=True)
    assert s["angle_deg"][0] == pytest.approx(90) and s["distance_mm"][0] == pytest.approx(2000)
    # source texte : Teleplot + variables + CSV mélangés
    src, asm = TextSerialSource("COMX"), ArduinoCSVAssembler()
    line = ">lidar:" + ";".join(f"{1000 * np.cos(a):.0f}:{-1000 * np.sin(a):.0f}"
                                for a in np.radians(np.arange(0, 360, 1.0))) + ";|xy"
    for l in [">speed:3600", line, "N,Angle(°),Distance(mm),Intensity,x(mm),y(mm)"] + \
             [f"{i},{i * 0.8:.2f},1500,200,0,0" for i in range(60)] + [""]:
        src.feed_line(l, asm)
    assert src.variables == {"speed": 3600.0}
    a, b = src.queue.get_nowait(), src.queue.get_nowait()
    assert len(a["angle_deg"]) == 360 and np.allclose(a["distance_mm"], 1000, atol=1)
    assert a["angle_deg"][90] == pytest.approx(90, abs=0.2)
    assert len(b["angle_deg"]) == 60 and src.formats_seen == {"Teleplot", "CSV"}


def test_arduino_csv_assembler():
    asm = ArduinoCSVAssembler()
    lines = ["N,Angle(°),Distance(mm),Intensity,x(mm),y(mm)"]
    lines += [f"{i},{i * 0.8:.2f},1000,200,0,0" for i in range(60)] + [""]
    lines += [f"{i},{i * 0.8:.2f},2000,200,0,0" for i in range(30)] + [""]  # trop court -> ignoré
    out = [s for s in (asm.feed_line(l) for l in lines) if s]
    assert len(out) == 1 and len(out[0]["angle_deg"]) == 60
