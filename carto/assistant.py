"""Assistant de capture : guide pas à pas pour scanner une salle avec le LD06.

    python -m carto assistant                     (choisir le port dans la fenêtre)
    python -m carto assistant --folder data/salle (reprendre une session)

Déroulé :
  1. Connexion : choisir le port, ou « Détection auto » qui trouve le port et le
     montage (carte Arduino/Teensy ou LD06 direct). Si rien n'arrive, le guide
     dit pourquoi (aucun octet, texte illisible, paquets invalides...).
  2. Pour chaque position :
     - poser le lidar, mesurer (x, y, θ) au mètre et les saisir ;
     - le scan en direct (rouge) se superpose à la carte ; on peut le
       DÉPLACER À LA SOURIS (glisser) et le TOURNER (molette) pour l'aligner ;
     - le RECOUVREMENT et le contrôle en direct disent si la pose et le scan
       sont bons ; « Recaler » corrige la pose par corrélation avec la carte ;
       « Aligner θ sur les murs » rend les murs parallèles aux axes (1re position) ;
     - « Capturer » : N tours enregistrés, contrôlés, sauvés en CSV +
       poses.json + journal.json, intégrés à la grid map ;
     - les étoiles indiquent où aller ensuite (frontières libre / inconnu).
  3. « Terminer » : export des cartes (grid + vectorielle) et d'un rapport.md.
Mode « Simulation » : lidar virtuel dans la salle simulée, CLIC DROIT sur la
carte pour le poser (la pose « mesurée » est remplie avec une erreur réaliste).
"""
from __future__ import annotations

import json
import os
import shutil
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from carto import theme
from carto.gridmap import OccupancyGrid
from carto.guide import (ERROR, OK, WARN, frontier_mask, likelihood_field, live_check, overlap_level,
                         overlap_ratio, refine_pose, scan_quality, suggest_next, theta_aligned_on_walls)
from carto.scan import Pose, Scan, load_scan_file, save_poses, save_scan_csv
from carto.theme import C, FONT
from carto.vectormap import build_vector_map
from ld06.sources import SerialSource, SimSource, detect_port_and_mode, list_serial_ports

SIM_LABEL = "Simulation (sans lidar)"
LEVEL_COLOR = {OK: C["ok"], WARN: C["warn"], ERROR: C["error"], "info": C["text"], "muted": C["muted"],
               "title": C["text"]}
LEVEL_ICON = {OK: "✓", WARN: "!", ERROR: "✕"}
NO_DATA_DELAY_S = 6.0


def scan_from_dict(d, name="live") -> Scan:
    return Scan(name, np.radians(d["angle_deg"]), np.asarray(d["distance_mm"], float) / 1000.0,
                np.asarray(d["intensity"], float), {"speed_dps": d.get("speed_dps", 0)})


def diagnose_no_data(src: SerialSource) -> list[tuple[str, str]]:
    """Pourquoi aucun tour n'arrive ? D'après ce que le thread de lecture a vu."""
    if src.bytes_received == 0:
        return [(ERROR, f"Aucun octet reçu sur {src.port} depuis {NO_DATA_DELAY_S:.0f} s."),
                ("info", "• Le lidar tourne-t-il ? (alimentation 5 V, GND commun)"),
                ("info", "• Montage carte : le sketch LD06_capture est-il téléversé ? Tx du lidar sur RX1 ?"),
                ("info", "• Montage direct : Tx du lidar sur RX de l'adaptateur ?"),
                ("info", "• Est-ce le bon port ? Essayez « Détection auto ».")]
    if src.mode == "arduino":
        if src.lines_received > 0:
            return [(ERROR, f"Du texte arrive ({src.lines_received} lignes) mais pas au format CSV attendu."),
                    ("info", "• C'est peut-être l'exemple Basic (format Teleplot) : téléversez LD06_capture."),
                    ("info", "• Caractères illisibles = mauvais débit. Ou c'est le LD06 en direct : "
                             "essayez « Détection auto » ou le mode « LD06 direct ».")]
        return [(ERROR, "Des octets arrivent mais aucune ligne complète."),
                ("info", "• Probablement le LD06 en direct : choisissez « LD06 direct (USB-UART) ».")]
    if src.packets_ok == 0:
        return [(ERROR, f"{src.bytes_received} octets reçus mais aucun paquet LD06 valide "
                        f"({src.crc_failures} CRC faux)."),
                ("info", "• C'est peut-être une carte Arduino qui envoie du texte : mode « Carte Arduino/Teensy »."),
                ("info", "• Sinon : câble trop long / mauvais contact sur Tx.")]
    return [(WARN, f"{src.packets_ok} paquets valides mais pas encore de tour complet."),
            ("info", "• Le lidar tourne-t-il assez vite ? (5 à 13 tr/s)")]


class CaptureAssistant:
    def __init__(self, root: tk.Tk, folder="data/salle", n_scans=5):
        self.root = root
        self.folder = Path(folder)
        self.source = None
        self.live: Scan | None = None
        self.capture_buf: list | None = None
        self.capture_needed = 0
        self.positions: dict[str, dict] = {}   # nom -> {"pose", "scans", "files", "overlap"}
        self.grid: OccupancyGrid | None = None
        self.field = None
        self.suggestions = []
        self._last_live_draw = 0.0
        self._last_live_check = 0.0
        self._connected_at = 0.0
        self._last_scan_at = 0.0
        self._diag_shown = False
        self._drag = None
        self._detect = None          # état de la détection auto (thread)
        self._setting_pose = False
        self.exported = False
        self.scale = theme.apply(root)
        root.title("Assistant de capture LD06")
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{min(int(1400 * self.scale), w - 40)}x{min(int(860 * self.scale), h - 80)}+10+10")
        root.minsize(int(1000 * self.scale), int(640 * self.scale))
        try:
            root.state("zoomed")  # plein écran sous Windows
        except tk.TclError:
            pass
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._build_ui(n_scans)
        self.refresh_ports()
        self.load_session(self.folder, quiet=True)
        self._tick()

    def px(self, v):
        return int(v * self.scale)

    # ================================================================== UI
    def _build_ui(self, n_scans):
        px = self.px
        # ---------------------------------------------------------- en-tête
        header = tk.Frame(self.root, bg=C["header"])
        header.pack(fill="x")
        left_h = tk.Frame(header, bg=C["header"])
        left_h.pack(side="left", padx=px(18), pady=px(10))
        tk.Label(left_h, text="◉  Assistant de capture LD06", bg=C["header"], fg=C["header_text"],
                 font=(FONT, 14, "bold")).pack(anchor="w")
        sub = tk.Frame(left_h, bg=C["header"])
        sub.pack(anchor="w")
        self.session_lbl = tk.Label(sub, text="", bg=C["header"], fg=C["header_muted"], font=(FONT, 9))
        self.session_lbl.pack(side="left")
        change = tk.Label(sub, text="  Changer de dossier…", bg=C["header"], fg="#93C5FD",
                          font=(FONT, 9, "underline"), cursor="hand2")
        change.pack(side="left")
        change.bind("<Button-1>", lambda e: self.choose_folder())
        self.steps = []
        steps_f = tk.Frame(header, bg=C["header"])
        steps_f.pack(side="right", padx=px(18))
        for k, lab in enumerate(("Connexion", "1re position", "Couverture", "Rapport"), 1):
            l = tk.Label(steps_f, text="", font=(FONT, 9, "bold"), padx=px(10), pady=px(4))
            l.pack(side="left", padx=px(3))
            self.steps.append((l, k, lab))

        body = ttk.Frame(self.root, style="Bg.TFrame")
        body.pack(fill="both", expand=True, padx=px(12), pady=px(12))

        # ---------------------------------------------------- panneau droit
        side = ttk.Frame(body, style="Bg.TFrame", width=px(440))
        side.pack(side="right", fill="y", padx=(px(12), 0))
        side.pack_propagate(False)

        # 1. connexion
        f, _ = theme.card(side, "1 · Connexion", self.scale)
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)
        row = ttk.Frame(f, style="Card.TFrame")
        row.grid(row=0, column=0, columnspan=2, sticky="we")
        self.src_var = tk.StringVar()
        self.src_box = ttk.Combobox(row, textvariable=self.src_var, state="readonly")
        self.src_box.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="↻", style="Small.TButton", command=self.refresh_ports).pack(side="left", padx=(px(4), 0))
        self.mode_var = tk.StringVar(value="arduino")
        ttk.Radiobutton(f, text="Carte Arduino/Teensy", variable=self.mode_var, value="arduino").grid(
            row=1, column=0, sticky="w", pady=px(4))
        ttk.Radiobutton(f, text="LD06 direct (USB-UART)", variable=self.mode_var, value="raw").grid(
            row=1, column=1, sticky="w", pady=px(4))
        self.conn_btn = ttk.Button(f, text="Connecter", style="Accent.TButton", command=self.toggle_connection)
        self.conn_btn.grid(row=2, column=0, sticky="we", padx=(0, px(3)))
        self.detect_btn = ttk.Button(f, text="Détection auto", command=self.auto_detect)
        self.detect_btn.grid(row=2, column=1, sticky="we", padx=(px(3), 0))
        st = ttk.Frame(f, style="Card.TFrame")
        st.grid(row=3, column=0, columnspan=2, sticky="we", pady=(px(6), 0))
        self.status_dot = tk.Label(st, text="●", bg=C["card"], fg="#CBD5E1", font=(FONT, 10))
        self.status_dot.pack(side="left")
        self.status = tk.Label(st, text="Non connecté", bg=C["card"], fg=C["muted"], font=(FONT, 9),
                               anchor="w", justify="left", wraplength=px(380))
        self.status.pack(side="left", fill="x")

        # 2. position
        f, _ = theme.card(side, "2 · Position", self.scale, "mesurez au mètre puis ajustez")
        for c in range(6):
            f.columnconfigure(c, weight=1 if c in (1, 4) else 0)
        ttk.Label(f, text="Nom").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar(value="pos1")
        ttk.Entry(f, textvariable=self.name_var, width=8).grid(row=0, column=1, sticky="we", padx=px(4))
        ttk.Label(f, text="Tours").grid(row=0, column=3, sticky="e", padx=(px(8), 0))
        self.n_var = tk.IntVar(value=n_scans)
        ttk.Spinbox(f, from_=1, to=30, textvariable=self.n_var, width=4).grid(row=0, column=4, sticky="w", padx=px(4))
        self.pose_vars = {}
        for i, (k, lab, step) in enumerate((("x", "x  (m)", 0.05), ("y", "y  (m)", 0.05), ("t", "θ  (°)", 1.0))):
            r = 1 + i
            ttk.Label(f, text=lab).grid(row=r, column=0, sticky="w", pady=px(2))
            v = tk.StringVar(value="0")
            ttk.Entry(f, textvariable=v, width=9, font=(FONT, 10, "bold")).grid(
                row=r, column=1, sticky="we", padx=px(4), pady=px(2))
            v.trace_add("write", lambda *_: self._pose_changed())
            self.pose_vars[k] = v
            ttk.Button(f, text="−", width=2, style="Small.TButton",
                       command=lambda k=k, s=step: self.nudge(k, -s)).grid(row=r, column=2, padx=px(1))
            ttk.Button(f, text="+", width=2, style="Small.TButton",
                       command=lambda k=k, s=step: self.nudge(k, s)).grid(row=r, column=3, padx=px(1), sticky="w")
        ttk.Label(f, text="Sur la carte : glisser = déplacer · molette = tourner (Maj : fin)",
                  style="Muted.TLabel").grid(row=4, column=0, columnspan=6, sticky="w", pady=(px(4), px(6)))

        ov = ttk.Frame(f, style="Card.TFrame")
        ov.grid(row=5, column=0, columnspan=6, sticky="we")
        ttk.Label(ov, text="Recouvrement avec la carte", font=(FONT, 9, "bold")).pack(side="left")
        self.ov_value = tk.Label(ov, text="—", bg=C["card"], fg=C["muted"], font=(FONT, 11, "bold"))
        self.ov_value.pack(side="right")
        self.ov_bar = ttk.Progressbar(f, maximum=100, style="muted.Horizontal.TProgressbar")
        self.ov_bar.grid(row=6, column=0, columnspan=6, sticky="we", pady=(px(2), px(2)))
        self.ov_hint = tk.Label(f, text="", bg=C["card"], fg=C["muted"], font=(FONT, 9), anchor="w")
        self.ov_hint.grid(row=7, column=0, columnspan=6, sticky="we")
        self.live_lbl = tk.Label(f, text="", bg=C["card"], fg=C["muted"], font=(FONT, 9), anchor="w",
                                 justify="left", wraplength=px(390))
        self.live_lbl.grid(row=8, column=0, columnspan=6, sticky="we", pady=(px(2), px(6)))
        b = ttk.Frame(f, style="Card.TFrame")
        b.grid(row=9, column=0, columnspan=6, sticky="we")
        b.columnconfigure(0, weight=1)
        b.columnconfigure(1, weight=1)
        ttk.Button(b, text="⤧  Recaler sur la carte", command=self.refine).grid(row=0, column=0, sticky="we",
                                                                              padx=(0, px(3)))
        ttk.Button(b, text="∟  Aligner θ sur les murs", command=self.align_walls).grid(row=0, column=1, sticky="we",
                                                                                     padx=(px(3), 0))
        self.cap_btn = ttk.Button(f, text="●  Capturer cette position", style="Accent.TButton",
                                  command=self.start_capture)
        self.cap_btn.grid(row=10, column=0, columnspan=6, sticky="we", pady=(px(8), 0))

        # 3. positions
        f, _ = theme.card(side, "3 · Positions capturées", self.scale)
        cols = ("x", "y", "θ", "tours", "recouv.")
        self.tree = ttk.Treeview(f, columns=cols, height=4, selectmode="browse")
        self.tree.heading("#0", text="position")
        self.tree.column("#0", width=px(70), stretch=False)
        for c, w in zip(cols, (52, 52, 52, 44, 64)):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=px(w), anchor="center", stretch=True)
        self.tree.tag_configure("ok", foreground=C["ok"])
        self.tree.tag_configure("warn", foreground=C["warn"])
        self.tree.tag_configure("error", foreground=C["error"])
        self.tree.pack(fill="x")
        bb = ttk.Frame(f, style="Card.TFrame")
        bb.pack(fill="x", pady=(px(6), 0))
        ttk.Button(bb, text="Retirer la sélection", command=self.remove_position).pack(side="left")
        self.finish_btn = ttk.Button(bb, text="✓  Terminer : cartes + rapport", style="Success.TButton",
                                     command=self.finish)
        self.finish_btn.pack(side="right")

        # ------------------------------------------------- carte + guide
        main = ttk.Frame(body, style="Bg.TFrame")
        main.pack(side="left", fill="both", expand=True)

        gf, gouter = theme.card(main, "Guide", self.scale)
        gouter.pack_configure(side="bottom", fill="x", pady=(px(8), 0))
        self.guide = tk.Text(gf, wrap="word", height=8, font=(FONT, 10), relief="flat", bg=C["card"],
                             fg=C["text"], padx=px(2), pady=px(2), highlightthickness=0, cursor="arrow")
        sb = ttk.Scrollbar(gf, command=self.guide.yview)
        self.guide.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.guide.pack(fill="both", expand=True)
        for tag, col in LEVEL_COLOR.items():
            self.guide.tag_configure(tag, foreground=col)
        self.guide.tag_configure("title", font=(FONT, 11, "bold"), spacing1=px(2), spacing3=px(3))
        for lvl in (OK, WARN, ERROR):
            self.guide.tag_configure(f"icon_{lvl}", foreground="white", background=LEVEL_COLOR[lvl],
                                     font=(FONT, 8, "bold"))

        mouter = tk.Frame(main, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
        mouter.pack(fill="both", expand=True)
        self.fig = Figure(figsize=(9, 7), dpi=100 * self.scale, facecolor=C["card"])
        self.ax = self.fig.add_axes([0.06, 0.07, 0.92, 0.9])
        self.canvas = FigureCanvasTkAgg(self.fig, master=mouter)
        tb_frame = tk.Frame(mouter, bg=C["card"])
        tb_frame.pack(side="bottom", fill="x")
        self.toolbar = NavigationToolbar2Tk(self.canvas, tb_frame, pack_toolbar=False)
        self.toolbar.configure(background=C["card"])
        for child in self.toolbar.winfo_children():
            try:
                child.configure(background=C["card"])
            except tk.TclError:
                pass
        self.toolbar.pack(side="left", padx=px(6))
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=px(4), pady=px(4))
        for ev, cb in (("button_press_event", self._on_press), ("motion_notify_event", self._on_motion),
                       ("button_release_event", self._on_release), ("scroll_event", self._on_scroll)):
            self.canvas.mpl_connect(ev, cb)

    def say(self, lines, clear=True):
        """lines : liste de (niveau, texte)."""
        self.guide.configure(state="normal")
        if clear:
            self.guide.delete("1.0", "end")
        for lvl, txt in lines:
            if lvl in LEVEL_ICON:
                self.guide.insert("end", f" {LEVEL_ICON[lvl]} ", f"icon_{lvl}")
                self.guide.insert("end", "  " + txt + "\n", lvl)
            else:
                self.guide.insert("end", txt + "\n", lvl)
        self.guide.configure(state="disabled")
        self.guide.see("end" if not clear else "1.0")

    def _status(self, text, lvl="muted"):
        col = {"muted": "#CBD5E1", "info": C["primary"]}.get(lvl, LEVEL_COLOR.get(lvl, C["muted"]))
        self.status_dot.configure(fg=col)
        self.status.configure(text=text, fg=C["muted"] if lvl == "muted" else C["text"])

    def _update_progress(self):
        n = len(self.positions)
        done = [self.source is not None and self.live is not None, n >= 1,
                n >= 3 and not self.suggestions, self.exported]
        current = next((i for i, d in enumerate(done) if not d), None)
        for i, (lbl, k, text) in enumerate(self.steps):
            extra = f" ({n})" if k == 3 and n else ""
            if done[i]:
                lbl.configure(text=f"✓  {text}{extra}", bg=C["ok"], fg="white")
            elif i == current:
                lbl.configure(text=f"{k}  {text}{extra}", bg=C["primary"], fg="white")
            else:
                lbl.configure(text=f"{k}  {text}{extra}", bg="#1E293B", fg=C["header_muted"])

    # ============================================================ connexion
    def refresh_ports(self):
        ports = list_serial_ports()
        values = [f"{dev} — {desc}" for dev, desc in ports] + [SIM_LABEL]
        self.src_box["values"] = values
        if self.src_var.get() not in values:
            self.src_var.set(values[0])
        if not ports:
            self._status("Aucun port série : carte branchée ? câble data ? pilote ?", WARN)
        return ports

    def toggle_connection(self):
        if self.source:
            self.source.stop()
            self.source = None
            self.live = None
            self.conn_btn.configure(text="Connecter", style="Accent.TButton")
            self._status("Déconnecté")
            self.redraw()
            return
        choice = self.src_var.get()
        if choice == SIM_LABEL:
            self.source = SimSource(Pose(1.5, 1.5, np.radians(10))).start()
            self.say([("title", "Mode simulation"),
                      ("info", "Un lidar virtuel est posé dans une salle simulée en L (8 × 6 m). "
                               "Clic droit sur la carte pour le déplacer : la pose « mesurée » est remplie "
                               "avec une petite erreur, comme une mesure au mètre.")])
            self._place_sim(1.5, 1.5)
        else:
            port = choice.split(" — ")[0]
            self.source = SerialSource(port, self.mode_var.get()).start()
            self._welcome()
        self._connected_at, self._diag_shown = time.time(), False
        self.conn_btn.configure(text="Déconnecter", style="TButton")
        self._status("Connexion… en attente du premier tour", "info")

    def auto_detect(self):
        if self._detect:
            return
        if self.source:
            self.toggle_connection()
        ports = [p for p, _ in self.refresh_ports()]
        if not ports:
            return self.say([(ERROR, "Aucun port série à tester."),
                             ("info", "Branchez la carte (ou l'adaptateur) en USB. Si rien n'apparaît : "
                                      "câble « charge seule » ou pilote manquant (CH340, CP210x, Teensyduino).")])
        self.detect_btn.configure(state="disabled")
        self.conn_btn.configure(state="disabled")
        state = {"log": "", "result": None, "done": False}

        def work():
            state["result"] = detect_port_and_mode(ports, log=lambda m: state.__setitem__("log", m))
            state["done"] = True

        threading.Thread(target=work, daemon=True).start()
        self._detect = state
        self.say([("title", "Détection automatique"),
                  ("info", f"J'écoute {len(ports)} port(s) en mode carte puis en mode direct "
                           "(environ 5 s par port)…")])

    def _poll_detect(self):
        st = self._detect
        if not st:
            return
        if not st["done"]:
            self._status(f"Détection : {st['log']}", "info")
            return
        self._detect = None
        self.detect_btn.configure(state="normal")
        self.conn_btn.configure(state="normal")
        if st["result"] is None:
            self._status("Détection : aucun lidar trouvé", ERROR)
            self.say([(ERROR, "Aucun port ne renvoie de données LD06."),
                      ("info", "• Le lidar tourne-t-il ? • Moniteur série de l'IDE fermé ? "
                               "• Sketch LD06_capture téléversé ? • Tx du lidar sur RX ?")])
            return
        port, mode = st["result"]
        self.mode_var.set(mode)
        for v in self.src_box["values"]:
            if v.split(" — ")[0] == port:
                self.src_var.set(v)
        self.say([(OK, f"Lidar trouvé sur {port} en mode "
                       f"{'carte Arduino/Teensy' if mode == 'arduino' else 'LD06 direct'}. Connexion…")])
        self.toggle_connection()

    def _welcome(self):
        if self.positions:
            return self._advise()
        self.say([("title", "Première position"),
                  ("info", "1.  Choisissez l'origine de la carte : un coin de la salle. L'axe x suit un mur, "
                           "l'axe y l'autre mur (sens trigo)."),
                  ("info", "2.  Posez le lidar à plat, à 1-2 m des murs, sans rien collé contre lui."),
                  ("info", "3.  Mesurez au mètre le centre du lidar (x, y) et l'angle θ de sa flèche "
                           "par rapport à l'axe x (0° = vers +x, 90° = vers +y)."),
                  ("info", "4.  Saisissez x, y, θ, puis « Aligner θ sur les murs » : toute la carte dépend "
                           "de cette première orientation."),
                  ("info", "5.  « Capturer ». Ne touchez plus le lidar et sortez de son champ.")])

    # ============================================================== session
    def choose_folder(self):
        d = filedialog.askdirectory(initialdir=str(self.folder.resolve().parent))
        if d:
            self.load_session(Path(d))

    def load_session(self, folder: Path, quiet=False):
        self.folder = Path(folder)
        self.session_lbl.configure(text=f"Session : {self.folder.resolve()}")
        self.positions = {}
        self.exported = (self.folder / "rapport" / "rapport.md").exists()
        poses = {}
        pj = self.folder / "poses.json"
        if pj.exists():
            poses = {k: Pose.from_list_deg(v) for k, v in json.loads(pj.read_text(encoding="utf-8")).items()}
        overlaps = {e["position"]: e.get("recouvrement") for e in self._journal()}
        for f in sorted(self.folder.glob("*.csv")) if self.folder.exists() else []:
            name = f.stem.rsplit("_", 1)[0]
            scans = load_scan_file(f)
            pos = self.positions.setdefault(name, {"pose": poses.get(f.stem, Pose()), "scans": [], "files": [],
                                                   "overlap": overlaps.get(name)})
            pos["scans"] += scans
            pos["files"].append(f)
        self._rebuild_map()
        self._next_name()
        if not quiet or self.positions:
            self._advise()
        else:
            self.say([("title", "Bienvenue"),
                      ("info", "Branchez la carte en USB puis « Détection auto », ou choisissez le port "
                               "vous-même (ou « Simulation (sans lidar) » pour vous entraîner) et « Connecter ».")])

    def _next_name(self):
        k = 1
        while f"pos{k}" in self.positions:
            k += 1
        self.name_var.set(f"pos{k}")

    def _rebuild_map(self):
        self.grid = None
        for pos in self.positions.values():
            for s in pos["scans"]:
                fs = s.filtered()
                if self.grid is None:
                    self.grid = OccupancyGrid.from_scan(fs, pos["pose"])
                else:
                    self.grid.update(fs, pos["pose"])
        self.field = likelihood_field(self.grid) if self.grid is not None else None
        self.suggestions = suggest_next(self.grid, [p["pose"] for p in self.positions.values()]) if self.grid else []
        self.tree.delete(*self.tree.get_children())
        for name, pos in self.positions.items():
            p, ov = pos["pose"], pos.get("overlap")
            tag = "" if ov is None else overlap_level(ov)
            self.tree.insert("", "end", iid=name, text=f"  {name}", tags=(tag,),
                             values=(f"{p.x:.2f}", f"{p.y:.2f}", f"{np.degrees(p.theta):.0f}°",
                                     len(pos["scans"]), "réf." if ov is None else f"{ov:.0%}"))
        self.redraw()

    def remove_position(self):
        sel = self.tree.selection()
        if not sel:
            return self.say([("info", "Sélectionnez d'abord une position dans le tableau.")], clear=False)
        name = sel[0]
        if not messagebox.askyesno("Retirer", f"Retirer {name} de la carte ?\n"
                                              "Ses fichiers sont déplacés dans le sous-dossier _retires/."):
            return
        trash = self.folder / "_retires"
        trash.mkdir(exist_ok=True)
        for f in self.positions[name]["files"]:
            shutil.move(str(f), str(trash / f.name))
        del self.positions[name]
        self._save_poses()
        self._rebuild_map()
        self._next_name()
        self._advise()

    def _save_poses(self):
        poses = {}
        for pos in self.positions.values():
            for f in pos["files"]:
                poses[Path(f).stem] = pos["pose"]
        if self.folder.exists():
            save_poses(self.folder / "poses.json", poses)

    # ================================================================= pose
    def get_pose(self) -> Pose | None:
        try:
            x, y, t = (float(self.pose_vars[k].get().replace(",", ".")) for k in ("x", "y", "t"))
        except ValueError:
            return None
        return Pose(x, y, np.radians(t))

    def set_pose(self, p: Pose):
        self._setting_pose = True  # une seule mise à jour pour les 3 champs
        for k, v in (("x", p.x), ("y", p.y), ("t", np.degrees((p.theta + np.pi) % (2 * np.pi) - np.pi))):
            self.pose_vars[k].set(f"{v:.2f}" if k != "t" else f"{v:.1f}")
        self._setting_pose = False
        self._pose_changed()

    def nudge(self, k, step):
        try:
            v = float(self.pose_vars[k].get().replace(",", "."))
        except ValueError:
            v = 0.0
        self.pose_vars[k].set(f"{v + step:.2f}" if k != "t" else f"{v + step:.1f}")

    def _pose_changed(self):
        if self._setting_pose:
            return
        self._update_overlap()
        self._draw_live()

    def _update_overlap(self):
        pose = self.get_pose()
        if self.live is None or pose is None or self.grid is None:
            first = self.grid is None
            self.ov_value.configure(text="—", fg=C["muted"])
            self.ov_bar.configure(value=0, style="muted.Horizontal.TProgressbar")
            self.ov_hint.configure(text="Première position : c'est elle qui fixe le repère de la carte."
                                   if first else "En attente du scan en direct…", fg=C["muted"])
            return None
        ov = overlap_ratio(self.grid, self.live, pose, self.field)
        lvl = overlap_level(ov)
        hint = {OK: "Pose cohérente avec la carte.",
                WARN: "À vérifier : alignez à la souris ou « Recaler » (ou zone très nouvelle).",
                ERROR: "Pose fausse ou aucun mur en commun."}[lvl]
        self.ov_value.configure(text=f"{ov:.0%}", fg=LEVEL_COLOR[lvl])
        self.ov_bar.configure(value=100 * ov, style=f"{lvl}.Horizontal.TProgressbar")
        self.ov_hint.configure(text=hint, fg=LEVEL_COLOR[lvl])
        return ov

    def _update_live_check(self):
        if self.live is None:
            self.live_lbl.configure(text="", fg=C["muted"])
            return
        issues = live_check(self.live)
        if not issues:
            self.live_lbl.configure(text=f"✓  Scan en direct : {len(self.live)} points, rien à signaler",
                                    fg=C["ok"])
        else:
            lvl = ERROR if any(l == ERROR for l, _ in issues) else WARN
            self.live_lbl.configure(text=f"{LEVEL_ICON[lvl]}  {issues[0][1]}", fg=LEVEL_COLOR[lvl])

    def refine(self):
        pose = self.get_pose()
        if self.grid is None or self.live is None or pose is None:
            self.say([(WARN, "Le recalage a besoin d'au moins une position déjà capturée, "
                             "d'un lidar connecté et d'une pose saisie. Pour la 1re position : "
                             "« Aligner θ sur les murs ».")], clear=False)
            return
        new, before, after = refine_pose(self.grid, self.live, pose)
        dx, dy, dt = new.x - pose.x, new.y - pose.y, np.degrees(new.theta - pose.theta)
        if after is None or after <= before + 0.02:
            self.say([("info", f"Recalage : pas d'amélioration (recouvrement {before:.0%}). Si la pose est "
                               "fausse de plus de 40 cm ou 8°, rapprochez-la d'abord à la souris.")], clear=False)
            return
        if messagebox.askyesno("Recalage", f"Pose proposée : x={new.x:.2f}  y={new.y:.2f}  "
                                          f"θ={np.degrees(new.theta):.1f}°\n"
                                          f"(correction {dx * 100:+.0f} cm, {dy * 100:+.0f} cm, {dt:+.1f}°)\n"
                                          f"Recouvrement {before:.0%} → {after:.0%}\n\nAppliquer ?"):
            self.set_pose(new)
            msg = [(OK, f"Pose recalée ({dx * 100:+.0f} cm, {dy * 100:+.0f} cm, {dt:+.1f}°).")]
            if np.hypot(dx, dy) > 0.25 or abs(dt) > 5:
                msg.append((WARN, "Grosse correction : vérifiez votre mesure au mètre "
                                  "(confusion de mur de référence ? sens de θ ?)."))
            self.say(msg, clear=False)

    def align_walls(self):
        pose = self.get_pose()
        if self.live is None or pose is None:
            return self.say([(WARN, "Connectez le lidar et saisissez une pose d'abord.")], clear=False)
        th = theta_aligned_on_walls(self.live, pose.theta)
        if th is None:
            return self.say([(WARN, "Pas assez de murs droits et perpendiculaires dans le scan pour "
                                    "en déduire l'angle. Gardez votre mesure.")], clear=False)
        dt = np.degrees(th - pose.theta)
        if abs(dt) < 0.1:
            return self.say([(OK, "θ déjà aligné sur les murs.")], clear=False)
        if messagebox.askyesno("Aligner θ", f"θ mesuré : {np.degrees(pose.theta):.1f}°\n"
                                           f"θ aligné sur les murs : {np.degrees(th):.1f}° (correction {dt:+.1f}°)\n\n"
                                           "Hypothèse : les murs de la salle sont perpendiculaires et l'axe x "
                                           "de la carte suit un mur.\nAppliquer ?"):
            self.set_pose(Pose(pose.x, pose.y, th))
            msg = [(OK, f"θ corrigé de {dt:+.1f}°.")]
            if abs(dt) > 10:
                msg.append((WARN, "Correction > 10° : vérifiez le sens de la flèche et le sens de θ "
                                  "(trigo : 90° = vers +y)."))
            self.say(msg, clear=False)

    # ============================================================ souris
    def _mouse_ok(self, e):
        return (e.inaxes is self.ax and self.capture_buf is None and not getattr(self.toolbar, "mode", "")
                and e.xdata is not None)

    def _on_press(self, e):
        if not self._mouse_ok(e):
            return
        if e.button == 3 and isinstance(self.source, SimSource):
            self._place_sim(e.xdata, e.ydata)
        elif e.button == 1 and self.live is not None and self.get_pose() is not None:
            self._drag = (e.xdata, e.ydata)
            self.canvas.get_tk_widget().configure(cursor="fleur")

    def _on_motion(self, e):
        if self._drag is None or not self._mouse_ok(e):
            return
        p = self.get_pose()
        dx, dy = e.xdata - self._drag[0], e.ydata - self._drag[1]
        self._drag = (e.xdata, e.ydata)
        self.set_pose(Pose(p.x + dx, p.y + dy, p.theta))

    def _on_release(self, e):
        self._drag = None
        self.canvas.get_tk_widget().configure(cursor="")

    def _on_scroll(self, e):
        if not self._mouse_ok(e) or self.live is None:
            return
        p = self.get_pose()
        if p is None:
            return
        step = 0.2 if e.key == "shift" else 1.0
        self.set_pose(Pose(p.x, p.y, p.theta + np.radians(step if e.button == "up" else -step)))

    # ============================================================== capture
    def start_capture(self):
        if not self.source:
            return self.say([(ERROR, "Connectez d'abord le lidar (étape 1).")], clear=False)
        if self.live is None:
            return self.say([(ERROR, "Aucun tour reçu pour l'instant : attendez le scan rouge.")], clear=False)
        if self.get_pose() is None:
            return self.say([(ERROR, "Pose invalide : x, y, θ doivent être des nombres.")], clear=False)
        name = self.name_var.get().strip()
        if not name or "_" in name:
            return self.say([(ERROR, "Nom de position invalide (pas de « _ »).")], clear=False)
        if name in self.positions and not messagebox.askyesno("Position existante", f"{name} existe déjà : remplacer ?"):
            return
        # on jette le premier tour reçu : il a pu commencer avant le clic (main sur le lidar...)
        self.capture_buf, self.capture_needed = [], self.n_var.get() + 1
        self.cap_btn.configure(state="disabled")
        self.say([("title", f"Capture de {name}…"),
                  ("info", "Ne touchez plus le lidar et restez hors de son champ.")])

    def _finish_capture(self):
        raw = self.capture_buf[1:self.capture_needed]  # plusieurs tours peuvent arriver d'un coup
        self.capture_buf = None
        self.cap_btn.configure(state="normal", text="●  Capturer cette position")
        name, pose = self.name_var.get().strip(), self.get_pose()
        scans = [scan_from_dict(d, f"{name}_{k:03d}") for k, d in enumerate(raw)]
        rep = scan_quality(scans)
        ov = overlap_ratio(self.grid, scans[0], pose, self.field) if self.grid is not None else None
        lines = [("title", f"Contrôle de {name}")] + rep.messages
        if ov is not None:
            lvl = overlap_level(ov)
            lines.append((lvl, f"Recouvrement avec la carte : {ov:.0%}" +
                          ("" if lvl == OK else " — pose à vérifier, ou pas assez de murs en commun.")))
        bad = rep.level == ERROR or (ov is not None and overlap_level(ov) == ERROR)
        self.say(lines)
        if bad and not messagebox.askyesno("Problème détecté", "La capture semble mauvaise (voir le guide).\n"
                                                              "La garder quand même ?"):
            self.say([("info", "Capture abandonnée : corrigez le problème puis recapturez.")], clear=False)
            return
        self.folder.mkdir(parents=True, exist_ok=True)
        old = self.positions.pop(name, None)
        for f in (old or {}).get("files", []):
            Path(f).unlink(missing_ok=True)  # remplacement demandé par l'utilisateur
        files = []
        for k, d in enumerate(raw):
            f = self.folder / f"{name}_{k:03d}.csv"
            save_scan_csv(f, d["angle_deg"], d["distance_mm"], d["intensity"],
                          meta={"speed_dps": d.get("speed_dps", 0), "pose": "%.3f;%.3f;%.2f" % (
                              pose.x, pose.y, np.degrees(pose.theta))})
            files.append(f)
        self.positions[name] = {"pose": pose, "scans": scans, "files": files, "overlap": ov}
        self.exported = False
        self._save_poses()
        self._log(name, pose, rep, ov)
        self._rebuild_map()
        self._next_name()
        self._advise(prefix=lines + [(OK, f"{len(files)} tours enregistrés dans {self.folder}.")])

    def _journal(self) -> list:
        log = self.folder / "journal.json"
        return json.loads(log.read_text(encoding="utf-8")) if log.exists() else []

    def _log(self, name, pose, rep, ov):
        entries = self._journal()
        entries.append({"position": name, "date": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "pose": pose.as_list_deg(), "recouvrement": ov, "stats": rep.stats,
                        "messages": rep.messages})
        (self.folder / "journal.json").write_text(json.dumps(entries, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")

    def _advise(self, prefix=None):
        lines = list(prefix or [])
        n = len(self.positions)
        if n == 0:
            self._welcome()
            return
        lines.append(("title", "Et maintenant ?"))
        if self.suggestions:
            lines.append(("info", "Zones encore inconnues : allez vers les étoiles numérotées "
                                  "(la plus grande frontière d'abord)."))
            for k, s in enumerate(self.suggestions, 1):
                lines.append(("info", f"     ★ {k}   x ≈ {s.x:.1f} m,  y ≈ {s.y:.1f} m   "
                                      f"(frontière de {s.frontier_m:.1f} m)"))
            lines.append(("muted", "Gardez au moins 2 murs en commun avec la carte ; "
                                   "1 à 2 m de déplacement suffit."))
        elif n < 3:
            lines.append(("info", "Plus de frontière visible, mais faites au moins 3 positions pour "
                                  "confirmer les murs vus une seule fois."))
        else:
            lines.append((OK, "Plus de zone inconnue détectée : la carte semble complète. "
                              "Vérifiez les coins et derrière les meubles, puis « Terminer »."))
        lines.append(("muted", f"{n} position(s), {sum(len(p['scans']) for p in self.positions.values())} tours."))
        self.say(lines)

    # =============================================================== export
    def finish(self):
        if not self.positions:
            return self.say([(WARN, "Rien à exporter : capturez au moins une position.")], clear=False)
        out = self.folder / "rapport"
        out.mkdir(parents=True, exist_ok=True)
        pairs = [(s.filtered(), pos["pose"]) for pos in self.positions.values() for s in pos["scans"]]
        vm = build_vector_map(pairs)
        vm.save_csv(out / "segments.csv")
        self.grid.save(out / "gridmap.npz")
        self._save_map_png(out / "gridmap.png", vector=None)
        self._save_map_png(out / "vectormap.png", vector=vm)
        (out / "rapport.md").write_text(self._report_md(vm), encoding="utf-8")
        self.exported = True
        self.say([("title", "Export terminé"),
                  (OK, f"Dans {out} : gridmap.png, gridmap.npz, vectormap.png, segments.csv, rapport.md."),
                  ("info", "Les scans (CSV) et poses.json du dossier de session sont vos données pour "
                           "les étapes 2 à 5 : sauvegardez ce dossier (clé USB, cloud)."),
                  ("muted", f"Étape 2 : python -m carto view {self.folder} --poses {self.folder / 'poses.json'}")])
        if messagebox.askyesno("Export terminé", f"Cartes et rapport enregistrés dans :\n{out}\n\nOuvrir le dossier ?"):
            try:
                os.startfile(out)  # Windows
            except (AttributeError, OSError):
                pass

    def _draw_poses(self, ax):
        for i, (name, pos) in enumerate(self.positions.items(), 1):
            p = pos["pose"]
            ax.plot([p.x, p.x + 0.45 * np.cos(p.theta)], [p.y, p.y + 0.45 * np.sin(p.theta)],
                    color=C["pose"], lw=2.2, solid_capstyle="round", zorder=4)
            ax.plot(p.x, p.y, "o", ms=15, mfc=C["pose"], mec="white", mew=1.5, zorder=4)
            ax.text(p.x, p.y, str(i), color="white", fontsize=7, weight="bold", ha="center", va="center", zorder=4)
            ax.text(p.x, p.y - 0.32, name, color=C["pose"], fontsize=7, ha="center", va="top", zorder=4,
                    weight="bold")

    def _save_map_png(self, path, vector=None):
        fig = Figure(figsize=(9, 7.5), dpi=130, facecolor="white")
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        theme.style_axes(ax)
        if vector is None:
            ax.imshow(self.grid.probability(), cmap=theme.OCC_CMAP, origin="lower", vmin=0, vmax=1,
                      extent=self.grid.extent, interpolation="nearest")
            title = f"Grid map — cellules de {self.grid.res * 100:.0f} cm"
            handles = theme.legend_handles(with_live=False, with_stars=False)
        else:
            ax.set_facecolor("white")
            for pos in self.positions.values():
                pts = pos["scans"][0].filtered().world_xy(pos["pose"])
                ax.scatter(pts[:, 0], pts[:, 1], s=1.5, color="#94A3B8", alpha=0.5, lw=0)
            for sg in vector.segments:
                ax.plot([sg.p1[0], sg.p2[0]], [sg.p1[1], sg.p2[1]], "-", color=C["wall"],
                        lw=1.2 + min(sg.n_obs, 4) * 0.5, solid_capstyle="round")
            title = f"Carte vectorielle — {len(vector.segments)} segments (épaisseur = nb d'observations)"
            handles = [theme.legend_handles(False, False)[3]]
        self._draw_poses(ax)
        ax.set_aspect("equal")
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title(title, fontsize=11, color=C["text"], loc="left", weight="bold")
        ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.95, edgecolor=C["border"])
        fig.tight_layout()
        fig.savefig(path)

    def _report_md(self, vm) -> str:
        g, journal = self.grid, {e["position"]: e for e in self._journal()}
        cls = g.classify()
        res2 = g.res ** 2
        frontier_m = frontier_mask(g).sum() * g.res
        L = [f"# Capture LD06 — {self.folder.name}", "",
             f"Généré le {time.strftime('%Y-%m-%d %H:%M')} par l'assistant de capture.", "",
             "## Positions", "",
             "| position | x (m) | y (m) | θ (°) | tours | pts/tour | sans écho | écart entre tours | recouvrement | alertes |",
             "|---|---|---|---|---|---|---|---|---|---|"]
        for name, pos in self.positions.items():
            p, e = pos["pose"], journal.get(name, {})
            st = e.get("stats", {})
            ov = e.get("recouvrement")
            alerts = "; ".join(m[1] for m in e.get("messages", []) if m[0] != OK) or "—"
            invalid = f"{st['invalides']:.0%}" if "invalides" in st else "—"
            spread = f"{st['ecart_median_m'] * 1000:.0f} mm" if "ecart_median_m" in st else "—"
            overlap = "référence" if ov is None else f"{ov:.0%}"
            L.append(f"| {name} | {p.x:.2f} | {p.y:.2f} | {np.degrees(p.theta):.1f} | {len(pos['scans'])} | "
                     f"{st.get('points_par_tour', '—')} | {invalid} | {spread} | {overlap} | {alerts} |")
        L += ["", "Le repère de la carte est celui de la première position (origine et axes choisis "
                  "dans la salle). Les poses sont celles mesurées au mètre, éventuellement corrigées "
                  "avec « Recaler » ou « Aligner θ sur les murs ».", "",
              "## Grid map", "",
              f"- cellules de {g.res * 100:.0f} cm, {g.shape[1]} × {g.shape[0]} cellules",
              f"- occupé : {(cls == 1).sum() * res2:.1f} m², libre : {(cls == 0).sum() * res2:.1f} m², "
              f"inconnu : {(cls == -1).sum() * res2:.1f} m²",
              f"- frontière libre/inconnu restante : {frontier_m:.1f} m",
              "", "![grid map](gridmap.png)", "",
              "## Carte vectorielle", "",
              f"- {len(vm.segments)} segments, dont {len(vm.confirmed(2))} vus au moins 2 fois",
              f"- longueur totale de murs : {sum(s.length for s in vm.segments):.1f} m",
              "", "![carte vectorielle](vectormap.png)", "",
              "## Fichiers", "",
              "- `../posN_00K.csv` : scans bruts (angle_deg, distance_mm, intensity), sens trigo, 0° = avant du lidar",
              "- `../poses.json` : pose de chaque scan [x_m, y_m, theta_deg]",
              "- `../journal.json` : contrôle qualité de chaque capture",
              "- `gridmap.npz` (log-odds), `segments.csv` (x1, y1, x2, y2, length, n_obs)", ""]
        return "\n".join(L)

    # =========================================================== simulation
    def _place_sim(self, x, y):
        rng = np.random.default_rng()
        true = Pose(x, y, float(rng.uniform(-np.pi, np.pi)))
        self.source.true_pose = true
        measured = Pose(true.x + rng.normal(0, 0.06), true.y + rng.normal(0, 0.06),
                        true.theta + np.radians(rng.normal(0, 3)))
        self.set_pose(measured)
        self.say([("muted", f"Lidar virtuel posé en ({x:.2f}, {y:.2f}). Pose « mesurée » remplie avec "
                            "une erreur de quelques cm / degrés : alignez à la souris, « Recaler » ou "
                            "« Aligner θ ».")], clear=False)

    # ================================================================= boucle
    def _tick(self):
        self._poll_detect()
        src = self.source
        if src is not None:
            if src.error:
                self._status(f"Erreur : {src.error}", ERROR)
                self.say([(ERROR, f"Lecture impossible : {src.error}"),
                          ("info", "Port occupé par le moniteur série ? Mauvais port ? Carte débranchée ?")])
                self.source = None
                self.conn_btn.configure(text="Connecter", style="Accent.TButton")
            else:
                self._drain(src)
        self._update_progress()
        self.root.after(100, self._tick)

    def _drain(self, src):
        latest = None
        while not src.queue.empty():
            latest = src.queue.get_nowait()
            if self.capture_buf is not None:
                self.capture_buf.append(latest)
        now = time.time()
        if latest is not None:
            self._last_scan_at = now
            first = self.live is None
            self.live = scan_from_dict(latest)
            valid = (self.live.ranges > 0).sum()
            extra = f" · CRC faux : {src.crc_failures}" if isinstance(src, SerialSource) and src.mode == "raw" else ""
            self._status(f"Connecté · {src.n_scans} tours reçus · {len(self.live)} points ({valid} valides){extra}", OK)
            self._update_overlap()
            if first or now - self._last_live_check > 1.0:
                self._last_live_check = now
                self._update_live_check()
            if now - self._last_live_draw > 0.15 and self._drag is None:
                self._draw_live()
        elif isinstance(src, SerialSource):
            if src.n_scans == 0 and not self._diag_shown and now - self._connected_at > NO_DATA_DELAY_S:
                self._diag_shown = True
                self._status("Aucun tour reçu", ERROR)
                self.say([("title", "Pas de données")] + diagnose_no_data(src))
            elif src.n_scans > 0 and now - self._last_scan_at > 3.0:
                self._status(f"Flux interrompu depuis {now - self._last_scan_at:.0f} s (câble ? alimentation ?)",
                             ERROR)
        if self.capture_buf is not None:
            self.cap_btn.configure(text=f"Capture en cours…  {max(0, len(self.capture_buf) - 1)} / "
                                        f"{self.capture_needed - 1}")
            if len(self.capture_buf) >= self.capture_needed:
                self._finish_capture()

    # ================================================================ dessin
    def redraw(self):
        ax = self.ax
        ax.clear()
        theme.style_axes(ax)
        if self.grid is not None:
            ax.imshow(self.grid.probability(), cmap=theme.OCC_CMAP, origin="lower", vmin=0, vmax=1,
                      extent=self.grid.extent, interpolation="nearest", zorder=0)
        self._draw_poses(ax)
        for k, s in enumerate(self.suggestions, 1):
            ax.plot([s.x, s.target[0]], [s.y, s.target[1]], ":", color=C["star"], lw=1.4, zorder=5)
            ax.plot(s.x, s.y, "*", ms=22, color=C["star"], mec="white", mew=1.2, zorder=5)
            ax.text(s.x + 0.2, s.y + 0.2, str(k), fontsize=9, weight="bold", color="white", ha="center",
                    va="center", zorder=6, bbox=dict(boxstyle="circle,pad=0.25", fc=C["star"], ec="white", lw=1))
        self.live_art = ax.scatter([], [], s=6, color=C["live"], zorder=6, lw=0)
        self.live_arrow = None
        self.live_dot = ax.plot([], [], "o", ms=9, mfc=C["live"], mec="white", mew=1.5, zorder=7)[0]
        self.ghost = ax.plot([], [], "x", color=C["ghost"], ms=10, mew=2, zorder=6)[0]
        ax.set_aspect("equal")
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.legend(handles=theme.legend_handles(), loc="upper right", fontsize=7.5, framealpha=0.95,
                  edgecolor=C["border"], borderpad=0.8, handletextpad=0.6)
        if self.grid is not None:
            x0, x1, y0, y1 = self.grid.extent
            ax.set_xlim(x0, x1)
            ax.set_ylim(y0, y1)
        elif isinstance(self.source, SimSource):
            ax.set_xlim(-1, 9)
            ax.set_ylim(-1, 7)
        else:
            ax.set_xlim(-6, 6)
            ax.set_ylim(-6, 6)
        self._draw_live()

    def _draw_live(self):
        if not hasattr(self, "live_art"):
            return
        self._last_live_draw = time.time()
        pose = self.get_pose()
        if self.live_arrow is not None:
            self.live_arrow.remove()
            self.live_arrow = None
        if self.live is not None and pose is not None:
            pts = self.live.filtered().world_xy(pose)
            self.live_art.set_offsets(pts if len(pts) else np.empty((0, 2)))
            self.live_dot.set_data([pose.x], [pose.y])
            self.live_arrow = self.ax.annotate(
                "", xy=(pose.x + 0.5 * np.cos(pose.theta), pose.y + 0.5 * np.sin(pose.theta)),
                xytext=(pose.x, pose.y), zorder=7,
                arrowprops=dict(arrowstyle="-|>,head_width=0.35,head_length=0.6", color=C["live"], lw=2.4))
        else:
            self.live_art.set_offsets(np.empty((0, 2)))
            self.live_dot.set_data([], [])
        if isinstance(self.source, SimSource):
            self.ghost.set_data([self.source.true_pose.x], [self.source.true_pose.y])
        else:
            self.ghost.set_data([], [])
        self.canvas.draw_idle()

    def close(self):
        if self.source:
            self.source.stop()
        self.root.quit()
        self.root.destroy()


def run_assistant(folder="data/salle", n_scans=5):
    theme.enable_dpi_awareness()
    root = tk.Tk()
    CaptureAssistant(root, folder, n_scans)
    root.mainloop()
