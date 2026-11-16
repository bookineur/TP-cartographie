"""Localisation GLOBALE d'un scan : retrouver où le robot était, sans aucune pose initiale.

Protocole écrit avant la mesure : resultats/localisation_globale/version_1/PROTOCOLE.md.

  1. candidats : corrélation FFT du scan avec les points de la référence, tous les 2° sur 360° ;
     les 8 meilleurs candidats distincts (> 0,6 m ou > 20° entre eux) ;
  2. affinage de chaque candidat sur la référence (méthodes du Jour 2) : multi-résolution
     (±0,3 m, ±6°) puis Gauss-Newton ;
  3. choix : la plus grande part p de points à moins de 10 cm de la référence ;
  4. acceptation (règles de Lidar Lab) : p ≥ 35 % et aucun rival éloigné (> 0,6 m ou > 0,4 rad)
     dont la part est ≥ p − 2·√(p(1−p)/N). Sinon : refus.

Lancer : python -m carto.localisation_globale [dossier_sortie]
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

from carto import localisation as L
from carto.gridmap import build_grid
from carto.register import _ANGLE_BATCH, _fast_len, _field, clean_scan
from carto.scan import Pose, load_poses, load_scans
from carto.vectormap import build_vector_map

SESSION = Path("data/mesures_phase19_2026-11-09/carte_autoslam_v1/session_assemblee")
SAME_MARK = 0.15        # même repère au sol (règle du Jour 2)
N_CAND = 8
CAND_XY, CAND_TH = 0.6, np.radians(20)
RIVAL_XY, RIVAL_TH = 0.6, 0.4
INLIER = 0.10
MIN_P = 0.35


def _num(name):
    return int("".join(c for c in name if c.isdigit()) or 0)


def _angdiff(a, b):
    return abs((a - b + np.pi) % (2 * np.pi) - np.pi)


def reference_points(ref) -> np.ndarray:
    """Points de la référence pour la corrélation : cellules occupées, ou points tous les 2 cm
    le long des segments."""
    if isinstance(ref, L.GridRef):
        return ref.occ_xy
    pts = []
    for s in ref.segments:
        n = max(2, int(np.ceil(np.linalg.norm(s.p2 - s.p1) / 0.02)) + 1)
        t = np.linspace(0, 1, n)[:, None]
        pts.append(s.p1 + t * (s.p2 - s.p1))
    return np.vstack(pts)


def global_candidates(a_pts, b_local, res=0.10, step_deg=2.0, max_pts=400, n=N_CAND):
    """Meilleure translation pour chaque angle (FFT), puis les n meilleurs candidats distincts."""
    rng = np.random.default_rng(0)
    b = b_local if len(b_local) <= max_pts else b_local[rng.choice(len(b_local), max_pts, replace=False)]
    field, lo = _field(a_pts, res, margin=np.abs(b).max() + 0.5)
    H, W = field.shape
    Hf, Wf = _fast_len(H), _fast_len(W)
    padded = np.zeros((Hf, Wf))
    padded[:H, :W] = field
    F = np.fft.rfft2(padded)
    found = []
    thetas = np.radians(np.arange(0, 360, step_deg))
    for start in range(0, len(thetas), _ANGLE_BATCH):
        ths = thetas[start:start + _ANGLE_BATCH]
        imgs = np.zeros((len(ths), Hf, Wf))
        for k, th in enumerate(ths):
            c, s = np.cos(th), np.sin(th)
            ci = np.round(b @ np.array([[c, s], [-s, c]]) / res).astype(int)
            np.add.at(imgs[k], (ci[:, 1] % Hf, ci[:, 0] % Wf), 1.0)
        corr = np.fft.irfft2(F * np.conj(np.fft.rfft2(imgs)), s=(Hf, Wf))[:, :H, :W]
        for k, th in enumerate(ths):
            j = int(np.argmax(corr[k]))
            iy, ix = divmod(j, W)
            tx, ty = lo + (np.array([ix, iy]) + 0.5) * res
            found.append((corr[k].flat[j], Pose(float(tx), float(ty), float(th))))
    found.sort(key=lambda r: -r[0])
    keep = []
    for _, p in found:
        if all(np.hypot(p.x - q.x, p.y - q.y) > CAND_XY or _angdiff(p.theta, q.theta) > CAND_TH for q in keep):
            keep.append(p)
        if len(keep) == n:
            break
    return keep


def inlier_fraction(ref, local, pose: Pose) -> float:
    return float(np.mean(ref.distance(pose.transform(local)) < INLIER))


def localise_global(ref, local):
    t0 = time.perf_counter()
    cands = global_candidates(reference_points(ref), local)
    refined = []
    for c in cands:
        p = L.multi_resolution(ref, local, c, half_xy=0.3, half_th_deg=6.0).pose
        p = L.gauss_newton(ref, local, p).pose
        refined.append((inlier_fraction(ref, local, p), p))
    refined.sort(key=lambda r: -r[0])
    p_best, best = refined[0]
    N = len(local)
    pc = min(max(p_best, 0.05), 0.95)
    bound = p_best - 2 * np.sqrt(pc * (1 - pc) / N)
    rivals = [(q, r) for q, r in refined[1:]
              if np.hypot(r.x - best.x, r.y - best.y) > RIVAL_XY or _angdiff(r.theta, best.theta) > RIVAL_TH]
    rival = max((q for q, _ in rivals), default=0.0)
    if p_best < MIN_P:
        decision = "refus (recouvrement)"
    elif rival >= bound:
        decision = "refus (ambiguïté)"
    else:
        decision = "accepté"
    return {"pose": best, "p": p_best, "rival": rival, "borne": bound, "decision": decision,
            "temps_s": time.perf_counter() - t0, "candidats": [(q, r.as_list_deg()) for q, r in refined]}


def classify(dxy, dth_deg, accepted):
    if not accepted:
        return "refusé"
    if dxy < 0.10 and dth_deg < 2:
        return "concordant"
    if dxy < 0.30 and dth_deg < 5:
        return "proche"
    return "faux positif"


def run(out: Path, session: Path = SESSION, log=print):
    out.mkdir(parents=True, exist_ok=True)
    truth = load_poses(session / "poses.json")
    files = sorted(session.glob("scan*.csv"), key=lambda f: _num(f.stem))
    scans = {s.name: clean_scan(s) for s in load_scans(files) if s.name in truth}
    names = sorted(scans, key=_num)
    rows = []
    for n in names:
        t = truth[n]
        others = [m for m in names if np.hypot(truth[m].x - t.x, truth[m].y - t.y) >= SAME_MARK]
        pairs = [(scans[m], truth[m]) for m in others]
        t_build = time.perf_counter()
        refs = {"grid map": L.GridRef(build_grid(pairs, 0.05)),
                "carte vectorielle": L.VectorRef(build_vector_map(pairs).segments)}
        t_build = time.perf_counter() - t_build
        local = scans[n].local_xy()
        for kind, ref in refs.items():
            r = localise_global(ref, local)
            p = r["pose"]
            dxy = float(np.hypot(p.x - t.x, p.y - t.y))
            dth = float(np.degrees(_angdiff(p.theta, t.theta)))
            cls = classify(dxy, dth, r["decision"] == "accepté")
            rows.append({"scan": n, "reference": kind, "n_exclus": len(names) - len(others),
                         "points": len(local), "decision": r["decision"], "classe": cls,
                         "ecart_m": round(dxy, 4), "ecart_deg": round(dth, 2), "p": round(r["p"], 3),
                         "rival": round(r["rival"], 3), "borne": round(r["borne"], 3),
                         "x": round(p.x, 4), "y": round(p.y, 4), "theta_deg": round(float(np.degrees(p.theta)), 2),
                         "temps_s": round(r["temps_s"], 2), "construction_cartes_s": round(t_build, 1)})
            log(f"{n:7s} {kind:17s} {r['decision']:22s} {cls:12s} écart {dxy*100:7.1f} cm {dth:6.1f}°  "
                f"p={r['p']:.2f} rival={r['rival']:.2f}  {r['temps_s']:.1f} s")
    with open(out / "resultats.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        w.writerows(rows)
    (out / "resultats.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), "utf-8")
    return rows


if __name__ == "__main__":
    run(Path(sys.argv[1] if len(sys.argv) > 1 else "resultats/localisation_globale/version_1"))
