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
