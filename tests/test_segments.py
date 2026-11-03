import numpy as np
import pytest

from carto.segments import (TOL, Segment, angle_between, are_close, cut, extract_segments,
                            intersection, merge)


def S(x1, y1, x2, y2):
    return Segment((x1, y1), (x2, y2))


def same(a: Segment, b: Segment, tol=1e-9):
    return np.allclose(a.p1, b.p1, atol=tol) and np.allclose(a.p2, b.p2, atol=tol)


# ---------------------------------------------------------------- angle
def test_angle_lines_and_oriented():
    h, v = S(0, 0, 1, 0), S(0, 0, 0, 1)
    assert angle_between(h, v) == pytest.approx(np.pi / 2)
    assert angle_between(h, S(1, 0, 0, 0)) == pytest.approx(0)          # sens opposé = même droite
    assert angle_between(h, S(0, 0, 1, 1)) == pytest.approx(np.pi / 4)
    assert angle_between(h, S(0, 0, -1, 1)) == pytest.approx(np.pi / 4)  # 135° -> 45° entre droites
    assert angle_between(h, v, oriented=True) == pytest.approx(np.pi / 2)
    assert angle_between(v, h, oriented=True) == pytest.approx(-np.pi / 2)


# ---------------------------------------------------------------- proches
def test_are_close():
    a = S(0, 0, 2, 0)
    assert are_close(a, S(2.05, 0.01, 4, 0.02))           # aligné, petit trou
    assert not are_close(a, S(2.5, 0, 4, 0))              # trou trop grand
    assert not are_close(a, S(0, 0.3, 2, 0.3))            # parallèle mais décalé
    assert not are_close(a, S(0, 0, 2, 0.5))              # angle trop grand
    assert are_close(a, S(1, 0.02, 3, 0.03))              # recouvrement


def test_merge():
    m = merge(S(0, 0, 2, 0), S(1.5, 0, 4, 0))
    assert same(m, S(0, 0, 4, 0))
    m = merge(S(0, 0, 2, 0), S(4, 0, 1, 0))                # sens opposé : on garde celui de s1
    assert same(m, S(0, 0, 4, 0))
    assert m.n_obs == 2


# ---------------------------------------------------------------- intersection
def test_intersection_basic():
    x = intersection(S(0, 0, 2, 0), S(1, -1, 1, 1))
    assert np.allclose(x, (1, 0))
    assert intersection(S(0, 0, 2, 0), S(3, -1, 3, 1)) is None    # hors du 1er segment
    assert intersection(S(0, 0, 2, 0), S(0, 1, 2, 1)) is None     # parallèles
    assert intersection(S(0, 0, 2, 0), S(1, 0, 3, 0)) is None     # colinéaires
    assert np.allclose(intersection(S(0, 0, 2, 0), S(2, 0, 2, 1)), (2, 0))  # extrémités qui se touchent


def test_intersection_tolerance():
    # le "cutter" s'arrête à 0.5 µm de la cible : dans la tolérance -> intersection
    assert intersection(S(0, 0, 2, 0), S(1, 1, 1, 0.5 * TOL)) is not None
    assert intersection(S(0, 0, 2, 0), S(1, 1, 1, 2 * TOL)) is None


# ---------------------------------------------------------------- découpe
T = S(0, 0, 10, 0)


def test_cut_keeps_longest_side():
    r, done = cut(T, S(3, -1, 3, 1))
    assert done and same(r, S(3, 0, 10, 0))
    r, done = cut(T, S(7, -1, 7, 1))
    assert done and same(r, S(0, 0, 7, 0))


def test_cut_no_intersection():
    r, done = cut(T, S(12, -1, 12, 1))
    assert not done and r is T
    r, done = cut(T, S(5, 0.5, 5, 2))        # coupe la droite mais pas le segment cutter
    assert not done


def test_cut_at_endpoint_of_target_changes_nothing():
    for cutter in (S(0, -1, 0, 1), S(10, -1, 10, 1), S(10 - 0.5 * TOL, -1, 10 - 0.5 * TOL, 1)):
        r, done = cut(T, cutter)
        assert not done and same(r, T)


def test_cut_just_inside_tolerance_cuts():
    r, done = cut(T, S(10 - 2 * TOL, -1, 10 - 2 * TOL, 1))
    assert done and same(r, S(0, 0, 10 - 2 * TOL, 0))


def test_cut_by_endpoint_of_cutter():
    # T-jonction : le cutter s'arrête pile sur la cible -> intersection sur les deux -> découpe
    r, done = cut(T, S(4, 1, 4, 0))
    assert done and same(r, S(4, 0, 10, 0))


def test_cut_collinear_or_parallel_not_cut():
    for cutter in (S(2, 0, 5, 0), S(-1, 0, 11, 0), S(2, 0.5, 5, 0.5), S(5, 0, 3, 0)):
        r, done = cut(T, cutter)
        assert not done and same(r, T)


def test_cut_equal_lengths_keeps_first_point_side():
    r, done = cut(T, S(5, -1, 5, 1))
    assert done and same(r, S(0, 0, 5, 0))
    # égalité à la tolérance près : toujours côté p1
    r, done = cut(T, S(5 + 0.4 * TOL, -1, 5 + 0.4 * TOL, 1))
    assert done and np.allclose(r.p1, (0, 0))
    r, done = cut(T, S(5 - 0.4 * TOL, -1, 5 - 0.4 * TOL, 1))
    assert done and np.allclose(r.p1, (0, 0))
    # et si on retourne le segment, c'est l'autre moitié géométrique qu'on garde
    r, done = cut(S(10, 0, 0, 0), S(5, -1, 5, 1))
    assert done and same(r, S(10, 0, 5, 0))


def test_cut_oblique():
    r, done = cut(S(0, 0, 4, 4), S(0, 3, 3, 0))    # croisement en (1.5, 1.5)
    assert done and same(r, S(1.5, 1.5, 4, 4))


# ---------------------------------------------------------------- extraction
def test_extract_square_room():
    rng = np.random.default_rng(1)
    # pièce carrée 4x4 vue du centre, points ordonnés par angle
    ang = np.linspace(-np.pi, np.pi, 720, endpoint=False)
    d = np.column_stack([np.cos(ang), np.sin(ang)])
    t = 2.0 / np.max(np.abs(d), axis=1)
    pts = d * t[:, None] + rng.normal(0, 0.01, (len(ang), 2))
    segs = extract_segments(pts)
    assert len(segs) == 4
    for s in segs:
        assert s.length == pytest.approx(4.0, abs=0.15)
        assert min(s.orientation % (np.pi / 2), np.pi / 2 - s.orientation % (np.pi / 2)) < np.radians(2)
