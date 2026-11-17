"""Grid map et carte vectorielle de chaque séance réelle, même calcul et même style pour toutes.
Poses : celles de l'assemblage (02/11, 03/11) ou de l'Auto-SLAM de Lidar Lab (04/11, 10/11).
Aucun fichier de données n'est modifié ; sortie dans version_N/.
Lancer : python resultats/cartes_seances/gen_cartes.py"""
import json, sys, time
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from carto.scan import Pose, load_scans  # noqa: E402
from carto.register import clean_scan  # noqa: E402
from carto.gridmap import build_grid  # noqa: E402
from carto.vectormap import build_vector_map  # noqa: E402

D = ROOT / "data"
SEANCES = [
    ("02_11", "Salle, 02/11 (lidar tenu à la main, 9 scans)", D / "salle_2026-11-02_18h31/carte/version_2/session_assemblee", D / "salle_2026-11-02_18h31/carte/version_2/poses_assemblees.json", "poses"),
    ("03_11", "Salle, 03/11 (relevés combinés)", D / "salle_combinee_tout_2026-11-03/carte/version_2/session_assemblee", D / "salle_combinee_tout_2026-11-03/carte/version_2/poses_assemblees.json", "poses"),
    ("04_11", "Robot Wi-Fi, 04/11 (Auto-SLAM de Lidar Lab)", D / "robot_wifi/seance_2026-11-04_17h42m59", D / "robot_wifi/seance_2026-11-04_17h42m59/seance.json", "seance"),
    ("10_11", "Robot Wi-Fi, 10/11 (Auto-SLAM de Lidar Lab)", D / "mesures_phase19_2026-11-09/capture/seance_2026-11-09_13h06m10", D / "mesures_phase19_2026-11-09/capture/seance_2026-11-09_13h06m10/seance.json", "seance"),
]


def poses_of(path, kind):
    j = json.loads(Path(path).read_text("utf-8"))
    if kind == "poses":
        return {k: Pose.from_list_deg(v) for k, v in j.items()}
    return {e["name"][:-4]: Pose.from_list_deg(e["pose"]) for e in j["scans"] if e.get("reg")}


def next_version(base):
    n = 1
    while (base / f"version_{n}").exists():
        n += 1
    return base / f"version_{n}"


out = next_version(Path(__file__).resolve().parent)
out.mkdir(parents=True)
bilan = []
for key, titre, folder, pfile, kind in SEANCES:
    t0 = time.time()
    poses = poses_of(pfile, kind)
    files = [f for f in sorted(Path(folder).glob("scan*.csv")) if f.stem in poses]
    scans = [clean_scan(s) for s in load_scans(files)]
    pairs = [(s, poses[s.name]) for s in scans]
    g = build_grid(pairs, 0.05)
    vm = build_vector_map(pairs)
    segs = vm.segments
    P = np.array([[p.x, p.y] for _, p in pairs])
    p = g.probability()
    ext = g.extent
    lo = np.array([min(ext[0], P[:, 0].min()), min(ext[2], P[:, 1].min())])
    occ = p > 0.65
    oy, ox = np.nonzero(occ)
    occxy = g.origin + (np.column_stack([ox, oy]) + 0.5) * g.res
    # cadrage : la salle (99 % des cellules occupées), pas les rayons isolés lointains
    xl = np.percentile(occxy[:, 0], [0.5, 99.5]) + [-0.6, 0.6]
    yl = np.percentile(occxy[:, 1], [0.5, 99.5]) + [-0.6, 0.6]
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.4))
    ax = axes[0]
    img = np.full(p.shape, 0.55)
    img[p < 0.35] = 1.0
    img[p > 0.65] = 0.0
    ax.imshow(img, cmap="gray", origin="lower", extent=ext, vmin=0, vmax=1, interpolation="nearest")
    ax.plot(P[:, 0], P[:, 1], "o", ms=3.5, color="#1f77b4", label="poses des scans")
    ax.set_title(f"Grid map — cellules de 5 cm ({len(pairs)} scans)\nnoir : occupé · blanc : libre · gris : inconnu", fontsize=10)
    ax2 = axes[1]
    nmax = max(s.n_obs for s in segs)
    for s in segs:
        ax2.plot([s.p1[0], s.p2[0]], [s.p1[1], s.p2[1]], "-", color="#1F4E79", lw=0.8 + 2.2 * (s.n_obs / nmax) ** 0.5, solid_capstyle="round")
    ax2.plot(P[:, 0], P[:, 1], "o", ms=3.5, color="#d62728", label="poses des scans")
    L = sum(np.linalg.norm(s.p2 - s.p1) for s in segs)
    ax2.set_title(f"Carte vectorielle — {len(segs)} segments, {L:.0f} m de murs\népaisseur : nombre d'observations", fontsize=10)
    for a in axes:
        a.set_xlim(*xl); a.set_ylim(*yl); a.set_aspect("equal"); a.set_xlabel("x (m)"); a.grid(alpha=0.25)
    axes[0].set_ylabel("y (m)")
    axes[0].legend(loc="lower left", fontsize=8); axes[1].legend(loc="lower left", fontsize=8)
    fig.suptitle(titre, fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(out / f"carte_{key}.png", dpi=125)
    plt.close(fig)
    bilan.append({"seance": titre, "scans": len(pairs), "segments": len(segs), "longueur_murs_m": round(float(L), 1),
                  "cellules_occupees": int(occ.sum()), "cellules_libres": int((p < 0.35).sum()), "duree_s": round(time.time() - t0, 1)})
    print(bilan[-1])
(out / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), "utf-8")
print("->", out)
