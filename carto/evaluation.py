"""Banc d'évaluation de la localisation (TP Jour 2, « Comparez les méthodes »).

Mêmes scans et mêmes poses initiales pour toutes les méthodes ; on mesure
l'erreur de position (m), l'erreur angulaire (°), le temps de calcul et le
taux de réussite, en faisant varier l'erreur de la pose initiale.

  Simulation (vérité terrain exacte) : salle de carto.simulate.
    - grid map et carte vectorielle construites à partir des 4 scans des
      positions pos1..pos4 (bruit 30 mm, comme la datasheet) ;
    - scans à localiser : 12 poses tirées au hasard dans la salle (à plus de
      40 cm des murs), scans simulés indépendamment (autre bruit) ;
    - entre scans : chaque scan pos1..pos4 sert de référence ; 3 scans pris à
      30 cm et ±10° de sa position (« pris près du scan de référence »).
  Réel (session de la salle) : référence = poses obtenues à l'assemblage
    (pas de mesure au mètre sur le robot) ; grid map et carte vectorielle
    construites SANS le scan testé (« leave-one-out ») ; entre scans : chaque
    scan contre son plus proche voisin.

    python -m carto evaluer [--reel data/salle_2026-11-02_18h31] [--rapide]
"""
from __future__ import annotations

import csv
import json
import time
from pathlib import Path

import numpy as np

from carto import localisation as L
from carto.gridmap import build_grid
from carto.scan import Pose, Scan
from carto.simulate import ROOM, TRUE_POSES, raycast
from carto.vectormap import build_vector_map

# Seuils de réussite (explicités dans le rapport) :
#  5 cm  ~ 1 cellule de la grid map, ~1,5 x la précision du LD06 (30 mm) ;
#  2°    -> à 3 m, un mur est décalé de 10 cm : au-delà la carte « bave ».
SUCCESS_XY, SUCCESS_TH = 0.05, 2.0
# Erreur de la pose initiale : distance (m) dans une direction au hasard,
# angle (°) de signe au hasard. Même tirage pour toutes les méthodes.
INIT_LEVELS = [(0.05, 2.0), (0.10, 5.0), (0.20, 8.0), (0.35, 12.0), (0.50, 20.0)]
STANDARD_LEVEL = 2  # (0,20 m ; 8°) : erreur typique d'une pose estimée à l'œil / odométrie
# Convergence : la méthode, partie d'une pose fausse, retombe-t-elle sur la pose
# qu'ELLE trouve en partant de la pose de référence ? Ne dépend pas de la
# précision de la référence (mètre ruban) : c'est ce qui mesure vraiment la
# sensibilité à l'initialisation. Tolérance plus large pour la brute force,
# dont le résultat est arrondi à son pas (4 cm, 1,5°).
CONV_TOL = {"brute force": (0.04, 1.5)}
CONV_DEFAULT = (0.02, 1.0)


# ===================================================================== données
def sim_scan(pose: Pose, rng, n=450, noise=0.03, dropout=0.02) -> Scan:
    ang = np.radians((np.arange(n) * 360.0 / n + rng.uniform(0, 0.8)) % 360)
    r = raycast(pose, ang)
    r = r + rng.normal(0, noise, n) * (r > 0)
    r[rng.random(n) < dropout] = 0.0
    return Scan("sim", ang, r, np.full(n, 200.0)).filtered()


def _wall_clearance(x, y):
    p = np.array([x, y])
    return min(_seg_dist(p, np.array(a, float), np.array(b, float)) for a, b in ROOM)


def _seg_dist(p, a, b):
    ab = b - a
    t = np.clip((p - a) @ ab / (ab @ ab), 0, 1)
    return float(np.hypot(*(p - a - t * ab)))


def _inside_room(x, y):
    in_l = (0 < x < 8 and 0 < y < 3.5) or (0 < x < 5 and 0 < y < 6)
    pillar = 6.2 <= x <= 6.8 and 1.2 <= y <= 1.8
    return in_l and not pillar


def random_room_poses(n, rng, clearance=0.4):
    out = []
    while len(out) < n:
        x, y = rng.uniform(0, 8), rng.uniform(0, 6)
        if _inside_room(x, y) and _wall_clearance(x, y) >= clearance:
            out.append(Pose(x, y, rng.uniform(-np.pi, np.pi)))
    return out


def perturb(pose: Pose, level, rng) -> Pose:
    # amplitude entre 75 et 100 % du niveau : évite que l'erreur tombe pile sur
    # un multiple du pas des recherches exhaustives (résultat artificiellement exact)
    d, a = level[0] * rng.uniform(0.75, 1), level[1] * rng.uniform(0.75, 1)
    phi = rng.uniform(0, 2 * np.pi)
    return Pose(pose.x + d * np.cos(phi), pose.y + d * np.sin(phi), pose.theta + np.radians(a) * rng.choice([-1, 1]))


def sim_dataset(seed=0, n_map_cases=12, n_per_ref=3):
    """-> (références, cas) ; un cas = (type de réf, clé de réf, scan local, vraie pose)."""
    rng = np.random.default_rng(seed)
    pairs = [(sim_scan(p, rng), p) for p in TRUE_POSES.values()]
    refs = {"grid": {"carte": L.GridRef(build_grid(pairs, 0.05))},
            "vector": {"carte": L.VectorRef(build_vector_map(pairs).segments)},
            "cloud": {}, "cloud_l": {}}
    cases = []
    for p in random_room_poses(n_map_cases, rng):
        s = sim_scan(p, rng).local_xy()
        cases.append(("grid", "carte", s, p))
        cases.append(("vector", "carte", s, p))
    for name, p_ref in TRUE_POSES.items():
        ref_pts = sim_scan(p_ref, rng).world_xy(p_ref)
        refs["cloud"][name] = L.CloudRef(ref_pts)
        refs["cloud_l"][name] = L.CloudRef(ref_pts, point_to_line=True)
        k = 0
        while k < n_per_ref:
            phi = rng.uniform(0, 2 * np.pi)
            p = Pose(p_ref.x + 0.3 * np.cos(phi), p_ref.y + 0.3 * np.sin(phi),
                     p_ref.theta + np.radians(10) * rng.choice([-1, 1]))
            if not (_inside_room(p.x, p.y) and _wall_clearance(p.x, p.y) > 0.25):
                continue
            s = sim_scan(p, rng).local_xy()
            cases.append(("cloud", name, s, p))
            cases.append(("cloud_l", name, s, p))
            k += 1
    return refs, cases


REF_LABEL = {"grid": "grid map", "vector": "carte vectorielle",
             "cloud": "entre scans (point-à-point)", "cloud_l": "entre scans (point-à-droite)"}


def _methods(kind, ref):
    m = L.methods_for(ref)
    if kind == "cloud_l":  # variante point-à-droite : seules les méthodes locales changent vraiment
        m = {k: v for k, v in m.items() if k in ("Gauss-Newton", "ICP")}
    return m


# ==================================================================== exécution
def run(refs, cases, levels=INIT_LEVELS, draws=1, seed=1, log=print, dataset="simulation"):
    # pose « ancre » de chaque méthode : trouvée en partant de la pose de référence
    anchors = {}
    for ci, (kind, key, local, truth) in enumerate(cases):
        for name, f in _methods(kind, refs[kind][key]).items():
            anchors[(ci, name)] = f(refs[kind][key], local, truth).pose
    rows = []
    for li, level in enumerate(levels):
        for ci, (kind, key, local, truth) in enumerate(cases):
            ref = refs[kind][key]
            for k in range(draws):
                # graine identique pour toutes les méthodes -> MÊME pose initiale
                # (les cas vont par deux : même scan sur grid map / carte vectorielle, ou point-à-point / point-à-droite)
                init = perturb(truth, level, np.random.default_rng([seed, li, ci // 2, k]))
                for name, f in _methods(kind, ref).items():
                    r = f(ref, local, init)
                    e_xy = float(np.hypot(r.pose.x - truth.x, r.pose.y - truth.y))
                    e_th = float(np.degrees(abs(L.wrap(r.pose.theta - truth.theta))))
                    a = anchors[(ci, name)]
                    tol = CONV_TOL.get(name, CONV_DEFAULT)
                    conv = (np.hypot(r.pose.x - a.x, r.pose.y - a.y) < tol[0]
                            and abs(np.degrees(L.wrap(r.pose.theta - a.theta))) < tol[1])
                    rows.append(dict(jeu=dataset, reference=REF_LABEL[kind], methode=name, cas=ci, scan=key, tirage=k,
                                     init_m=level[0], init_deg=level[1], err_m=e_xy, err_deg=e_th,
                                     temps_ms=r.time_s * 1000, score=r.score, poses_evaluees=r.n_eval,
                                     reussite=int(e_xy < SUCCESS_XY and e_th < SUCCESS_TH), convergence=int(conv)))
        log(f"  erreur initiale {level[0]:.2f} m / {level[1]:.0f}° : fait")
    return rows


# ========================================================================= réel
SAME_MARK = 0.15   # deux poses à moins de 15 cm : même repère au sol, QUEL QUE SOIT l'angle
                   # (un lidar 360° tourné sur place voit les mêmes points dans le repère de la salle)
NEAR_SCAN = 1.5            # entre scans : référence à 1,5 m au plus (« pris près »)


def parse_selection(text) -> set[int] | None:
    """« 1-9,12 » -> {1, ..., 9, 12} ; None ou "" -> tous."""
    if not text:
        return None
    out = set()
    for part in str(text).replace(" ", "").split(","):
        if "-" in part:
            lo, hi = part.split("-", 1)
            out |= set(range(int(lo), int(hi) + 1))
        elif part:
            out.add(int(part))
    return out


def _num(name):
    d = "".join(c for c in name if c.isdigit())
    return int(d) if d else 0


def _same_mark(p: Pose, q: Pose) -> bool:
    return bool(np.hypot(p.x - q.x, p.y - q.y) < SAME_MARK)


def real_dataset(session: Path, poses_file: Path, scans=None, log=print):
    """Cas de test sur une session réelle.
    - grid map et carte vectorielle construites SANS le scan testé ni les autres
      captures faites au même repère (sinon un scan presque identique serait
      dans la carte et la localisation serait faussement facile) ;
    - entre scans : référence = le scan le plus proche pris à un AUTRE repère,
      à moins de NEAR_SCAN m ;
    - paires de captures au même repère : servent à mesurer la répétabilité.
    `scans` : numéros à utiliser, ex. "1-9,12" (None = tous ceux qui ont une pose)."""
    from carto.register import clean_scan
    from carto.scan import load_poses, load_scans
    truth = load_poses(poses_file)
    sel = set(scans) if isinstance(scans, (set, range, list)) else parse_selection(scans)
    files = sorted(session.glob("scan*.csv"), key=lambda f: _num(f.stem))
    loaded = {s.name: clean_scan(s) for s in load_scans(files)
              if s.name in truth and (sel is None or _num(s.name) in sel)}
    names = sorted(loaded, key=_num)
    if len(names) < 2:
        raise SystemExit(f"Il faut au moins 2 scans avec une pose dans {poses_file} (trouvés : {names}).")
    if all((truth[n].x, truth[n].y, truth[n].theta) == (0, 0, 0) for n in names):
        raise SystemExit(f"Toutes les poses de {poses_file} valent (0, 0, 0) : saisissez les positions mesurées "
                         "dans Lidar Plot (éditeur de position) avant d'évaluer.")
    refs, cases, repeats = {"grid": {}, "vector": {}, "cloud": {}, "cloud_l": {}}, [], []
    for n in names:
        same = [m for m in names if _same_mark(truth[m], truth[n])]
        repeats += [(n, m) for m in same if _num(m) > _num(n)]
        others = [m for m in names if m not in same]
        if not others:
            log(f"  {n} : aucun scan pris à un autre repère, ignoré")
            continue
        pairs = [(loaded[m], truth[m]) for m in others]
        refs["grid"][n] = L.GridRef(build_grid(pairs, 0.05))
        refs["vector"][n] = L.VectorRef(build_vector_map(pairs).segments)
        local = loaded[n].local_xy()
        cases.append(("grid", n, local, truth[n]))
        cases.append(("vector", n, local, truth[n]))
        m = min(others, key=lambda m: np.hypot(truth[m].x - truth[n].x, truth[m].y - truth[n].y))
        if np.hypot(truth[m].x - truth[n].x, truth[m].y - truth[n].y) > NEAR_SCAN:
            log(f"  {n} : pas de scan de référence à moins de {NEAR_SCAN} m (localisation entre scans ignorée)")
            continue
        key = f"{n}->{m}"
        pts = loaded[m].world_xy(truth[m])
        refs["cloud"][key] = L.CloudRef(pts)
        refs["cloud_l"][key] = L.CloudRef(pts, point_to_line=True)
        cases.append(("cloud", key, local, truth[n]))
        cases.append(("cloud_l", key, local, truth[n]))
    return refs, cases, loaded, truth, repeats


def repeatability(loaded, truth, repeats):
    """Pour deux captures au même repère : pose trouvée par Gauss-Newton
    (point-à-droite, scan m comme référence) comparée à la pose saisie. Si le
    robot a été reposé sur le repère entre les deux, l'écart mesure la précision
    du placement (donc de la pose de référence) ; sinon, le bruit du lidar."""
    out = []
    for n, m in repeats:
        ref = L.CloudRef(loaded[m].world_xy(truth[m]), point_to_line=True)
        r = L.gauss_newton(ref, loaded[n].local_xy(), truth[n])
        out.append((n, m, float(np.hypot(r.pose.x - truth[n].x, r.pose.y - truth[n].y)),
                    float(np.degrees(abs(L.wrap(r.pose.theta - truth[n].theta)))), r.score))
    return out


def reference_uncertainty(refs, cases):
    """Écart-type (x, y, θ) des poses de référence du réel : approximation de
    Laplace autour de la pose assemblée, sur la carte vectorielle sans ce scan."""
    out = {}
    for kind, key, local, truth in cases:
        if kind == "vector":
            s = L.pose_covariance(refs[kind][key], local, truth)
            if s is not None:
                out[key] = (float(s[0]), float(s[1]), float(np.degrees(s[2])))
    return out


# ===================================================================== synthèse
def wilson(k, n, z=1.96):
    """Intervalle de confiance à 95 % d'une proportion k/n (Wilson) : avec 16 essais,
    10/16 = 62 % veut dire « entre 39 et 82 % »."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), min(1.0, c + h)


def _pct(rate, n, ci=True):
    lo, hi = wilson(round(rate * n), n)
    return f"{rate:.0%}" + (f" [{lo:.0%}–{hi:.0%}]" if ci else "")


def summarize(rows):
    """{(référence, méthode, niveau)} -> statistiques."""
    groups = {}
    for r in rows:
        groups.setdefault((r["reference"], r["methode"], (r["init_m"], r["init_deg"])), []).append(r)
    out = {}
    for k, g in groups.items():
        e, a = np.array([r["err_m"] for r in g]), np.array([r["err_deg"] for r in g])
        ok = np.array([r["reussite"] for r in g], bool)
        cv = np.array([r.get("convergence", 0) for r in g], bool)
        out[k] = dict(n=len(g), reussite=ok.mean(), convergence=cv.mean(),
                      mean_m=float(e.mean()), std_m=float(e.std()), mean_deg=float(a.mean()), std_deg=float(a.std()),
                      med_m=float(np.median(e)), p90_m=float(np.percentile(e, 90)),
                      med_deg=float(np.median(a)), p90_deg=float(np.percentile(a, 90)),
                      ok_m=float(np.median(e[ok])) if ok.any() else np.nan,
                      ok_deg=float(np.median(a[ok])) if ok.any() else np.nan,
                      temps_ms=float(np.mean([r["temps_ms"] for r in g])),
                      poses=float(np.mean([r["poses_evaluees"] for r in g])))
    return out


def _threshold_figure(rows, out: Path, tag, level, unc=None):
    """Part des essais dont l'écart est sous le seuil, en fonction du seuil
    (position et angle) : rend explicite le choix des seuils ; le palier montre
    l'incertitude de la référence."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    refs = [r for r in REF_LABEL.values() if any(x["reference"] == r for x in rows)]
    fig, axes = plt.subplots(2, len(refs), figsize=(4.4 * len(refs), 6.4), squeeze=False)
    tx, ta = np.linspace(0, 0.20, 201), np.linspace(0, 10, 201)
    for j, ref in enumerate(refs):
        for m in sorted({r["methode"] for r in rows if r["reference"] == ref}):
            g = [r for r in rows if r["reference"] == ref and r["methode"] == m and (r["init_m"], r["init_deg"]) == level]
            if not g:
                continue
            e = np.array([r["err_m"] for r in g]); a = np.array([r["err_deg"] for r in g])
            axes[0, j].plot(tx * 100, [(e < t).mean() * 100 for t in tx], label=m)
            axes[1, j].plot(ta, [(a < t).mean() * 100 for t in ta], label=m)
        for row, (thr, u, unit) in enumerate(((SUCCESS_XY * 100, unc and unc[0] * 100, "cm"), (SUCCESS_TH, unc and unc[1], "°"))):
            ax = axes[row, j]
            ax.axvline(thr, color="k", ls=":", lw=1)
            if u:
                ax.axvspan(0, u, color="tab:orange", alpha=0.12, label="incertitude de la référence")
            ax.set_xlabel(f"seuil ({unit})")
            ax.grid(alpha=0.3)
        axes[0, j].set_title(ref, fontsize=10)
        axes[0, j].legend(fontsize=7)
    axes[0, 0].set_ylabel("% d'essais sous le seuil (position)")
    axes[1, 0].set_ylabel("% d'essais sous le seuil (angle)")
    fig.suptitle(f"Taux de réussite selon le seuil choisi — départ {level[0]:.2f} m / {level[1]:.0f}° — {tag}")
    fig.tight_layout()
    fig.savefig(out / f"seuils_{tag}.png", dpi=120)
    plt.close(fig)


def _figures(rows, summ, out: Path, tag):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    refs = [r for r in REF_LABEL.values() if any(x["reference"] == r for x in rows)]
    lv = sorted({(r["init_m"], r["init_deg"]) for r in rows})
    fig, axes = plt.subplots(1, len(refs), figsize=(4.6 * len(refs), 4), sharey=True)
    for ax, ref in zip(np.atleast_1d(axes), refs):
        meths = sorted({r["methode"] for r in rows if r["reference"] == ref})
        for m in meths:
            ax.plot(range(len(lv)), [100 * summ[(ref, m, l)]["reussite"] for l in lv], "o-", label=m)
        ax.set_xticks(range(len(lv)), [f"{d:.2f} m\n{a:.0f}°" for d, a in lv], fontsize=8)
        ax.set_title(ref, fontsize=10)
        ax.set_xlabel("erreur de la pose initiale")
        ax.grid(alpha=0.3)
        ax.legend(fontsize=7)
    np.atleast_1d(axes)[0].set_ylabel(f"taux de réussite (%)  [< {SUCCESS_XY * 100:.0f} cm et < {SUCCESS_TH:.0f}°]")
    fig.suptitle(f"Sensibilité à la pose initiale — {tag}")
    fig.tight_layout()
    fig.savefig(out / f"sensibilite_{tag}.png", dpi=130)
    plt.close(fig)

    # précision vs temps, au niveau standard
    std = lv[min(STANDARD_LEVEL, len(lv) - 1)]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    marks = dict(zip(refs, "osD^"))
    for (ref, m, l), s in summ.items():
        if l != std:
            continue
        ax.scatter(s["temps_ms"], 100 * s["med_m"], marker=marks[ref], s=50)
        ax.annotate(f"{m}\n({ref.split(' (')[0]})" if "scan" in ref else f"{m}\n({ref})", (s["temps_ms"], 100 * s["med_m"]),
                    fontsize=6.5, xytext=(4, 2), textcoords="offset points")
    ax.set_xscale("log")
    ax.set_yscale("symlog", linthresh=1)
    ax.set_xlabel("temps de calcul moyen (ms, échelle log)")
    ax.set_ylabel("erreur de position médiane (cm)")
    ax.set_title(f"Précision et coût — pose initiale à {std[0]:.2f} m / {std[1]:.0f}° — {tag}")
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(out / f"precision_temps_{tag}.png", dpi=130)
    plt.close(fig)


def _example_figure(refs, cases, out: Path, tag, method="Gauss-Newton"):
    """Un exemple par type de référence : pose initiale (rouge) -> pose trouvée (vert)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    seen, picks = set(), []
    for c in cases:
        if c[0] in ("grid", "vector", "cloud") and c[0] not in seen:
            seen.add(c[0])
            picks.append(c)
    fig, axes = plt.subplots(1, len(picks), figsize=(5.2 * len(picks), 4.6))
    for ax, (kind, key, local, truth) in zip(np.atleast_1d(axes), picks):
        ref = refs[kind][key]
        init = perturb(truth, INIT_LEVELS[STANDARD_LEVEL], np.random.default_rng(7))
        res = L.localise(ref, local, init, method)
        if kind == "grid":
            g = ref.grid
            x0, y0 = g.origin
            ax.imshow(g.probability() > 0.65, origin="lower", cmap="Greys", alpha=0.8,
                      extent=[x0, x0 + g.shape[1] * g.res, y0, y0 + g.shape[0] * g.res])
        elif kind == "vector":
            for s in ref.segments:
                ax.plot([s.p1[0], s.p2[0]], [s.p1[1], s.p2[1]], "k-", lw=2)
        else:
            ax.plot(ref.P[:, 0], ref.P[:, 1], ".", color="0.3", ms=2, label="scan de référence")
        for pose, col, lab in ((init, "tab:red", "pose initiale"), (res.pose, "tab:green", "pose trouvée")):
            w = pose.transform(local)
            ax.plot(w[:, 0], w[:, 1], ".", color=col, ms=2.5, label=lab)
            ax.plot(pose.x, pose.y, "o", color=col)
        e = np.hypot(res.pose.x - truth.x, res.pose.y - truth.y) * 100
        ax.set_title(f"{REF_LABEL[kind].split(' (')[0]} — {method}\nerreur finale {e:.1f} cm, "
                     f"{np.degrees(abs(L.wrap(res.pose.theta - truth.theta))):.2f}°", fontsize=9)
        ax.set_aspect("equal")
        ax.legend(fontsize=7, loc="upper right", markerscale=3)
    fig.tight_layout()
    fig.savefig(out / f"exemples_{tag}.png", dpi=130)
    plt.close(fig)


def _table(summ, level, refs, absolute=True):
    """absolute=False (réel, référence mesurée ou assemblée) : pas de verdict
    réussi/échoué sur l'écart à la référence, seulement écart moyen ± écart-type."""
    if absolute:
        head = ("| référence | méthode | réussite [IC 95 %] | convergence | erreur position médiane / p90 | "
                "erreur angle médiane / p90 | temps moyen | poses évaluées |")
    else:
        head = ("| référence | méthode | convergence [IC 95 %] | écart à la référence : position moyenne ± σ | "
                "angle moyen ± σ | médiane position / angle | temps moyen | poses évaluées |")
    lines = [head, "|---|---|---|---|---|---|---|---|"]
    for ref in refs:
        for (r, m, l), s in sorted(summ.items(), key=lambda kv: (kv[0][0], kv[1]["temps_ms"])):
            if r != ref or l != level:
                continue
            if absolute:
                lines.append(f"| {r} | {m} | {_pct(s['reussite'], s['n'])} ({s['n']}) | {s['convergence']:.0%} | "
                             f"{s['med_m'] * 100:.1f} / {s['p90_m'] * 100:.1f} cm | {s['med_deg']:.2f} / {s['p90_deg']:.2f}° | "
                             f"{s['temps_ms']:.0f} ms | {s['poses']:.0f} |")
            else:
                lines.append(f"| {r} | {m} | {_pct(s['convergence'], s['n'])} ({s['n']}) | "
                             f"{s['mean_m'] * 100:.1f} ± {s['std_m'] * 100:.1f} cm | {s['mean_deg']:.2f} ± {s['std_deg']:.2f}° | "
                             f"{s['med_m'] * 100:.1f} cm / {s['med_deg']:.2f}° | {s['temps_ms']:.0f} ms | {s['poses']:.0f} |")
    return lines


def _sensitivity_table(summ, refs, levels, key="reussite"):
    head = "| référence | méthode | " + " | ".join(f"{d:.2f} m / {a:.0f}°" for d, a in levels) + " |"
    lines = [head, "|---|---|" + "---|" * len(levels)]
    for ref in refs:
        for m in sorted({k[1] for k in summ if k[0] == ref}):
            vals = [summ.get((ref, m, l)) for l in levels]
            lines.append(f"| {ref} | {m} | " + " | ".join(f"{v[key]:.0%}" if v else "—" for v in vals) + " |")
    n = next(iter(summ.values()))["n"] if summ else 0
    lo, hi = wilson(n // 2, n)
    lines += ["", f"Chaque case porte sur {n} essais : à 50 %, l'intervalle de confiance à 95 % va de {lo:.0%} à {hi:.0%} "
                  "(Wilson). Deux cases qui diffèrent de moins de ~20 points ne sont pas significativement différentes."]
    return lines


def _per_scan_table(rows, refs):
    """Écart médian (toutes méthodes itératives et tous niveaux) entre la pose
    trouvée et la pose de référence, scan par scan : si TOUTES les méthodes
    s'accordent sur une pose éloignée de la référence, c'est la référence
    (l'assemblage) qui est douteuse, pas la localisation."""
    keep = ("Gauss-Newton", "ICP", "particules", "multi-résolution", "brute force")
    scans = sorted({r["scan"].split("->")[0] for r in rows}, key=lambda n: int(n[4:]) if n[4:].isdigit() else 0)
    L = ["### Écart à la référence scan par scan", "",
         "Erreur de position médiane sur toutes les méthodes itératives et toutes les poses initiales "
         "(un scan dont toutes les méthodes s'écartent de la même façon a probablement une pose de référence décalée) :", "",
         "| scan | " + " | ".join(refs) + " |", "|---|" + "---|" * len(refs)]
    for n in scans:
        cells = []
        for ref in refs:
            e = [r["err_m"] for r in rows if r["reference"] == ref and r["methode"] in keep
                 and r["scan"].split("->")[0] == n]
            cells.append(f"{np.median(e) * 100:.1f} cm" if e else "—")
        L.append(f"| {n} | " + " | ".join(cells) + " |")
    return L + [""]


# ======================================================================= rapport
def _next_version(base: Path) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    k = 1
    while (base / f"version_{k}").exists():
        k += 1
    out = base / f"version_{k}"
    out.mkdir()
    return out


def evaluate(out_base="resultats/localisation", real_session=None, real_poses=None, quick=False, log=print,
             scans=None, seuils=None, incertitude=None, sans_simulation=False):
    """`real_poses` : poses de référence du réel. Par défaut, les poses de
    l'assemblage (carte/version_N) ; "mesurees" -> poses.json de la session
    (positions mesurées et saisies dans Lidar Plot, ou poses RobotControl).
    `incertitude` : (m, °) de ces mesures, recopiée dans le rapport."""
    global SUCCESS_XY, SUCCESS_TH
    if seuils:
        SUCCESS_XY, SUCCESS_TH = float(seuils[0]), float(seuils[1])
    levels = INIT_LEVELS[1:4] if quick else INIT_LEVELS
    t0 = time.time()
    real_data = None
    if real_session:  # contrôles d'abord : pas de dossier version_N vide en cas d'erreur
        session = Path(real_session)
        measured = real_poses == "mesurees"
        poses = session / "poses.json" if measured else Path(real_poses) if real_poses else _latest_poses(session)
        if not poses.exists():
            raise SystemExit(f"Pas de fichier {poses}. Ouvrez la session dans Lidar Plot et saisissez les poses mesurées "
                             "(ou importez les lidar_scan.csv de RobotControl avec « 📥 Importer » : leur pose est reprise).")
        log(f"Réel : {session.name} (poses de référence : {poses})…")
        real_data = real_dataset(session, poses, scans, log=log)
    out = _next_version(Path(out_base))
    rows, sim_summ = [], {}
    if not sans_simulation:
        log("Simulation : construction des références…")
        refs, cases = sim_dataset(n_map_cases=4 if quick else 12, n_per_ref=1 if quick else 3)
        rows = run(refs, cases, levels, log=log)
        sim_summ = summarize(rows)
        _figures(rows, sim_summ, out, "simulation")
        _example_figure(refs, cases, out, "simulation")
        _threshold_figure(rows, out, "simulation", levels[min(STANDARD_LEVEL, len(levels) - 1)]
                          if levels is INIT_LEVELS else levels[len(levels) // 2])

    real_summ, unc, real_rows, real = None, {}, [], None
    if real_data:
        rrefs, rcases, loaded, truth, repeats = real_data
        rep_ = repeatability(loaded, truth, repeats)
        unc_source = "annoncée"
        if incertitude is None and rep_:  # par défaut : la répétabilité mesurée (robot reposé sur le repère)
            ev = np.array([[r[2], r[3]] for r in rep_])
            incertitude, unc_source = (float(np.median(ev[:, 0])), float(np.median(ev[:, 1]))), "répétabilité"
        real = dict(session=session, poses=poses, measured=measured, incertitude=incertitude, unc_source=unc_source,
                    scans=sorted({c[1].split("->")[0] for c in rcases}, key=_num), repeat=rep_,
                    n_cloud=sum(c[0] == "cloud" for c in rcases))
        unc = reference_uncertainty(rrefs, rcases)
        real_rows = run(rrefs, rcases, levels, draws=1 if quick else 2, log=log, dataset="réel")
        real_summ = summarize(real_rows)
        _figures(real_rows, real_summ, out, "reel")
        _example_figure(rrefs, rcases, out, "reel")
        _threshold_figure(real_rows, out, "reel", levels[min(STANDARD_LEVEL, len(levels) - 1)]
                          if levels is INIT_LEVELS else levels[len(levels) // 2], incertitude if measured else None)

    with open(out / "resultats.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list((rows or real_rows)[0]), delimiter=";")
        w.writeheader()
        for r in rows + real_rows:
            w.writerow({k: (f"{v:.5f}".replace(".", ",") if isinstance(v, float) else v) for k, v in r.items()})
    _report(out, rows, sim_summ, real_rows, real_summ, unc, levels, time.time() - t0, real)
    log(f"Résultats dans {out}")
    return out


def _latest_poses(session: Path) -> Path:
    vers = sorted((session / "carte").glob("version_*/poses_assemblees.json"),
                  key=lambda p: int(p.parent.name.split("_")[1]))
    if not vers:
        raise SystemExit(f"Pas de poses assemblées dans {session}/carte (lancer d'abord « python -m carto assemble »).")
    return vers[-1]


def _report(out, rows, summ, real_rows, real_summ, unc, levels, dt, real):
    refs = [r for r in REF_LABEL.values() if any(x["reference"] == r for x in rows)]
    std = levels[min(STANDARD_LEVEL, len(levels) - 1)] if levels is INIT_LEVELS else levels[len(levels) // 2]
    why = (" 5 cm ≈ une cellule de la grid map et ≈ 1,5 × la précision du LD06 (30 mm, datasheet) ; "
           "2° décale un mur situé à 3 m de 10 cm, au-delà la carte construite avec cette pose « bave »."
           if (SUCCESS_XY, SUCCESS_TH) == (0.05, 2.0) else " (seuils choisis avec `--seuils`).")
    Lx = ["# Localisation par scan matching — évaluation chiffrée", "",
          f"Généré par `python -m carto evaluer` en {dt:.0f} s.", "",
          "## Protocole", "",
          "- **Mêmes scans, mêmes poses initiales** pour toutes les méthodes : pour chaque scan et chaque niveau "
          "d'erreur initiale, la pose de départ est tirée une fois (graine fixe) puis donnée à chaque méthode.",
          "- **Erreur de la pose initiale** : décalage de 75 à 100 % de d mètres dans une direction au hasard et de "
          "±(75 à 100 % de a) degrés. Niveaux : " + ", ".join(f"{d:.2f} m / {a:.0f}°" for d, a in levels) + ".",
          f"- **Réussite** : erreur de position < {SUCCESS_XY * 100:.0f} cm **et** erreur angulaire < {SUCCESS_TH:g}°." + why,
          "- **Convergence** : la méthode, partie de la pose fausse, retombe sur la pose qu'elle trouve en partant de la "
          f"pose de référence (à {CONV_DEFAULT[0] * 100:.0f} cm et {CONV_DEFAULT[1]:g}° près ; "
          f"{CONV_TOL['brute force'][0] * 100:.0f} cm et {CONV_TOL['brute force'][1]:g}° pour la brute force, arrondie à son pas). "
          "Elle ne dépend pas de la précision de la référence : c'est elle qui mesure la sensibilité à l'initialisation "
          "sur le réel. Les calculs directs donnent la même réponse quel que soit le départ : leur convergence vaut "
          "presque toujours 100 %, même quand la réponse est fausse ; les juger sur l'écart à la référence.",
          "- **IC 95 %** : intervalle de confiance de Wilson d'un taux calculé sur peu d'essais.",
          "- **Fenêtre de recherche** de la brute force : ±0,50 m et ±15° autour du départ, fixée à l'avance. Au-delà "
          "de 15° (niveau 20°) la vraie pose peut être hors fenêtre : l'échec est attendu. La multi-résolution part de "
          "la même fenêtre mais **se recentre** sur le meilleur résultat à chaque niveau (±20 cm / ±8° de plus au "
          "niveau 2) : elle rattrape souvent une pose en bord de fenêtre.",
          "- **Calcul direct par moments** : le centre de gravité d'un scan dépend de ce que le lidar voit et de la "
          "densité de points (plus forte près du lidar) ; dès que le robot bouge de 30 cm ces deux choses changent, "
          "d'où un biais de 10 à 20 cm même avec une pose de départ presque exacte. Ce n'est pas un bug.",
          "- **Temps** : temps de calcul de la localisation seule (la référence — champ de distance, index — est "
          "construite une fois, avant), Python + numpy sur ce PC.", ""]
    if summ:
        Lx += ["## Simulation (vérité terrain exacte)", "",
               "Salle simulée en L (8 × 6 m, cloison, pilier) ; bruit des distances 30 mm, 2 % de mesures sans écho, 450 points/tour.",
               "- grid map (cellules 5 cm) et carte vectorielle construites à partir de 4 scans simulés (pos1..pos4) ;",
               "- scans à localiser sur ces cartes : poses tirées au hasard dans la salle (à plus de 40 cm des murs) ;",
               "- entre scans : chaque scan pos1..pos4 est une référence ; scans à localiser pris à 30 cm et ±10° de sa position.", "",
               f"### Comparaison à erreur initiale {std[0]:.2f} m / {std[1]:.0f}°", ""]
        Lx += _table(summ, std, refs)
        Lx += ["", "### Sensibilité à la pose initiale (taux de réussite)", ""]
        Lx += _sensitivity_table(summ, refs, levels)
        Lx += ["", "Attention : la simulation génère les scans avec le même modèle de salle et de bruit que celui "
                   "qu'utilisent les méthodes ; elle ne reproduit pas les défauts propres au LD06 (bords d'objets, "
                   "vitres, reflets). Ses taux de réussite sont donc un maximum, pas une prévision du réel.", "",
               "![sensibilité](sensibilite_simulation.png)", "", "![seuils](seuils_simulation.png)", "",
               "![précision et temps](precision_temps_simulation.png)", "", "![exemples](exemples_simulation.png)", ""]
    if real_summ:
        rrefs = [r for r in REF_LABEL.values() if any(x["reference"] == r for x in real_rows)]
        scans = real["scans"]
        Lx += ["## Scans réels", "",
               f"Session `{real['session'].name}`, {len(scans)} scans : {', '.join(scans)}. "
               f"Poses de référence : `{real['poses']}`."]
        if real["measured"]:
            inc = real["incertitude"]
            Lx += ["- **Pose de référence** : position **mesurée** sur le robot (repères au sol, mètre) et saisie dans "
                   "Lidar Plot ou dans RobotControl"
                   + ((f", incertitude **±{inc[0] * 100:.1f} cm et ±{inc[1]:.2g}°** (" +
                       ("valeur annoncée par l'opérateur" if real["unc_source"] == "annoncée" else
                        "estimée par la répétabilité : robot reposé sur le même repère") + ").") if inc else
                      " ; incertitude de mesure inconnue (ni `--incertitude`, ni captures répétées au même repère)."),
                   "- Les cartes sont construites avec les poses mesurées des AUTRES scans : leur erreur de mesure est "
                   "donc à la fois dans la carte et dans la pose de référence. Sous cette incertitude, l'écart à la "
                   "référence ne permet pas de dire quelle méthode est la plus précise : il n'y a donc **pas de verdict "
                   "réussi/échoué** sur cet écart, seulement sa moyenne ± écart-type. Le taux de réussite est remplacé "
                   "par la **convergence**."]
        else:
            Lx += ["- **Pose de référence** : pose obtenue à l'assemblage (recalage global + ICP). Les positions n'ont "
                   "pas été mesurées sur le robot : la référence vient elle-même du scan matching. L'écart à cette "
                   "référence mesure donc la **cohérence** entre méthodes, **pas leur précision** absolue."]
        Lx += [f"- grid map et carte vectorielle construites **sans** le scan testé ni les captures faites au même repère "
               f"(poses à moins de {SAME_MARK * 100:.0f} cm, quel que soit l'angle) ;",
               f"- entre scans : chaque scan contre le scan le plus proche pris à un autre repère (à moins de {NEAR_SCAN} m).", ""]
        if real["repeat"]:
            Lx += ["### Répétabilité : deux captures au même repère", "",
                   "Pose de la 2e capture retrouvée sur la 1re (Gauss-Newton, point-à-droite), comparée aux poses saisies. "
                   "Si le robot a été **reposé** sur le repère entre les deux captures, l'écart mesure la précision du "
                   "placement, donc l'incertitude des poses de référence ; s'il n'a pas bougé, il mesure le bruit du lidar.", "",
                   "| captures | écart de position | écart d'angle | score |", "|---|---|---|---|"]
            for n, m, e, a, sc in real["repeat"]:
                Lx.append(f"| {n} / {m} | {e * 100:.1f} cm | {a:.2f}° | {sc:.2f} |")
            ev = np.array([[r[2], r[3]] for r in real["repeat"]])
            Lx += ["", f"Médiane : **{np.median(ev[:, 0]) * 100:.1f} cm** et **{np.median(ev[:, 1]):.2f}°** "
                       f"(maximum {ev[:, 0].max() * 100:.1f} cm, {ev[:, 1].max():.2f}°).", ""]
        if not real["n_cloud"]:
            Lx += [f"> Aucun cas « entre scans » : aucun scan n'a de voisin pris à un autre repère à moins de {NEAR_SCAN} m. "
                   "Prévoir des repères proches les uns des autres (par paires à 30 cm).", ""]
        Lx += ["### Précision du recalage (calcul, borne basse)", "",
               "Écart-type estimé par approximation de Laplace (Σ = s² (JᵀWJ)⁻¹, s² = variance des distances "
               "point → carte vectorielle construite sans ce scan), à la pose de référence. C'est la précision "
               "avec laquelle le scan « tient » sur la carte, **pas** l'incertitude du placement du robot sur le repère :", "",
               "| scan | σx | σy | σθ |", "|---|---|---|---|"]
        for k, (sx, sy, st) in unc.items():
            Lx.append(f"| {k} | {sx * 1000:.1f} mm | {sy * 1000:.1f} mm | {st:.3f}° |")
        if unc:
            a = np.array(list(unc.values()))
            Lx += ["", f"Moyenne : σx = {a[:, 0].mean() * 1000:.1f} mm, σy = {a[:, 1].mean() * 1000:.1f} mm, "
                       f"σθ = {a[:, 2].mean():.3f}°. C'est une borne optimiste (bruit supposé indépendant d'un point "
                       "à l'autre) : l'écart scan par scan ci-dessous, et la répétabilité si elle a été mesurée, "
                       "donnent l'incertitude réaliste.", ""]
        Lx += _per_scan_table(real_rows, rrefs)
        Lx += [f"### Comparaison à erreur initiale {std[0]:.2f} m / {std[1]:.0f}°", ""]
        Lx += _table(real_summ, std, rrefs, absolute=False)
        Lx += ["", "### Sensibilité à la pose initiale (taux de convergence)", ""]
        Lx += _sensitivity_table(real_summ, rrefs, levels, key="convergence")
        Lx += ["", f"Pour information, part des essais à moins de {SUCCESS_XY * 100:.0f} cm et {SUCCESS_TH:g}° de la "
                   "référence (dépend surtout de la précision de la référence) :", ""]
        Lx += _sensitivity_table(real_summ, rrefs, levels)
        Lx += ["", "![sensibilité](sensibilite_reel.png)", "", "![seuils](seuils_reel.png)", "",
               "![précision et temps](precision_temps_reel.png)", "", "![exemples](exemples_reel.png)", ""]
        if real["measured"] and real["incertitude"] and (real["incertitude"][1] >= SUCCESS_TH * 0.5
                                                         or real["incertitude"][0] >= SUCCESS_XY * 0.5):
            Lx += [f"> **Attention** : l'incertitude des poses mesurées (±{real['incertitude'][0] * 100:.1f} cm, "
                   f"±{real['incertitude'][1]:.2g}°) est du même ordre que les seuils ({SUCCESS_XY * 100:.0f} cm, "
                   f"{SUCCESS_TH:g}°). Un écart au-dessus du seuil peut venir de la mesure et non de la méthode : "
                   "juger les méthodes sur la convergence.", ""]
    Lx += ["## Fichiers", "", "- `resultats.csv` : une ligne par essai (séparateur `;`, virgule décimale : s'ouvre dans Excel) ;",
           "- `sensibilite_*.png`, `seuils_*.png`, `precision_temps_*.png`, `exemples_*.png` : figures du rapport.", ""]
    (out / "synthese.md").write_text("\n".join(Lx), encoding="utf-8")
    (out / "parametres.json").write_text(json.dumps(dict(
        reussite_m=SUCCESS_XY, reussite_deg=SUCCESS_TH, niveaux=levels, sigma_score=L.SIGMA,
        fenetre_brute_force=[0.5, 15.0], pas_brute_force=[0.04, 1.5], niveaux_multires=L.LEVELS,
        poses_reel=str(real["poses"]) if real else None, poses_mesurees=bool(real and real["measured"]),
        incertitude_mesure=real["incertitude"] if real else None), indent=2), "utf-8")
