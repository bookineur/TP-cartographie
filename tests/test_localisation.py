import numpy as np
import pytest

from carto import localisation as L
from carto.evaluation import perturb, sim_scan
from carto.gridmap import build_grid
from carto.scan import Pose
from carto.segments import Segment
from carto.simulate import ROOM, TRUE_POSES


@pytest.fixture(scope="module")
def setup():
    rng = np.random.default_rng(3)
    pairs = [(sim_scan(p, rng), p) for p in TRUE_POSES.values()]
    truth = Pose(2.0, 3.0, np.radians(40))
    local = sim_scan(truth, rng).local_xy()
    p_ref = TRUE_POSES["pos2"]
    refs = {"grid": L.GridRef(build_grid(pairs, 0.05)),
            "vector": L.VectorRef([Segment(a, b) for a, b in ROOM]),
            "cloud": L.CloudRef(sim_scan(p_ref, rng).world_xy(p_ref))}
    return refs, local, truth


def _err(r, truth):
    return np.hypot(r.pose.x - truth.x, r.pose.y - truth.y), np.degrees(abs(L.wrap(r.pose.theta - truth.theta)))


@pytest.mark.parametrize("kind", ["grid", "vector", "cloud"])
@pytest.mark.parametrize("method", list(L.METHODS))
def test_every_method_finds_the_pose(setup, kind, method):
    refs, local, truth = setup
    init = perturb(truth, (0.2, 8.0), np.random.default_rng(0))
    e_xy, e_th = _err(L.localise(refs[kind], local, init, method), truth)
    assert e_xy < 0.05 and e_th < 2.0


def test_vector_distance_is_exact():
    ref = L.VectorRef([Segment((0, 0), (2, 0))])
    d, g = ref.query(np.array([[1.0, 0.3], [3.0, 0.0], [-0.5, -0.5]]))
    assert np.allclose(d, [0.3, 1.0, np.sqrt(0.5)], atol=1e-9)
    assert np.allclose(g[0], [0, 1])


def test_grid_distance_and_gradient():
    from carto.gridmap import OccupancyGrid
    g = OccupancyGrid(0.05, (0, 0), (40, 40))
    g.logodds[:, 20] = 2.0  # mur vertical, centre des cellules à x = 1,025
    ref = L.GridRef(g)
    d, grad = ref.query(np.array([[1.325, 1.0]]))
    assert d[0] == pytest.approx(0.30, abs=1e-6) and np.allclose(grad[0], [1, 0])


def test_direct_methods_are_close_on_easy_cases(setup):
    refs, local, truth = setup
    init = perturb(truth, (0.1, 5.0), np.random.default_rng(1))
    e_xy, e_th = _err(L.direct_murs(refs["vector"], local, init), truth)
    assert e_xy < 0.10 and e_th < 1.0
    # moments géométriques : exact quand les deux nuages sont les mêmes
    rng = np.random.default_rng(2)
    pts = sim_scan(truth, rng).local_xy()
    ref = L.CloudRef(truth.transform(pts))
    e_xy, e_th = _err(L.direct_moments(ref, pts, Pose(truth.x + 0.3, truth.y, truth.theta + 0.1)), truth)
    assert e_xy < 1e-6 and e_th < 1e-4


def test_covariance_is_small_at_true_pose(setup):
    refs, local, truth = setup
    s = L.pose_covariance(refs["vector"], local, truth)
    assert s[0] < 0.01 and s[1] < 0.01 and np.degrees(s[2]) < 0.5


def test_robotcontrol_csv_is_read_in_meters(tmp_path):
    from carto.scan import load_scan_file
    f = tmp_path / "lidar_scan.csv"
    f.write_text("# Robot position: x=1.2000m, y=0.5000m, theta=90.00deg\nangle_deg,distance_m,intensity\n"
                 "0.000,1.5000,200\n90.000,2.2500,180\n", encoding="utf-8")
    (s,) = load_scan_file(f)
    assert s.meta["format"] == "robotcontrol" and np.allclose(s.ranges, [1.5, 2.25])
    assert np.allclose(s.intensities, [200, 180]) and s.meta["robot_pose"].as_list_deg() == [1.2, 0.5, 90.0]


def test_load_reference_formats(tmp_path):
    v = tmp_path / "vector_map.txt"
    v.write_text("# carte\nx1,y1,x2,y2\n0,0,2,0\n2,0,2,2\n", encoding="utf-8")
    ref = L.load_reference(v)
    assert isinstance(ref, L.VectorRef) and len(ref.segments) == 2
    c = tmp_path / "segments.csv"
    c.write_text("x1,y1,x2,y2,length,n_obs\n0,0,1,0,1,3\n", encoding="utf-8")
    assert isinstance(L.load_reference(c), L.VectorRef)


def test_selection_parser():
    from carto.evaluation import parse_selection
    assert parse_selection("1-3,7") == {1, 2, 3, 7} and parse_selection("") is None


def test_real_dataset_excludes_same_mark(tmp_path):
    """Les captures faites au même repère ne doivent pas entrer dans la carte du scan testé."""
    from carto.evaluation import real_dataset
    from carto.simulate import simulate_tp2_session
    out = simulate_tp2_session(tmp_path / "s", n_marks=4, repeats=2, seed=3)
    refs, cases, loaded, truth, repeats = real_dataset(out, out / "poses.json", log=lambda *a: None)
    assert len(repeats) == 4 and len(loaded) == 8
    for kind, key, local, pose in cases:
        if kind == "grid":
            same = [n for n in truth if n != key and np.hypot(truth[n].x - pose.x, truth[n].y - pose.y) < 0.15]
            assert same  # chaque scan a un jumeau au même repère…
    # la paire (scan1, scan2) est reconnue comme répétition, pas comme scan de référence voisin
    assert ("scan1", "scan2") in repeats
    assert all(not k.startswith("scan1->scan2") for k in refs["cloud"])


def test_same_mark_ignores_angle_and_wilson():
    from carto.evaluation import _same_mark, wilson
    assert _same_mark(Pose(1, 1, 0), Pose(1.05, 1, np.radians(90)))   # robot tourné sur le même repère
    assert not _same_mark(Pose(1, 1, 0), Pose(1.3, 1, 0))
    lo, hi = wilson(10, 16)
    assert 0.35 < lo < 0.42 and 0.80 < hi < 0.86
