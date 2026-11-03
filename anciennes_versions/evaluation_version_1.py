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
                    rows.append(dict(jeu=dataset, reference=REF_LABEL[kind], methode=name, cas=ci, scan=key, tirage=k,
                                     init_m=level[0], init_deg=level[1], err_m=e_xy, err_deg=e_th,
                                     temps_ms=r.time_s * 1000, score=r.score, poses_evaluees=r.n_eval,
                                     reussite=int(e_xy < SUCCESS_XY and e_th < SUCCESS_TH)))
        log(f"  erreur initiale {level[0]:.2f} m / {level[1]:.0f}° : fait")
    return rows


# ========================================================================= réel
def real_dataset(session: Path, poses_file: Path, scans=range(1, 10)):
    from carto.register import clean_scan
    from carto.scan import load_poses, load_scans
    truth = load_poses(poses_file)
    names = [f"scan{i}" for i in scans]
    loaded = {s.name: clean_scan(s) for s in load_scans(sorted(session.glob("scan*.csv"))) if s.name in names}
    names = [n for n in names if n in loaded and n in truth]
    refs, cases = {"grid": {}, "vector": {}, "cloud": {}, "cloud_l": {}}, []
    for n in names:
        others = [(loaded[m], truth[m]) for m in names if m != n]
        refs["grid"][n] = L.GridRef(build_grid(others, 0.05))
        refs["vector"][n] = L.VectorRef(build_vector_map(others).segments)
        local = loaded[n].local_xy()
        cases.append(("grid", n, local, truth[n]))
        cases.append(("vector", n, local, truth[n]))
        # plus proche voisin = scan de référence
        m = min((m for m in names if m != n), key=lambda m: np.hypot(truth[m].x - truth[n].x, truth[m].y - truth[n].y))
        key = f"{n}->{m}"
        pts = loaded[m].world_xy(truth[m])
        refs["cloud"][key] = L.CloudRef(pts)
        refs["cloud_l"][key] = L.CloudRef(pts, point_to_line=True)
        cases.append(("cloud", key, local, truth[n]))
        cases.append(("cloud_l", key, local, truth[n]))
    return refs, cases, loaded, truth


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
def summarize(rows):
    """{(référence, méthode, niveau)} -> statistiques."""
    groups = {}
    for r in rows:
        groups.setdefault((r["reference"], r["methode"], (r["init_m"], r["init_deg"])), []).append(r)
    out = {}
    for k, g in groups.items():
        e, a = np.array([r["err_m"] for r in g]), np.array([r["err_deg"] for r in g])
        ok = np.array([r["reussite"] for r in g], bool)
        out[k] = dict(n=len(g), reussite=ok.mean(),
                      med_m=float(np.median(e)), p90_m=float(np.percentile(e, 90)),
                      med_deg=float(np.median(a)), p90_deg=float(np.percentile(a, 90)),
                      ok_m=float(np.median(e[ok])) if ok.any() else np.nan,
                      ok_deg=float(np.median(a[ok])) if ok.any() else np.nan,
                      temps_ms=float(np.mean([r["temps_ms"] for r in g])),
                      poses=float(np.mean([r["poses_evaluees"] for r in g])))
    return out


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


def _table(summ, level, refs):
    lines = ["| référence | méthode | réussite | erreur position médiane / p90 | erreur angle médiane / p90 | "
             "précision si réussite | temps moyen | poses évaluées |", "|---|---|---|---|---|---|---|---|"]
    for ref in refs:
        for (r, m, l), s in sorted(summ.items(), key=lambda kv: (kv[0][0], kv[1]["temps_ms"])):
            if r != ref or l != level:
                continue
            ok = f"{s['ok_m'] * 100:.1f} cm / {s['ok_deg']:.2f}°" if np.isfinite(s["ok_m"]) else "—"
            lines.append(f"| {r} | {m} | {s['reussite']:.0%} ({s['n']}) | {s['med_m'] * 100:.1f} / {s['p90_m'] * 100:.1f} cm | "
                         f"{s['med_deg']:.2f} / {s['p90_deg']:.2f}° | {ok} | {s['temps_ms']:.0f} ms | {s['poses']:.0f} |")
    return lines


def _sensitivity_table(summ, refs, levels):
    head = "| référence | méthode | " + " | ".join(f"{d:.2f} m / {a:.0f}°" for d, a in levels) + " |"
    lines = [head, "|---|---|" + "---|" * len(levels)]
    for ref in refs:
        for m in sorted({k[1] for k in summ if k[0] == ref}):
            vals = [summ.get((ref, m, l)) for l in levels]
            lines.append(f"| {ref} | {m} | " + " | ".join(f"{v['reussite']:.0%}" if v else "—" for v in vals) + " |")
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


def evaluate(out_base="resultats/localisation", real_session=None, real_poses=None, quick=False, log=print):
    out = _next_version(Path(out_base))
    levels = INIT_LEVELS[1:4] if quick else INIT_LEVELS
    t0 = time.time()
    log("Simulation : construction des références…")
    refs, cases = sim_dataset(n_map_cases=4 if quick else 12, n_per_ref=1 if quick else 3)
    rows = run(refs, cases, levels, log=log)
    sim_summ = summarize(rows)
    _figures(rows, sim_summ, out, "simulation")
    _example_figure(refs, cases, out, "simulation")

    real_summ, unc, real_rows = None, {}, []
    if real_session:
        session = Path(real_session)
        poses = Path(real_poses) if real_poses else _latest_poses(session)
        log(f"Réel : {session.name} (poses de référence : {poses})…")
        rrefs, rcases, _, _ = real_dataset(session, poses)
        unc = reference_uncertainty(rrefs, rcases)
        real_rows = run(rrefs, rcases, levels, draws=1 if quick else 2, log=log, dataset="réel")
        real_summ = summarize(real_rows)
        _figures(real_rows, real_summ, out, "reel")
        _example_figure(rrefs, rcases, out, "reel")

    with open(out / "resultats.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), delimiter=";")
        w.writeheader()
        for r in rows + real_rows:
            w.writerow({k: (f"{v:.5f}".replace(".", ",") if isinstance(v, float) else v) for k, v in r.items()})
    _report(out, rows, sim_summ, real_rows, real_summ, unc, levels, time.time() - t0, real_session)
    log(f"Résultats dans {out}")
    return out


def _latest_poses(session: Path) -> Path:
    vers = sorted((session / "carte").glob("version_*/poses_assemblees.json"),
                  key=lambda p: int(p.parent.name.split("_")[1]))
    if not vers:
        raise SystemExit(f"Pas de poses assemblées dans {session}/carte (lancer d'abord « python -m carto assemble »).")
    return vers[-1]


def _report(out, rows, summ, real_rows, real_summ, unc, levels, dt, session):
    refs = [r for r in REF_LABEL.values() if any(x["reference"] == r for x in rows)]
    std = levels[min(STANDARD_LEVEL, len(levels) - 1)] if levels is INIT_LEVELS else levels[len(levels) // 2]
    Lx = ["# Localisation par scan matching — évaluation chiffrée", "",
          f"Généré par `python -m carto evaluer` en {dt:.0f} s.", "",
          "## Protocole", "",
          "- **Mêmes scans, mêmes poses initiales** pour toutes les méthodes : pour chaque scan et chaque niveau "
          "d'erreur initiale, la pose de départ est tirée une fois (graine fixe) puis donnée à chaque méthode.",
          "- **Erreur de la pose initiale** : décalage de 75 à 100 % de d mètres dans une direction au hasard et de ±(75 à 100 % de a) degrés. "
          "Niveaux : " + ", ".join(f"{d:.2f} m / {a:.0f}°" for d, a in levels) + ".",
          f"- **Réussite** : erreur de position < {SUCCESS_XY * 100:.0f} cm **et** erreur angulaire < {SUCCESS_TH:.0f}°. "
          "5 cm ≈ une cellule de la grid map et ≈ 1,5 × la précision du LD06 (30 mm, datasheet) ; "
          "2° décale un mur situé à 3 m de 10 cm, au-delà la carte construite avec cette pose « bave ».",
          "- **Fenêtre de recherche** des méthodes globales (brute force, multi-résolution) : ±0,50 m et ±15°, "
          "fixée à l'avance (sans connaître l'erreur réelle). Une erreur initiale de 20° est donc hors fenêtre : "
          "l'échec est attendu et montre la limite de ces méthodes.",
          "- **Temps** : temps de calcul de la localisation seule (la référence — champ de distance, index — est "
          "construite une fois, avant), Python + numpy sur ce PC.", "",
          "## Simulation (vérité terrain exacte)", "",
          "Salle simulée en L (8 × 6 m, cloison, pilier) ; bruit des distances 30 mm, 2 % de mesures sans écho, 450 points/tour.",
          "- grid map (cellules 5 cm) et carte vectorielle construites à partir de 4 scans simulés (pos1..pos4) ;",
          "- scans à localiser sur ces cartes : poses tirées au hasard dans la salle (à plus de 40 cm des murs) ;",
          "- entre scans : chaque scan pos1..pos4 est une référence ; scans à localiser pris à 30 cm et ±10° de sa position.", "",
          f"### Comparaison à erreur initiale {std[0]:.2f} m / {std[1]:.0f}°", ""]
    Lx += _table(summ, std, refs)
    Lx += ["", "### Sensibilité à la pose initiale (taux de réussite)", ""]
    Lx += _sensitivity_table(summ, refs, levels)
    Lx += ["", "![sensibilité](sensibilite_simulation.png)", "", "![précision et temps](precision_temps_simulation.png)", "",
           "![exemples](exemples_simulation.png)", ""]
    if real_summ:
        rrefs = [r for r in REF_LABEL.values() if any(x["reference"] == r for x in real_rows)]
        Lx += ["## Scans réels de la salle", "",
               f"Session `{Path(session).name}`, scans 1 à 9 (les scans 10 à 14, lidar posé au sol, ne voient presque pas les murs).",
               "- **Pose de référence** : pose obtenue à l'assemblage (recalage global + ICP). Les positions n'ont pas été "
               "mesurées au mètre sur le robot pendant la capture : la référence est donc elle-même une estimation.",
               "- grid map et carte vectorielle construites **sans** le scan testé (sinon le scan se retrouverait dans sa propre carte) ;",
               "- entre scans : chaque scan contre le scan dont la position assemblée est la plus proche.", "",
               "### Incertitude des poses de référence", "",
               "Écart-type estimé par approximation de Laplace (Σ = s² (JᵀWJ)⁻¹, s² = variance des distances "
               "point → carte vectorielle construite sans ce scan) :", "",
               "| scan | σx | σy | σθ |", "|---|---|---|---|"]
        for k, (sx, sy, st) in unc.items():
            Lx.append(f"| {k} | {sx * 1000:.1f} mm | {sy * 1000:.1f} mm | {st:.3f}° |")
        if unc:
            a = np.array(list(unc.values()))
            Lx += ["", f"Moyenne : σx = {a[:, 0].mean() * 1000:.1f} mm, σy = {a[:, 1].mean() * 1000:.1f} mm, "
                       f"σθ = {a[:, 2].mean():.3f}°. C'est une borne optimiste (bruit supposé indépendant) : "
                       "l'incertitude réelle est surtout due aux erreurs de l'assemblage lui-même et aux objets "
                       "déplacés entre scans, de l'ordre du centimètre et du demi-degré (écart entre méthodes "
                       "convergées ci-dessous). Une pose mesurée au mètre ruban et au rapporteur serait "
                       "connue à environ ±2 cm et ±2°, donc moins précise que les méthodes testées.", ""]
        Lx += _per_scan_table(real_rows, rrefs)
        Lx += [f"### Comparaison à erreur initiale {std[0]:.2f} m / {std[1]:.0f}°", ""]
        Lx += _table(real_summ, std, rrefs)
        Lx += ["", "### Sensibilité à la pose initiale (taux de réussite)", ""]
        Lx += _sensitivity_table(real_summ, rrefs, levels)
        Lx += ["", "![sensibilité](sensibilite_reel.png)", "", "![précision et temps](precision_temps_reel.png)", "",
               "![exemples](exemples_reel.png)", ""]
    Lx += ["## Fichiers", "", "- `resultats.csv` : une ligne par essai (séparateur `;`, virgule décimale : s'ouvre dans Excel) ;",
           "- `sensibilite_*.png`, `precision_temps_*.png`, `exemples_*.png` : figures du rapport.", ""]
    (out / "synthese.md").write_text("\n".join(Lx), encoding="utf-8")
    (out / "parametres.json").write_text(json.dumps(dict(
        reussite_m=SUCCESS_XY, reussite_deg=SUCCESS_TH, niveaux=levels, sigma_score=L.SIGMA,
        fenetre_brute_force=[0.5, 15.0], pas_brute_force=[0.04, 1.5], niveaux_multires=L.LEVELS), indent=2), "utf-8")
