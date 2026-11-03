"""Visualiseur interactif : plusieurs scans, une couleur par scan, pose éditable.

Commandes (le scan sélectionné est celui coché dans la liste « Scan actif ») :
  souris  clic-gauche + glisser   déplace le scan actif
          molette                  tourne le scan actif (1°, Maj = 0.1°)
  clavier flèches                  translation 5 cm (Maj = 1 cm)
          a / e                    rotation +/- 1° (Maj = 0.1°)
          n / p                    scan suivant / précédent
  champs  x, y (m), θ (°)         saisie directe de la pose
  boutons Grid map / Vectorielle / Effacer / Sauver poses / Export
(Désactiver le zoom/pan de la barre d'outils matplotlib pour déplacer à la souris.)
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Button, CheckButtons, RadioButtons, TextBox

from carto.gridmap import build_grid
from carto.scan import Pose, Scan, save_poses
from carto.vectormap import build_vector_map


class ScanViewer:
    def __init__(self, scans: list[Scan], poses: dict[str, Pose] | None = None,
                 poses_path="poses.json", out_dir=".", resolution=0.05, ray_cutting=False):
        self.scans = scans
        self.poses = {s.name: (poses or {}).get(s.name, Pose()) for s in scans}
        self.visible = {s.name: True for s in scans}
        self.cur = 0
        self.poses_path, self.out_dir = Path(poses_path), Path(out_dir)
        self.resolution, self.ray_cutting = resolution, ray_cutting
        self.grid = self.vmap = None
        self._drag = None
        cmap = plt.get_cmap("tab10" if len(scans) <= 10 else "tab20")
        self.colors = [cmap(i % cmap.N) for i in range(len(scans))]
        self._build_ui()
        self.redraw(rescale=True)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        # libère les touches utilisées par matplotlib (flèches = historique de vue, p = pan)
        for k in ("keymap.back", "keymap.forward", "keymap.pan"):
            plt.rcParams[k] = []
        self.fig = plt.figure(figsize=(13, 8))
        self.fig.canvas.manager.set_window_title("Cartographie LD06")
        self.ax = self.fig.add_axes([0.04, 0.06, 0.62, 0.9])
        self.ax.set_aspect("equal")
        names = [s.name for s in self.scans]
        h = min(0.035 * len(names) + 0.02, 0.36)
        ax_r = self.fig.add_axes([0.70, 0.95 - h, 0.13, h])
        ax_r.set_title("Scan actif", fontsize=9)
        self.radio = RadioButtons(ax_r, names, active=0)
        for lab, c in zip(self.radio.labels, self.colors):
            lab.set_color(c)
            lab.set_fontsize(8)
        self.radio.on_clicked(lambda name: self.select(names.index(name)))
        ax_c = self.fig.add_axes([0.85, 0.95 - h, 0.13, h])
        ax_c.set_title("Visible", fontsize=9)
        self.check = CheckButtons(ax_c, names, [True] * len(names))
        for lab in self.check.labels:
            lab.set_fontsize(8)
        self.check.on_clicked(self._toggle)

        y = 0.95 - h - 0.07
        self.boxes = {}
        for k, label in (("x", "x (m)"), ("y", "y (m)"), ("t", "θ (°)")):
            tb = TextBox(self.fig.add_axes([0.75, y, 0.12, 0.04]), label + " ")
            tb.on_submit(lambda txt, k=k: self._set_from_box(k, txt))
            self.boxes[k] = tb
            y -= 0.05
        y -= 0.02
        self.buttons = []
        for label, cb in (("Grid map", self.show_grid), ("Carte vectorielle", self.show_vector),
                          ("Effacer cartes", self.clear_maps), ("Sauver poses", self.save),
                          ("Export cartes", self.export)):
            b = Button(self.fig.add_axes([0.72, y, 0.24, 0.045]), label)
            b.on_clicked(lambda _e, cb=cb: cb())
            self.buttons.append(b)
            y -= 0.055
        self.status = self.fig.text(0.70, 0.02, "", fontsize=8, va="bottom")

        c = self.fig.canvas
        c.mpl_connect("key_press_event", self._on_key)
        c.mpl_connect("scroll_event", self._on_scroll)
        c.mpl_connect("button_press_event", self._on_press)
        c.mpl_connect("motion_notify_event", self._on_motion)
        c.mpl_connect("button_release_event", lambda e: setattr(self, "_drag", None))

    # ------------------------------------------------------------- actions
    @property
    def pose(self) -> Pose:
        return self.poses[self.scans[self.cur].name]

    def select(self, i):
        self.cur = i % len(self.scans)
        if self.radio.value_selected != self.scans[self.cur].name:
            self.radio.set_active(self.cur)  # rappelle select via on_clicked
            return
        self.redraw()

    def move(self, dx=0.0, dy=0.0, dtheta_deg=0.0):
        p = self.pose
        p.x += dx
        p.y += dy
        p.theta = float(np.radians((np.degrees(p.theta + np.radians(dtheta_deg)) + 180) % 360 - 180))
        self.redraw()

    def _set_from_box(self, k, txt):
        try:
            v = float(txt.replace(",", "."))
        except ValueError:
            return
        p = self.pose
        cur = {"x": p.x, "y": p.y, "t": np.degrees(p.theta)}[k]
        if abs(cur - v) < (0.006 if k == "t" else 0.0006):  # = valeur affichée (arrondie)
            return
        if k == "x":
            p.x = v
        elif k == "y":
            p.y = v
        else:
            p.theta = np.radians(v)
        self.redraw()

    def _toggle(self, name):
        self.visible[name] = not self.visible[name]
        self.redraw()

    def _active_pairs(self):
        return [(s.filtered(), self.poses[s.name]) for s in self.scans if self.visible[s.name]]

    def show_grid(self):
        pairs = self._active_pairs()
        if pairs:
            self.grid = build_grid(pairs, self.resolution)
            self._msg(f"Grid map : {self.grid.shape[1]}x{self.grid.shape[0]} cellules, {len(pairs)} scans")
        self.redraw()

    def show_vector(self):
        pairs = self._active_pairs()
        if pairs:
            self.vmap = build_vector_map(pairs, ray_cutting=self.ray_cutting)
            self._msg(f"Carte vectorielle : {len(self.vmap.segments)} segments")
        self.redraw()

    def clear_maps(self):
        self.grid = self.vmap = None
        self.redraw()

    def save(self):
        save_poses(self.poses_path, self.poses)
        self._msg(f"Poses sauvées dans {self.poses_path}")

    def export(self):
        self.out_dir.mkdir(parents=True, exist_ok=True)
        if self.grid is not None:
            self.grid.save(self.out_dir / "gridmap.npz")
        if self.vmap is not None:
            self.vmap.save_csv(self.out_dir / "segments.csv")
        self.fig.savefig(self.out_dir / "vue.png", dpi=150)
        self._msg(f"Export dans {self.out_dir}/ (vue.png, gridmap.npz, segments.csv)")

    def _msg(self, txt):
        self.status.set_text(txt)
        self.fig.canvas.draw_idle()

    # -------------------------------------------------------------- events
    def _on_key(self, e):
        if e.key is None:
            return
        fine = e.key.startswith("shift+")
        key = e.key.replace("shift+", "")
        step, rot = (0.01, 0.1) if fine else (0.05, 1.0)
        acts = {"left": (-step, 0, 0), "right": (step, 0, 0), "up": (0, step, 0), "down": (0, -step, 0),
                "a": (0, 0, rot), "A": (0, 0, rot), "e": (0, 0, -rot), "E": (0, 0, -rot)}
        if key in acts:
            self.move(*acts[key])
        elif key == "n":
            self.select(self.cur + 1)
        elif key == "p":
            self.select(self.cur - 1)

    def _toolbar_busy(self):
        tb = getattr(self.fig.canvas, "toolbar", None)
        return bool(tb is not None and getattr(tb, "mode", ""))

    def _on_scroll(self, e):
        if e.inaxes is self.ax:
            fine = e.key == "shift"
            self.move(dtheta_deg=(0.1 if fine else 1.0) * (1 if e.button == "up" else -1))

    def _on_press(self, e):
        if e.inaxes is self.ax and e.button == 1 and not self._toolbar_busy():
            self._drag = (e.xdata, e.ydata)

    def _on_motion(self, e):
        if self._drag and e.inaxes is self.ax and e.xdata is not None:
            dx, dy = e.xdata - self._drag[0], e.ydata - self._drag[1]
            self._drag = (e.xdata, e.ydata)
            self.move(dx, dy)

    # ---------------------------------------------------------------- draw
    def redraw(self, rescale=False):
        ax = self.ax
        lims = (ax.get_xlim(), ax.get_ylim())
        ax.clear()
        if self.grid is not None:
            ax.imshow(1.0 - self.grid.probability(), cmap="gray", origin="lower", vmin=0, vmax=1,
                      extent=self.grid.extent, interpolation="nearest", zorder=0)
        for i, s in enumerate(self.scans):
            if not self.visible[s.name]:
                continue
            p = self.poses[s.name]
            pts = s.filtered().world_xy(p)
            active = i == self.cur
            ax.scatter(pts[:, 0], pts[:, 1], s=6 if active else 3, color=self.colors[i],
                       label=s.name, zorder=3 if active else 2, alpha=1 if active else 0.75)
            ax.annotate("", xy=(p.x + 0.4 * np.cos(p.theta), p.y + 0.4 * np.sin(p.theta)),
                        xytext=(p.x, p.y), zorder=4,
                        arrowprops=dict(arrowstyle="-|>", color=self.colors[i], lw=2.5 if active else 1.2))
        if self.vmap is not None:
            for sg in self.vmap.segments:
                ax.plot([sg.p1[0], sg.p2[0]], [sg.p1[1], sg.p2[1]], "-", color="crimson",
                        lw=1 + min(sg.n_obs, 4) * 0.5, zorder=5)
        ax.set_aspect("equal")
        ax.grid(True, lw=0.3, alpha=0.5)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.legend(loc="upper left", fontsize=7, markerscale=3)
        if rescale:
            ax.autoscale()
        else:
            ax.set_xlim(*lims[0])
            ax.set_ylim(*lims[1])
        p = self.pose
        ax.set_title(f"{self.scans[self.cur].name} : x={p.x:.3f} m  y={p.y:.3f} m  "
                     f"θ={np.degrees(p.theta):.2f}°", fontsize=10)
        for k, v in (("x", f"{p.x:.3f}"), ("y", f"{p.y:.3f}"), ("t", f"{np.degrees(p.theta):.2f}")):
            if self.boxes[k].text != v:
                self.boxes[k].set_val(v)
        self.fig.canvas.draw_idle()


def run_viewer(scans, poses=None, **kw):
    v = ScanViewer(scans, poses, **kw)
    plt.show()
    return v
