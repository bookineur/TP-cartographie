"""Ligne de commande.

    python -m carto plot
    python -m carto assistant --folder data/salle
    python -m carto simulate --out data/sim
    python -m carto view   data/sim --poses data/sim/poses_init.json --save-poses data/sim/poses.json
    python -m carto grid   data/sim --poses data/sim/poses_truth.json --out out/grid
    python -m carto vector data/sim --poses data/sim/poses_truth.json --out out/vector [--cut-rays]
    python -m carto evaluer [--reel data/salle_2026-11-02_18h31] [--rapide]
    python -m carto localiser scan.csv --ref gridmap.npz|carte_vectorielle.txt|scan_ref.csv --init x y theta
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def _load(args):
    from carto.scan import Pose, load_poses, load_scans
    scans = load_scans(args.scans)
    if not scans:
        raise SystemExit("Aucun scan trouvé.")
    poses = load_poses(args.poses) if args.poses and Path(args.poses).exists() else {}
    # scans du MapTool du prof : la position du robot est écrite dans le fichier
    for s in scans:
        if s.name not in poses and "robot_pose" in s.meta:
            poses[s.name] = s.meta["robot_pose"]
    missing = [s.name for s in scans if s.name not in poses]
    if missing and args.poses:
        print(f"(pose absente -> (0,0,0) pour : {', '.join(missing)})")
    return scans, {s.name: poses.get(s.name, Pose()) for s in scans}


def _filter(scans, args):
    return [s.filtered(args.min_range, args.max_range, args.min_intensity) for s in scans]


def cmd_assemble(args):
    from carto.build_map import build
    build(Path(args.session), args.scans, Path(args.out) if args.out else None, args.use_poses, args.res,
          excluded=args.ecartes, align_walls=not args.sans_redressement)


def cmd_plot(args):
    from carto.plot_app import run_plot
    run_plot(args.folder)


def cmd_assistant(args):
    from carto.assistant import run_assistant
    run_assistant(args.folder, args.tours)


def cmd_simulate(args):
    from carto.simulate import simulate
    out = simulate(args.out, args.per_pose, args.seed)
    print(f"Scans simulés dans {out}/ (+ poses_truth.json, poses_init.json)")


def cmd_view(args):
    from carto.viewer import run_viewer
    scans, poses = _load(args)
    run_viewer(scans, poses, poses_path=args.save_poses or args.poses or "poses.json",
               out_dir=args.out, resolution=args.res, ray_cutting=args.cut_rays)


def cmd_grid(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from carto.gridmap import OccupancyGrid

    scans, poses = _load(args)
    scans = _filter(scans, args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    grid = None
    for k, s in enumerate(scans):
        p = poses[s.name]
        if grid is None:
            grid = OccupancyGrid.from_scan(s, p, args.res)          # outil 1
            print(f"[from_scan] {s.name}")
        else:
            grid.update(s, p, decay=args.decay)                     # outil 2
            print(f"[update]    {s.name}")
        if args.steps:
            _save_grid_png(grid, out / f"step_{k:02d}_{s.name}.png", plt, [(s, p)])
    grid.save(out / "gridmap.npz")
    _save_grid_png(grid, out / "gridmap.png", plt, list(zip(scans, [poses[s.name] for s in scans])))
    cls = grid.classify()
    print(f"Grille {grid.shape[1]}x{grid.shape[0]} @ {grid.res} m : "
          f"{(cls == 1).sum()} occupées, {(cls == 0).sum()} libres, {(cls == -1).sum()} inconnues")
    print(f"-> {out}/gridmap.png, gridmap.npz")


def _save_grid_png(grid, path, plt, scans_poses):
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.imshow(1.0 - grid.probability(), cmap="gray", origin="lower", vmin=0, vmax=1,
              extent=grid.extent, interpolation="nearest")
    for s, p in scans_poses:
        ax.plot(p.x, p.y, "o", ms=5)
        ax.arrow(p.x, p.y, 0.3 * np.cos(p.theta), 0.3 * np.sin(p.theta), width=0.03, color="tab:red")
    ax.set_aspect("equal")
    ax.set_title(f"Grid map ({grid.n_scans} scans) — noir = occupé, blanc = libre, gris = inconnu")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def cmd_vector(args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from carto.vectormap import VectorMap

    scans, poses = _load(args)
    scans = _filter(scans, args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    vm = VectorMap(ray_cutting=args.cut_rays)
    for s in scans:
        new = vm.add_scan(s, poses[s.name])
        print(f"{s.name}: {len(new)} segments extraits -> carte = {len(vm.segments)} segments")
    vm.save_csv(out / "segments.csv")
    fig, ax = plt.subplots(figsize=(8, 7))
    for s in scans:
        pts = s.world_xy(poses[s.name])
        ax.scatter(pts[:, 0], pts[:, 1], s=1, alpha=0.4)
    for sg in vm.segments:
        ax.plot([sg.p1[0], sg.p2[0]], [sg.p1[1], sg.p2[1]], "-", color="crimson",
                lw=1 + min(sg.n_obs, 4) * 0.5)
    ax.set_aspect("equal")
    ax.set_title(f"Carte vectorielle : {len(vm.segments)} segments (épaisseur = nb d'observations)")
    fig.tight_layout()
    fig.savefig(out / "vectormap.png", dpi=130)
    print(f"-> {out}/vectormap.png, segments.csv")


def cmd_evaluer(args):
    from carto.evaluation import evaluate
    evaluate(args.out, args.reel, args.poses, args.rapide)


def load_reference(path, ref_pose=None):
    """grid map (.npz), carte vectorielle (.txt / .csv x1,y1,x2,y2) ou scan de référence (.csv)."""
    from carto import localisation as L
    from carto.gridmap import OccupancyGrid
    from carto.scan import Pose, load_scan_file
    from carto.segments import Segment
    path = Path(path)
    if path.suffix == ".npz":
        return L.GridRef(OccupancyGrid.load(path))
    head = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    rows = [l for l in head if l.strip() and not l.startswith("#")]
    if rows and rows[0].replace(" ", "").lower().startswith("x1,y1,x2,y2") or path.suffix == ".txt":
        segs = []
        for l in rows:
            try:
                x1, y1, x2, y2 = map(float, l.split(",")[:4])
            except ValueError:
                continue  # en-tête
            segs.append(Segment((x1, y1), (x2, y2)))
        return L.VectorRef(segs)
    (s,) = load_scan_file(path)[:1]
    pose = ref_pose or s.meta.get("robot_pose") or Pose()
    return L.CloudRef(s.filtered().world_xy(pose), point_to_line=True)


def cmd_localiser(args):
    from carto import localisation as L
    from carto.register import clean_scan
    from carto.scan import Pose, load_scan_file
    ref = load_reference(args.ref)
    scan = clean_scan(load_scan_file(args.scan)[0])
    init = Pose.from_list_deg(args.init) if args.init else scan.meta.get("robot_pose", Pose())
    print(f"Référence : {ref.kind} ; pose initiale {init.as_list_deg()}")
    names = L.methods_for(ref) if args.methode == "toutes" else [args.methode]
    for m in names:
        r = L.localise(ref, scan.local_xy(), init, m)
        print(f"  {m:18s} -> x={r.pose.x:.3f} m  y={r.pose.y:.3f} m  θ={np.degrees(r.pose.theta):.2f}°   "
              f"score {r.score:.2f}   {r.time_s * 1000:.0f} ms")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m carto", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("assemble", help="assemble les scans d'une session et construit grid map + carte vectorielle")
    p.add_argument("session", help="dossier de session Lidar Plot (scanK.csv)")
    p.add_argument("--scans", help="scans à utiliser, ex. 1-9 ou 1,2,5-7 (défaut : tous)")
    p.add_argument("--out", help="dossier de sortie (défaut : nouveau <session>/carte/version_N)")
    p.add_argument("--use-poses", action="store_true", help="utiliser poses.json au lieu du recalage automatique")
    p.add_argument("--ecartes", help="scans écartés de la carte mais présentés dans le rapport, ex. 10-14")
    p.add_argument("--sans-redressement", action="store_true",
                   help="garder l'orientation du scan de référence (ne pas aligner les murs sur les axes)")
    p.add_argument("--res", type=float, default=0.05, help="taille des cellules de la grid map (m)")
    p.set_defaults(func=cmd_assemble)

    p = sub.add_parser("plot", help="Lidar Plot : visualiseur temps réel façon Teleplot + captures")
    p.add_argument("--folder", default=None, help="dossier de session (défaut : data/captures_<date>)")
    p.set_defaults(func=cmd_plot)

    p = sub.add_parser("assistant", help="assistant de capture guidée (fenêtre)")
    p.add_argument("--folder", default="data/salle", help="dossier de la session")
    p.add_argument("--tours", type=int, default=5, help="tours enregistrés par position")
    p.set_defaults(func=cmd_assistant)

    p = sub.add_parser("simulate", help="génère des scans simulés")
    p.add_argument("--out", default="data/sim")
    p.add_argument("--per-pose", type=int, default=1)
    p.add_argument("--seed", type=int, default=0)
    p.set_defaults(func=cmd_simulate)

    p = sub.add_parser("evaluer", help="TP Jour 2 : compare les méthodes de localisation (chiffré)")
    p.add_argument("--reel", help="session réelle à évaluer aussi, ex. data/salle_2026-11-02_18h31")
    p.add_argument("--poses", help="poses de référence du réel (défaut : dernière carte/version_N/poses_assemblees.json)")
    p.add_argument("--out", default="resultats/localisation", help="dossier (une version_N par lancement)")
    p.add_argument("--rapide", action="store_true", help="moins de cas, pour essayer")
    p.set_defaults(func=cmd_evaluer)

    p = sub.add_parser("localiser", help="localise un scan sur une grid map, une carte vectorielle ou un scan")
    p.add_argument("scan", help="scan à localiser (CSV)")
    p.add_argument("--ref", required=True, help="gridmap.npz, carte_vectorielle.txt / vector_map.txt, ou scan de référence .csv")
    p.add_argument("--init", nargs=3, type=float, metavar=("X", "Y", "THETA_DEG"), help="pose initiale")
    p.add_argument("--methode", default="toutes", help="brute force, multi-résolution, Gauss-Newton, ICP, particules… ou toutes")
    p.set_defaults(func=cmd_localiser)

    for name, func, help_ in (("view", cmd_view, "visualiseur interactif"),
                              ("grid", cmd_grid, "construit une grid map"),
                              ("vector", cmd_vector, "construit une carte vectorielle")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("scans", nargs="+", help="fichiers CSV ou dossiers")
        p.add_argument("--poses", help="JSON {scan: [x_m, y_m, theta_deg]}")
        p.add_argument("--out", default=f"out/{name}")
        p.add_argument("--res", type=float, default=0.05, help="taille de cellule (m)")
        p.add_argument("--min-range", type=float, default=0.05)
        p.add_argument("--max-range", type=float, default=12.0)
        p.add_argument("--min-intensity", type=float, default=0)
        p.add_argument("--cut-rays", action="store_true", help="vectorielle : découpe par les rayons")
        p.set_defaults(func=func)
        if name == "view":
            p.add_argument("--save-poses", help="où sauver les poses (défaut : --poses)")
        if name == "grid":
            p.add_argument("--decay", type=float, default=0.0, help="oubli par scan (0..1)")
            p.add_argument("--steps", action="store_true", help="PNG après chaque scan")

    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
