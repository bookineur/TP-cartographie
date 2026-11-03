"""Fenêtre « Localiser » de Lidar Plot (TP Jour 2, vrais tests sur le robot).

Pour le scan sélectionné, dont la pose saisie est la position MESURÉE du robot :
  1. on choisit la référence : grid map ou carte vectorielle des AUTRES scans
     (sans les captures faites au même repère), le scan le plus proche pris à un
     autre repère, ou un fichier (gridmap.npz, vector_map.txt du MapTool, scan) ;
  2. on choisit le départ : la pose saisie, ou la pose saisie décalée d'une
     erreur connue (10 cm / 5° … 50 cm / 20°) pour tester la méthode ;
  3. on lance une méthode ou toutes : le tableau donne la pose trouvée, l'écart
     à la pose mesurée, le score et le temps ; la carte montre le scan au départ
     (orange) et à la pose trouvée (blanc). Chaque essai est ajouté à
     <session>/localisation_essais.csv.
« Évaluation complète » lance `python -m carto evaluer --mesurees` sur la
session (toutes les méthodes, tous les scans, rapport synthese.md).
"""
from __future__ import annotations

import csv
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np

from carto import localisation as L
from carto.evaluation import INIT_LEVELS, SAME_MARK, SUCCESS_TH, SUCCESS_XY, _same_mark, perturb
from carto.gridmap import build_grid
from carto.register import clean_scan
from carto.scan import Pose
from carto.theme import D, FONT
from carto.vectormap import build_vector_map

REF_CHOICES = ["Grid map des autres scans", "Carte vectorielle des autres scans",
               "Scan le plus proche (autre repère)", "Fichier… (gridmap.npz, vector_map.txt, scan .csv)"]
START_CHOICES = ["Pose saisie (mesurée)"] + [f"Pose saisie + erreur de {d * 75:.0f} à {d * 100:.0f} cm / {a * .75:.0f} à {a:.0f}°"
                                              for d, a in INIT_LEVELS[1:]]
ALL = "Toutes (comparer)"
LOG_FIELDS = ["date", "scan", "reference", "depart", "methode", "x_m", "y_m", "theta_deg", "x_saisi", "y_saisi",
              "theta_saisi", "ecart_m", "ecart_deg", "reussite", "score", "temps_ms"]


class LocaliseDialog:
    def __init__(self, app):
        self.app = app
        self.win = tk.Toplevel(app.root, bg=D["panel"])
        self.win.title("Localiser — TP Jour 2")
        self.win.transient(app.root)
        self.win.protocol("WM_DELETE_WINDOW", self.close)
        self.q = queue.Queue()
        self.busy = False
        self.results = []          # (méthode, Result)
        self.ref_file = None
        self._ref_cache = {}
        px = app.px
        f = ttk.Frame(self.win, style="Panel.TFrame")
        f.pack(fill="both", expand=True, padx=px(14), pady=px(12))
        self.title = tk.Label(f, text="", bg=D["panel"], fg=D["text"], font=(FONT, 12, "bold"), anchor="w")
        self.title.grid(row=0, column=0, columnspan=4, sticky="we")
        self.subtitle = tk.Label(f, text="", bg=D["panel"], fg=D["muted"], font=(FONT, 9), anchor="w", justify="left")
        self.subtitle.grid(row=1, column=0, columnspan=4, sticky="we", pady=(0, px(8)))

        def lab(text, r):
            tk.Label(f, text=text, bg=D["panel"], fg=D["muted"], font=(FONT, 9)).grid(row=r, column=0, sticky="w",
                                                                                     pady=px(2))
        lab("Référence", 2)
        self.ref_var = tk.StringVar(value=REF_CHOICES[0])
        cb = ttk.Combobox(f, textvariable=self.ref_var, values=REF_CHOICES, state="readonly", width=46)
        cb.grid(row=2, column=1, columnspan=3, sticky="we")
        cb.bind("<<ComboboxSelected>>", lambda e: self._ref_changed())
        lab("Départ", 3)
        self.start_var = tk.StringVar(value=START_CHOICES[2])
        ttk.Combobox(f, textvariable=self.start_var, values=START_CHOICES, state="readonly", width=46).grid(
            row=3, column=1, columnspan=3, sticky="we")
        lab("Méthode", 4)
        self.meth_var = tk.StringVar(value=ALL)
        self.meth_box = ttk.Combobox(f, textvariable=self.meth_var, state="readonly", width=46)
        self.meth_box.grid(row=4, column=1, columnspan=3, sticky="we")
        self.same_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text=f"Exclure de la référence les captures faites au même endroit (< {SAME_MARK * 100:.0f} cm, "
                                "même robot tourné)", variable=self.same_var).grid(row=5, column=0, columnspan=4, sticky="w",
                                                                       pady=(px(4), 0))
        b = ttk.Frame(f, style="Panel.TFrame")
        b.grid(row=6, column=0, columnspan=4, sticky="we", pady=(px(8), px(6)))
        ttk.Button(b, text="◀ Scan précédent", style="Small.TButton", command=lambda: self.step(-1)).pack(side="left")
        ttk.Button(b, text="Scan suivant ▶", style="Small.TButton", command=lambda: self.step(1)).pack(
            side="left", padx=px(4))
        self.run_btn = ttk.Button(b, text="Localiser", style="Accent.TButton", command=self.run)
        self.run_btn.pack(side="right")

        cols = ("methode", "pose", "ecart", "ok", "score", "temps")
        st = ttk.Style(self.win)
        st.configure("Loc.Treeview", background=D["panel2"], fieldbackground=D["panel2"], foreground=D["text"],
                     rowheight=px(22), font=(FONT, 9))
        st.configure("Loc.Treeview.Heading", background=D["panel"], foreground=D["muted"], font=(FONT, 8, "bold"))
        st.map("Loc.Treeview", background=[("selected", D["accent"])])
        self.tree = ttk.Treeview(f, columns=cols, show="headings", height=8, style="Loc.Treeview")
        for c, t, w in zip(cols, ("Méthode", "Pose trouvée (x, y, θ)", "Écart à la pose saisie",
                                  f"< {SUCCESS_XY * 100:.0f} cm et < {SUCCESS_TH:g}° ?", "Score", "Temps"),
                           (120, 180, 140, 110, 55, 65)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=px(w), anchor="w" if c in ("methode", "pose", "ecart") else "center")
        self.tree.grid(row=7, column=0, columnspan=4, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._show_selected())
        f.rowconfigure(7, weight=1)
        f.columnconfigure(1, weight=1)
        tk.Label(f, text="Score = part des points du scan posés sur la référence (0 à 1 ; une bonne localisation "
                         "dépasse ~0,6). La meilleure méthode est tracée sur la carte : × orange = départ, × blanc = pose "
                         "trouvée (cliquez une ligne pour en voir une autre). Si toutes les méthodes trouvent la même pose "
                         "loin de votre saisie, c'est la saisie qu'il faut vérifier, pas les méthodes.",
                 bg=D["panel"], fg=D["muted"], font=(FONT, 8), wraplength=px(660), justify="left").grid(
            row=8, column=0, columnspan=4, sticky="w", pady=(px(4), 0))
        self.status = tk.Label(f, text="", bg=D["panel"], fg=D["muted"], font=(FONT, 9), anchor="w", justify="left",
                               wraplength=px(660))
        self.status.grid(row=9, column=0, columnspan=4, sticky="we", pady=(px(6), 0))
        a = ttk.Frame(f, style="Panel.TFrame")
        a.grid(row=10, column=0, columnspan=4, sticky="we", pady=(px(6), 0))
        ttk.Button(a, text="✓ Appliquer la pose sélectionnée au scan", command=self.apply).pack(side="left")
        ttk.Button(a, text="Effacer l'affichage", style="Small.TButton", command=self.clear_overlay).pack(
            side="left", padx=px(6))

        sep = tk.Frame(f, bg=D["border"], height=1)
        sep.grid(row=11, column=0, columnspan=4, sticky="we", pady=px(10))
        tk.Label(f, text="ÉVALUATION COMPLÈTE DE LA SESSION", bg=D["panel"], fg=D["muted"],
                 font=(FONT, 8, "bold")).grid(row=12, column=0, columnspan=4, sticky="w")
        e = ttk.Frame(f, style="Panel.TFrame")
        e.grid(row=13, column=0, columnspan=4, sticky="we", pady=(px(4), 0))
        tk.Label(e, text="Incertitude de vos mesures : ±", bg=D["panel"], fg=D["muted"], font=(FONT, 9)).pack(side="left")
        self.unc_m = tk.StringVar(value="")
        ttk.Entry(e, textvariable=self.unc_m, width=5).pack(side="left")
        tk.Label(e, text="m  ±", bg=D["panel"], fg=D["muted"], font=(FONT, 9)).pack(side="left")
        self.unc_d = tk.StringVar(value="")
        ttk.Entry(e, textvariable=self.unc_d, width=4).pack(side="left")
        tk.Label(e, text="°", bg=D["panel"], fg=D["muted"], font=(FONT, 9)).pack(side="left")
        self.eval_btn = ttk.Button(e, text="Lancer l'évaluation (≈ 1 min par scan)", style="Ok.TButton", command=self.evaluate)
        self.eval_btn.pack(side="right")
        tk.Label(f, text="Toutes les méthodes × tous les scans × 5 erreurs de départ, avec vos poses saisies comme "
                         "référence. Incertitude laissée vide = estimée par la répétabilité (robot reposé plusieurs fois "
                         "sur le même repère). Le rapport (synthese.md, figures, CSV) s'ouvre à la fin.",
                 bg=D["panel"], fg=D["muted"], font=(FONT, 8), wraplength=px(660), justify="left").grid(
            row=14, column=0, columnspan=4, sticky="w")

        self.k = app.selected
        self._ref_changed()
        self._refresh_title()
        self.win.geometry(f"{px(720)}x{px(720)}")
        self._poll()

    # ---------------------------------------------------------------- état
    @property
    def cap(self):
        caps = self.app.captures
        return caps[self.k] if self.k is not None and self.k < len(caps) else None

    def _refresh_title(self):
        c = self.cap
        if c is None:
            self.title.configure(text="Sélectionnez un scan dans la liste de Lidar Plot")
            self.subtitle.configure(text="")
            return
        p = c["pose"]
        self.title.configure(text=f"Scan {c['k']}", fg=c["color"])
        zero = (p.x, p.y, p.theta) == (0, 0, 0)
        self.subtitle.configure(
            text=f"Pose saisie (référence) : x = {p.x:.3f} m, y = {p.y:.3f} m, θ = {np.degrees(p.theta):.1f}°"
                 + ("\n⚠ Pose à (0, 0, 0) : saisissez d'abord la position mesurée du robot." if zero else ""),
            fg=D["warn"] if zero else D["muted"])

    def _ref_changed(self):
        kind = self.ref_var.get()
        if kind.startswith("Fichier"):
            path = filedialog.askopenfilename(parent=self.win, title="Référence (grid map, carte vectorielle ou scan)",
                                              filetypes=[("Références", "*.npz *.txt *.csv"), ("Tous", "*.*")])
            if not path:
                self.ref_var.set(REF_CHOICES[0])
                return self._ref_changed()
            self.ref_file = path
            self._ref_cache.clear()
        names = list(L.METHODS)
        if kind.startswith("Carte vectorielle") or (self.ref_file and kind.startswith("Fichier")
                                                   and Path(self.ref_file).suffix.lower() == ".txt"):
            names.append("direct (murs)")
        self.meth_box.configure(values=[ALL] + names)
        if self.meth_var.get() not in [ALL] + names:
            self.meth_var.set(ALL)

    def step(self, d):
        n = len(self.app.captures)
        if not n:
            return
        self.k = 0 if self.k is None else (self.k + d) % n
        self.app.select(self.k) if self.app.selected != self.k else None
        self.results = []
        self.tree.delete(*self.tree.get_children())
        self.clear_overlay()
        self._refresh_title()

    # ------------------------------------------------------------ référence
    def _spec(self, c):
        """Tout ce dont le calcul a besoin, lu dans le fil principal (les variables
        Tk ne doivent pas être lues depuis le fil de calcul)."""
        caps = [o for o in self.app.captures if o is not c and o["visible"].get()]
        if self.same_var.get():
            caps = [o for o in caps if not _same_mark(o["pose"], c["pose"])]
        others = [(o["name"], o["k"], o["pose"], self.app._vis(o["scan"])) for o in caps]
        return dict(kind=self.ref_var.get(), file=self.ref_file, cell=self.app._cell(), pose=c["pose"],
                    others=others, key=(self.ref_var.get(), self.ref_file, c["name"], self.app._cell(),
                                        tuple((n, p.x, p.y, p.theta, len(v)) for n, _, p, v in others)))

    def _reference(self, spec):
        """(référence, description) ; calculée dans le fil de calcul, gardée en cache."""
        if spec["key"] in self._ref_cache:
            return self._ref_cache[spec["key"]]
        kind, others = spec["kind"], spec["others"]
        if kind.startswith("Fichier"):
            ref, desc = L.load_reference(spec["file"]), f"fichier {Path(spec['file']).name}"
        elif not others:
            raise ValueError("aucun autre scan visible pris à un autre repère : impossible de construire la référence")
        elif kind.startswith("Grid"):
            ref = L.GridRef(build_grid([(clean_scan(v), p) for _, _, p, v in others], spec["cell"]))
            desc = f"grid map de {len(others)} scans"
        elif kind.startswith("Carte"):
            ref = L.VectorRef(build_vector_map([(clean_scan(v), p) for _, _, p, v in others]).segments)
            desc = f"carte vectorielle de {len(others)} scans ({len(ref.segments)} segments)"
        else:
            q = spec["pose"]
            _, k, p, v = min(others, key=lambda o: np.hypot(o[2].x - q.x, o[2].y - q.y))
            d = np.hypot(p.x - q.x, p.y - q.y)
            ref = L.CloudRef(clean_scan(v).world_xy(p), point_to_line=True)
            desc = f"Scan {k} (à {d:.2f} m)" + ("  ⚠ loin : l'énoncé demande un scan pris PRÈS" if d > 1.5 else "")
        self._ref_cache[spec["key"]] = (ref, desc)
        return ref, desc

    # ------------------------------------------------------------ lancement
    def run(self):
        c = self.cap
        if c is None or self.busy:
            return
        start_i = START_CHOICES.index(self.start_var.get())
        meas = c["pose"]
        start = meas if start_i == 0 else perturb(meas, INIT_LEVELS[start_i], np.random.default_rng([c["k"], start_i]))
        meth = self.meth_var.get()
        names = [m for m in self.meth_box.cget("values") if m != ALL] if meth == ALL else [meth]
        local = clean_scan(self.app._vis(c["scan"])).local_xy()
        spec = self._spec(c)
        if len(local) < 20:
            return self._status("Trop peu de points dans ce scan.", D["error"])
        self.busy = True
        self.run_btn.state(["disabled"])
        self.tree.delete(*self.tree.get_children())
        self.results = []
        self.app.loc_overlay = [("Départ", c["scan"], start, D["warn"])]
        self.app._draw_captures()
        self._status("Construction de la référence…")

        def work():
            try:
                ref, desc = self._reference(spec)
                self.q.put(("status", f"Référence : {desc}. Localisation…", D["muted"]))
                for m in names:
                    r = L.localise(ref, local, start, m)
                    self.q.put(("result", c, m, r, start, start_i, desc))
                self.q.put(("done", f"Référence : {desc}. Départ à {self._dist(start, meas)} de la pose saisie.",
                            D["ok"]))
            except Exception as e:  # erreur affichée dans la fenêtre plutôt qu'une trace
                self.q.put(("done", f"Erreur : {e}", D["error"]))
        threading.Thread(target=work, daemon=True).start()

    @staticmethod
    def _dist(p, q):
        return (f"{np.hypot(p.x - q.x, p.y - q.y) * 100:.1f} cm / "
                f"{abs(np.degrees(L.wrap(p.theta - q.theta))):.1f}°")

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "status":
                    self._status(msg[1], msg[2])
                elif msg[0] == "result":
                    self._add_result(*msg[1:])
                elif msg[0] == "done":
                    self.busy = False
                    self.run_btn.state(["!disabled"])
                    self.eval_btn.state(["!disabled"])
                    verdict = self._consensus()
                    self._status(msg[1] + ("\n" + verdict[0] if verdict else ""), verdict[1] if verdict else msg[2])
                elif msg[0] == "eval_done":
                    self.busy = False
                    self.eval_btn.state(["!disabled"])
                    self.run_btn.state(["!disabled"])
                    self._status(f"Évaluation terminée : {msg[1]}", D["ok"])
                    rep = Path(msg[1]) / "synthese.md"
                    try:
                        os.startfile(rep if rep.exists() else msg[1])
                    except OSError:
                        pass
        except queue.Empty:
            pass
        if self.win.winfo_exists():
            self.win.after(100, self._poll)

    def _consensus(self):
        """Les méthodes itératives sont-elles d'accord entre elles ? Si oui et que
        leur pose est loin de la pose saisie, c'est probablement la MESURE qui
        est décalée (ou la référence construite avec d'autres mesures)."""
        c = self.cap
        rs = [r for m, r in self.results if not m.startswith("direct")]
        if c is None or len(rs) < 3:
            return None
        P = np.array([[r.pose.x, r.pose.y] for r in rs])
        th = np.array([r.pose.theta for r in rs])
        med = np.median(P, axis=0)
        med_th = np.arctan2(np.median(np.sin(th)), np.median(np.cos(th)))
        spread = float(np.max(np.hypot(*(P - med).T)))
        off = float(np.hypot(med[0] - c["pose"].x, med[1] - c["pose"].y))
        off_th = abs(np.degrees(L.wrap(med_th - c["pose"].theta)))
        if spread > 0.05:
            return (f"Les méthodes ne s'accordent pas (jusqu'à {spread * 100:.0f} cm d'écart entre elles) : "
                    "certaines se sont trompées. Essayez un départ plus proche ou une autre référence.", D["warn"])
        if off < SUCCESS_XY and off_th < SUCCESS_TH:
            return (f"Les méthodes s'accordent (à {spread * 100:.1f} cm près) avec votre pose saisie "
                    f"(écart {off * 100:.1f} cm / {off_th:.1f}°).", D["ok"])
        return (f"Les méthodes s'accordent entre elles (à {spread * 100:.1f} cm près) sur une pose à "
                f"{off * 100:.1f} cm / {off_th:.1f}° de votre pose saisie : c'est probablement la MESURE (ou les "
                "poses des scans de la référence) qui est décalée, pas la localisation. Vérifiez la marque au sol et la "
                "saisie x, y, θ.", D["warn"])

    def _add_result(self, c, m, r, start, start_i, desc):
        meas = c["pose"]
        e_xy = np.hypot(r.pose.x - meas.x, r.pose.y - meas.y)
        e_th = abs(np.degrees(L.wrap(r.pose.theta - meas.theta)))
        ok = e_xy < SUCCESS_XY and e_th < SUCCESS_TH
        self.results.append((m, r))
        iid = self.tree.insert("", "end", values=(
            m, f"{r.pose.x:.3f}, {r.pose.y:.3f}, {np.degrees(r.pose.theta):.1f}°",
            f"{e_xy * 100:.1f} cm / {e_th:.2f}°", "✓" if ok else "✗", f"{r.score:.2f}", f"{r.time_s * 1000:.0f} ms"))
        if len(self.results) == 1 or r.score > max(x[1].score for x in self.results[:-1]):
            self.tree.selection_set(iid)  # la meilleure (score le plus haut) est montrée sur la carte
        self._log(c, m, r, desc, START_CHOICES[start_i], e_xy, e_th, ok)

    def _log(self, c, m, r, desc, start, e_xy, e_th, ok):
        f = self.app.folder / "localisation_essais.csv"
        new = not f.exists()
        try:
            with open(f, "a", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh, delimiter=";")
                if new:
                    w.writerow(LOG_FIELDS)
                p, q = r.pose, c["pose"]
                num = lambda v, d=4: f"{v:.{d}f}".replace(".", ",")
                w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), c["name"], desc, start, m, num(p.x), num(p.y),
                            num(np.degrees(p.theta), 2), num(q.x), num(q.y), num(np.degrees(q.theta), 2),
                            num(e_xy), num(e_th, 3), int(ok), num(r.score, 3), num(r.time_s * 1000, 1)])
        except OSError as e:  # fichier ouvert dans Excel, par exemple
            self._status(f"Résultat non enregistré dans {f.name} : {e}", D["warn"])

    def _show_selected(self):
        sel = self.tree.selection()
        if not sel or self.cap is None:
            return
        m, r = self.results[self.tree.index(sel[0])]
        ov = [o for o in getattr(self.app, "loc_overlay", []) if o[0] == "Départ"]
        self.app.loc_overlay = ov + [(f"Trouvée ({m})", self.cap["scan"], r.pose, "#FFFFFF")]
        self.app._draw_captures()

    def apply(self):
        sel = self.tree.selection()
        c = self.cap
        if not sel or c is None:
            return
        m, r = self.results[self.tree.index(sel[0])]
        if not messagebox.askyesno("Appliquer", f"Remplacer la pose saisie du Scan {c['k']} par celle trouvée par "
                                                f"« {m} » ?\n\nSi la pose saisie est votre MESURE (référence du TP), "
                                                "gardez-la plutôt.", parent=self.win):
            return
        c["pose"] = Pose(r.pose.x, r.pose.y, r.pose.theta)
        self.app._save_poses()
        self.app._refresh_list()
        self.clear_overlay()
        self._refresh_title()

    def clear_overlay(self):
        self.app.loc_overlay = []
        self.app._draw_captures()

    def _status(self, text, color=None):
        self.status.configure(text=text, fg=color or D["muted"])

    # ------------------------------------------------------------ évaluation
    def evaluate(self):
        if self.busy:
            return
        um, ud = self.unc_m.get().strip(), self.unc_d.get().strip()
        try:
            unc = (float(um.replace(",", ".")), float(ud.replace(",", "."))) if um or ud else None
        except ValueError:
            return self._status("Incertitude : deux nombres, en mètres et en degrés (ex. 0.02 et 2), ou rien.", D["error"])
        caps = [c for c in self.app.captures if (c["pose"].x, c["pose"].y, c["pose"].theta) != (0, 0, 0)]
        if len(caps) < 2:
            return self._status("Il faut au moins 2 scans avec une pose saisie.", D["error"])
        if not messagebox.askyesno("Évaluation complète", f"Évaluer {len(caps)} scans avec toutes les méthodes ?\n"
                                   f"Durée estimée : {len(caps)} à {2 * len(caps)} minutes. Lidar Plot reste utilisable.",
                                   parent=self.win):
            return
        from carto.evaluation import evaluate
        self.busy = True
        self.eval_btn.state(["disabled"])
        self.run_btn.state(["disabled"])
        folder = self.app.folder

        def work():
            try:
                out = evaluate(str(folder / "localisation"), str(folder), "mesurees", incertitude=unc,
                               sans_simulation=True,
                               log=lambda t: self.q.put(("status", "Évaluation : " + t.strip(), D["muted"])))
                self.q.put(("eval_done", str(out)))
            except BaseException as e:  # SystemExit des contrôles d'entrée compris
                self.q.put(("done", f"Évaluation impossible : {e}", D["error"]))
        threading.Thread(target=work, daemon=True).start()

    def close(self):
        self.clear_overlay()
        self.app.loc_dialog = None
        self.win.destroy()
