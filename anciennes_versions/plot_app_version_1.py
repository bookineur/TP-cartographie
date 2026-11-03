"""Lidar Plot : visualiseur temps réel du LD06, dans l'esprit de Teleplot.

    python -m carto plot            (ou double-clic sur « Lidar Plot.bat »)

  * barre du haut : port série, débit (Auto), format, Connecter ;
  * au centre : la carte en direct (bleu clair) avec anneaux de distance ;
    molette = zoom, glisser = déplacer la vue, double-clic = recentrer ;
  * à droite :
      - Pause (Espace) fige l'image ; Capturer (Entrée) enregistre ce qui est
        affiché comme « Scan 1 » (vert), puis « Scan 2 » (orange), etc. ;
      - liste des scans : visibilité, suppression, position du lidar (x, y, θ)
        pour superposer des scans pris à des endroits différents, recalage auto ;
      - exports : image PNG, tableau CSV de tous les points, dossier complet ;
      - variables Teleplot (>nom:valeur) et console série.
  Chaque capture est aussitôt sauvée dans le dossier de session (format du
  projet : scanK.csv + poses.json), réutilisable par les étapes 2 à 5 du TP.

Formats acceptés sur le port :
  - Teleplot  >lidar:x:y;x:y;...|xy   (LD06::printScanTeleplot, exemple Basic)
  - CSV       LD06::printScanCSV      (sketch arduino/LD06_capture)
  - LD06 branché directement (paquets binaires 0x54, 230400 bauds)
"""
from __future__ import annotations

import collections
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
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from carto import theme
from carto.gridmap import build_grid
from carto.guide import refine_pose
from carto.scan import Pose, Scan, load_scan_file, save_poses, save_scan_csv
from carto.theme import D, FONT, SCAN_COLORS
from ld06.sources import SerialSource, SimSource, TextSerialSource, list_serial_ports, probe_port

SIM_LABEL = "Simulation (sans lidar)"
BAUDS = ["Auto", "115200", "230400", "921600", "460800", "57600"]
FORMATS = {"Texte : Teleplot / CSV": "texte", "LD06 direct (binaire)": "raw"}


def scan_from_dict(d, name="direct") -> Scan:
    return Scan(name, np.radians(d["angle_deg"]), np.asarray(d["distance_mm"], float) / 1000.0,
                np.asarray(d["intensity"], float), {"speed_dps": d.get("speed_dps", 0)})


class LidarPlot:
    def __init__(self, root: tk.Tk, folder: str | None = None):
        self.root = root
        self.scale = theme.apply_dark(root)
        self.folder = Path(folder) if folder else self._last_session()
        self.source = None
        self.live: Scan | None = None
        self.live_raw: dict | None = None
        self.frozen: tuple | None = None        # (Scan, dict) affichés pendant la pause
        self.paused = False
        self.captures: list[dict] = []
        self.selected: int | None = None
        self.arrivals = collections.deque(maxlen=12)
        self._probe = None
        self._pan = None
        self._last_draw = 0.0
        self._last_slow = 0.0
        self._fitted = False
        self._sim_index = 0
        root.title("Lidar Plot — LD06")
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.geometry(f"{min(int(1400 * self.scale), w - 40)}x{min(int(860 * self.scale), h - 80)}+10+10")
        root.minsize(int(980 * self.scale), int(620 * self.scale))
        try:
            root.state("zoomed")
        except tk.TclError:
            pass
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<space>", lambda e: self._key(e, self.toggle_pause))
        root.bind("<Return>", lambda e: self._key(e, self.capture))
        self._build_ui()
        self.refresh_ports()
        self._load_session()
        self._tick()

    def px(self, v):
        return int(v * self.scale)

    # ================================================================== UI
    def _build_ui(self):
        px = self.px
        # ------------------------------------------------------ barre du haut
        top = tk.Frame(self.root, bg=D["panel"], highlightthickness=1, highlightbackground=D["border"])
        top.pack(fill="x")
        tk.Label(top, text="◉ Lidar Plot", bg=D["panel"], fg=D["text"], font=(FONT, 13, "bold")).pack(
            side="left", padx=(px(14), px(4)), pady=px(8))
        tk.Label(top, text="LD06", bg=D["accent"], fg="white", font=(FONT, 8, "bold"), padx=px(6)).pack(
            side="left", padx=(0, px(18)))

        def lab(text):
            tk.Label(top, text=text, bg=D["panel"], fg=D["muted"], font=(FONT, 9)).pack(side="left", padx=(px(8), px(4)))

        lab("Port")
        self.port_var = tk.StringVar()
        self.port_box = ttk.Combobox(top, textvariable=self.port_var, state="readonly", width=28)
        self.port_box.pack(side="left")
        ttk.Button(top, text="↻", style="Small.TButton", command=self.refresh_ports).pack(side="left", padx=px(3))
        lab("Débit")
        self.baud_var = tk.StringVar(value="Auto")
        ttk.Combobox(top, textvariable=self.baud_var, values=BAUDS, state="readonly", width=8).pack(side="left")
        lab("Format")
        self.fmt_var = tk.StringVar(value=list(FORMATS)[0])
        ttk.Combobox(top, textvariable=self.fmt_var, values=list(FORMATS), state="readonly", width=22).pack(side="left")
        self.conn_btn = ttk.Button(top, text="Connecter", style="Ok.TButton", command=self.toggle_connection)
        self.conn_btn.pack(side="left", padx=px(12))
        self.dot = tk.Label(top, text="●", bg=D["panel"], fg=D["border"], font=(FONT, 11))
        self.dot.pack(side="left")
        self.status = tk.Label(top, text="Déconnecté", bg=D["panel"], fg=D["muted"], font=(FONT, 9))
        self.status.pack(side="left", padx=px(4))
        self.sim_btn = ttk.Button(top, text="Déplacer le lidar virtuel", command=self.move_sim)

        # ------------------------------------------------------ barre du bas
        bottom = tk.Frame(self.root, bg=D["panel"], highlightthickness=1, highlightbackground=D["border"])
        bottom.pack(side="bottom", fill="x")
        self.cursor_lbl = tk.Label(bottom, text="", bg=D["panel"], fg=D["muted"], font=("Consolas", 9))
        self.cursor_lbl.pack(side="left", padx=px(12), pady=px(4))
        self.msg_lbl = tk.Label(bottom, text="", bg=D["panel"], fg=D["muted"], font=(FONT, 9))
        self.msg_lbl.pack(side="left", padx=px(12))
        folder_lbl = tk.Label(bottom, text="", bg=D["panel"], fg=D["accent"], font=(FONT, 9, "underline"),
                              cursor="hand2")
        folder_lbl.pack(side="right", padx=px(12))
        folder_lbl.bind("<Button-1>", lambda e: self.open_folder())
        self.folder_lbl = folder_lbl
        tk.Label(bottom, text="Dossier :", bg=D["panel"], fg=D["muted"], font=(FONT, 9)).pack(side="right")

        body = ttk.Frame(self.root, style="Bg.TFrame")
        body.pack(fill="both", expand=True)

        # ------------------------------------------------------ panneau droit
        side_outer = tk.Frame(body, bg=D["panel"], width=px(350), highlightthickness=1,
                              highlightbackground=D["border"])
        side_outer.pack(side="right", fill="y")
        side_outer.pack_propagate(False)
        side = ttk.Frame(side_outer, style="Panel.TFrame")
        side.pack(fill="both", expand=True, padx=px(12), pady=px(10))

        def section(title):
            tk.Label(side, text=title.upper(), bg=D["panel"], fg=D["muted"], font=(FONT, 8, "bold")).pack(
                anchor="w", pady=(px(10), px(4)))

        section("Direct")
        row = ttk.Frame(side, style="Panel.TFrame")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)
        self.pause_btn = ttk.Button(row, text="⏸  Pause", command=self.toggle_pause)
        self.pause_btn.grid(row=0, column=0, sticky="we", padx=(0, px(3)))
        self.cap_btn = ttk.Button(row, text="●  Capturer", style="Accent.TButton", command=self.capture)
        self.cap_btn.grid(row=0, column=1, sticky="we", padx=(px(3), 0))
        tk.Label(side, text="Espace = pause · Entrée = capturer ce qui est affiché", bg=D["panel"],
                 fg=D["muted"], font=(FONT, 8)).pack(anchor="w", pady=(px(3), 0))
        self.stats = {}
        grid = ttk.Frame(side, style="Panel.TFrame")
        grid.pack(fill="x", pady=(px(8), 0))
        for i, (k, label) in enumerate((("pts", "Points"), ("valid", "Valides"), ("hz", "Fréquence"),
                                        ("dmin", "Distance min"), ("dmax", "Distance max"), ("fmt", "Format"))):
            cell = tk.Frame(grid, bg=D["panel2"], padx=px(8), pady=px(4))
            cell.grid(row=i // 3, column=i % 3, sticky="we", padx=px(2), pady=px(2))
            grid.columnconfigure(i % 3, weight=1)
            tk.Label(cell, text=label, bg=D["panel2"], fg=D["muted"], font=(FONT, 7)).pack(anchor="w")
            v = tk.Label(cell, text="—", bg=D["panel2"], fg=D["text"], font=(FONT, 10, "bold"))
            v.pack(anchor="w")
            self.stats[k] = v
        opts = ttk.Frame(side, style="Panel.TFrame")
        opts.pack(fill="x", pady=(px(6), 0))
        self.show_live = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Afficher le direct", variable=self.show_live,
                        command=self._draw_live).pack(side="left")
        self.mirror = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Corriger miroir Teleplot", variable=self.mirror).pack(side="right")
        self.vars_lbl = tk.Label(side, text="", bg=D["panel"], fg=D["muted"], font=("Consolas", 8),
                                 justify="left", anchor="w", wraplength=px(320))
        self.vars_lbl.pack(fill="x")

        sess = ttk.Frame(side, style="Panel.TFrame")
        sess.pack(fill="x", pady=(px(12), px(4)))
        tk.Label(sess, text="SESSION", bg=D["panel"], fg=D["muted"], font=(FONT, 8, "bold")).pack(side="left")
        ttk.Button(sess, text="📂 Ouvrir…", style="Small.TButton", command=self.open_session).pack(side="right")
        ttk.Button(sess, text="＋ Nouvelle session", style="Small.TButton", command=self.new_session).pack(
            side="right", padx=px(4))
        self.session_lbl = tk.Label(side, text="", bg=D["panel"], fg=D["text"], font=(FONT, 10, "bold"), anchor="w")
        self.session_lbl.pack(fill="x")

        section("Scans capturés")
        # Disposition : « Exporter » est fixé en BAS du panneau (packé avant la liste),
        # l'éditeur de position juste au-dessus quand un scan est sélectionné, et la
        # liste des scans prend la place restante avec une barre de défilement.
        # Ainsi les boutons d'export restent visibles quel que soit le nombre de scans.
        exf = ttk.Frame(side, style="Panel.TFrame")
        exf.pack(side="bottom", fill="x", pady=(px(6), 0))
        tk.Label(exf, text="EXPORTER", bg=D["panel"], fg=D["muted"], font=(FONT, 8, "bold")).pack(
            anchor="w", pady=(px(4), px(4)))
        ex = ttk.Frame(exf, style="Panel.TFrame")
        ex.pack(fill="x")

        self.list_box = tk.Frame(side, bg=D["panel"])
        self.list_canvas = tk.Canvas(self.list_box, bg=D["panel"], highlightthickness=0, bd=0)
        list_sb = ttk.Scrollbar(self.list_box, orient="vertical", command=self.list_canvas.yview)
        self.cap_list = tk.Frame(self.list_canvas, bg=D["panel"])
        win = self.list_canvas.create_window((0, 0), window=self.cap_list, anchor="nw")
        self.cap_list.bind("<Configure>", lambda e: self.list_canvas.configure(
            scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.bind("<Configure>", lambda e: self.list_canvas.itemconfigure(win, width=e.width))
        self.list_canvas.configure(yscrollcommand=list_sb.set)
        list_sb.pack(side="right", fill="y")
        self.list_canvas.pack(side="left", fill="both", expand=True)
        wheel = lambda e: self.list_canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")
        self.list_box.bind("<Enter>", lambda e: self.list_canvas.bind_all("<MouseWheel>", wheel))
        self.list_box.bind("<Leave>", lambda e: self.list_canvas.unbind_all("<MouseWheel>"))
        self.list_box.pack(side="top", fill="both", expand=True)
        self.empty_lbl = tk.Label(self.cap_list, text="Aucun scan. Quand l'image vous plaît : Pause puis Capturer.",
                                  bg=D["panel"], fg=D["muted"], font=(FONT, 9), wraplength=px(320), justify="left")
        self.pose_frame = ttk.Frame(side, style="Panel.TFrame")
        self._build_pose_editor()

        for col in range(3):
            ex.columnconfigure(col, weight=1)
        ttk.Button(ex, text="🖼 Image", command=self.export_png).grid(row=0, column=0, sticky="we", padx=(0, px(2)))
        ttk.Button(ex, text="▦ Excel", command=self.export_xlsx).grid(row=0, column=1, sticky="we", padx=px(2))
        ttk.Button(ex, text="CSV", command=self.export_csv).grid(row=0, column=2, sticky="we", padx=(px(2), 0))
        ttk.Button(ex, text="⬇  Tout exporter (image + Excel + résumé)", style="Ok.TButton",
                   command=self.export_all).grid(row=1, column=0, columnspan=3, sticky="we", pady=(px(5), 0))

        # ------------------------------------------------------ carte + console
        mframe = tk.Frame(body, bg=D["plot_bg"])
        mframe.pack(side="left", fill="both", expand=True)
        self.console_frame = tk.Frame(mframe, bg=D["bg"], highlightthickness=1, highlightbackground=D["border"])
        self.console = tk.Text(self.console_frame, bg=D["bg"], fg="#7EE787", font=("Consolas", 9), relief="flat",
                               wrap="none", height=9, highlightthickness=0, padx=px(8), pady=px(4))
        self.console.pack(fill="both", expand=True)
        self.console.configure(state="disabled")
        cbtn = tk.Label(bottom, text="▤  Console série", bg=D["panel2"], fg=D["text"], font=(FONT, 9),
                        padx=px(8), pady=px(1), cursor="hand2")
        cbtn.pack(side="left", padx=(px(4), 0), before=self.cursor_lbl)
        cbtn.bind("<Button-1>", lambda e: self.toggle_console())
        self.console_btn = cbtn
        self.fig = Figure(dpi=100 * self.scale, facecolor=D["plot_bg"])
        self.ax = self.fig.add_axes([0.04, 0.045, 0.95, 0.94])
        self.canvas = FigureCanvasTkAgg(self.fig, master=mframe)
        self.canvas.get_tk_widget().configure(bg=D["plot_bg"], highlightthickness=0)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        for ev, cb in (("scroll_event", self._on_scroll), ("button_press_event", self._on_press),
                       ("motion_notify_event", self._on_motion), ("button_release_event", self._on_release),
                       ("resize_event", lambda e: self._set_view(*self._view_center(), self._view_half()))):
            self.canvas.mpl_connect(ev, cb)
        self._setup_axes()

    def toggle_console(self):
        if self.console_frame.winfo_ismapped():
            self.console_frame.pack_forget()
            self.console_btn.configure(bg=D["panel2"])
        else:
            self.console_frame.pack(side="bottom", fill="x", before=self.canvas.get_tk_widget())
            self.console_btn.configure(bg=D["accent"])

    def _build_pose_editor(self):
        px = self.px
        f = self.pose_frame
        self.pose_title = tk.Label(f, text="", bg=D["panel"], fg=D["text"], font=(FONT, 9, "bold"))
        self.pose_title.grid(row=0, column=0, columnspan=7, sticky="w")
        self.pose_vars = {}
        for i, (k, lab, step) in enumerate((("x", "x (m)", 0.05), ("y", "y (m)", 0.05), ("t", "θ (°)", 1.0))):
            tk.Label(f, text=lab, bg=D["panel"], fg=D["muted"], font=(FONT, 8)).grid(row=1, column=i * 2, columnspan=2,
                                                                                    sticky="w")
            v = tk.StringVar(value="0")
            e = ttk.Entry(f, textvariable=v, width=7)
            e.grid(row=2, column=i * 2, sticky="we", padx=(0, px(1)))
            e.bind("<Return>", lambda ev: self.apply_pose())
            e.bind("<FocusOut>", lambda ev: self.apply_pose())
            self.pose_vars[k] = v
            sp = ttk.Frame(f, style="Panel.TFrame")
            sp.grid(row=2, column=i * 2 + 1, padx=(0, px(6)))
            ttk.Button(sp, text="+", style="Small.TButton", width=2,
                       command=lambda k=k, s=step: self.nudge(k, s)).pack()
            ttk.Button(sp, text="−", style="Small.TButton", width=2,
                       command=lambda k=k, s=step: self.nudge(k, -s)).pack()
        b = ttk.Frame(f, style="Panel.TFrame")
        b.grid(row=3, column=0, columnspan=7, sticky="we", pady=(px(4), 0))
        ttk.Button(b, text="⤧ Recaler sur les autres scans", command=self.refine_selected).pack(side="left")
        ttk.Button(b, text="✕ Supprimer", command=self.delete_selected).pack(side="right")
        self.pose_frame.pack_forget()

    # ------------------------------------------------------------ messages
    def _status(self, text, color=None):
        self.dot.configure(fg=color or D["border"])
        self.status.configure(text=text, fg=D["text"] if color else D["muted"])

    def _msg(self, text, color=None):
        self.msg_lbl.configure(text=text, fg=color or D["muted"])

    def _key(self, e, action):
        if isinstance(e.widget, (tk.Entry, ttk.Entry, ttk.Combobox, tk.Text)):
            return
        action()

    # ============================================================ connexion
    def refresh_ports(self):
        ports = list_serial_ports()
        values = [f"{dev} — {desc}" for dev, desc in ports] + [SIM_LABEL]
        self.port_box["values"] = values
        if self.port_var.get() not in values:
            self.port_var.set(values[0])
        if not ports and not self.source:
            self._status("Aucun port série détecté : robot branché ? câble USB data ? pilote ?", D["warn"])

    def toggle_connection(self):
        if self._probe:
            return
        if self.source:
            self.source.stop()
            self.source = None
            self.conn_btn.configure(text="Connecter", style="Ok.TButton")
            self.sim_btn.pack_forget()
            self._status("Déconnecté")
            return
        choice = self.port_var.get()
        if choice == SIM_LABEL:
            from carto.simulate import TRUE_POSES
            self.source = SimSource(list(TRUE_POSES.values())[0]).start()
            self.sim_btn.pack(side="left", padx=self.px(8))
            return self._connected("Simulation")
        port = choice.split(" — ")[0]
        fmt = FORMATS[self.fmt_var.get()]
        baud = self.baud_var.get()
        if baud == "Auto":
            self._start_probe(port)
            return
        self._open(port, fmt, int(baud))

    def _open(self, port, fmt, baud):
        if fmt == "raw":
            self.source = SerialSource(port, "raw", baud).start()
        else:
            self.source = TextSerialSource(port, baud, self.mirror.get()).start()
        self._connected(f"{port} · {baud} bauds")

    def _connected(self, what):
        self.arrivals.clear()
        self._connected_at = time.time()
        self.conn_btn.configure(text="Déconnecter", style="Danger.TButton")
        self._status(f"{what} · en attente de données…", D["warn"])

    def _port_error(self, port, err: str):
        """Message adapté à la cause : port occupé, débranché, ou autre."""
        if "PermissionError" in err or "refus" in err or "denied" in err.lower():
            self._status(f"{port} est déjà utilisé par un autre programme", D["error"])
            messagebox.showerror(
                "Port occupé", f"{port} est déjà ouvert par un autre programme.\n"
                               "Un port série ne peut être utilisé que par un seul programme à la fois.\n\n"
                               "Fermez, puis cliquez à nouveau sur Connecter :\n"
                               "  • le Moniteur série / Traceur série de l'IDE Arduino\n"
                               "  • l'assistant de capture (python -m carto assistant)\n"
                               "  • une autre fenêtre Lidar Plot\n"
                               "  • Teleplot (site web ou extension VS Code), PuTTY…\n\n"
                               "Pendant un téléversement, l'IDE Arduino occupe aussi le port.")
        elif "FileNotFoundError" in err or "introuvable" in err:
            self._status(f"{port} introuvable : robot débranché ?", D["error"])
            messagebox.showerror("Port introuvable", f"{port} n'existe plus : robot débranché ou câble USB "
                                                     "déplacé.\nRebranchez, cliquez sur ↻ puis Connecter.")
        else:
            self._status(f"Erreur : {err}", D["error"])
            messagebox.showerror("Connexion perdue", f"{err}\n\nRobot débranché ? Câble USB ?")

    def _start_probe(self, port):
        st = {"log": "", "res": None, "done": False, "err": None}

        def work():
            try:
                st["res"] = probe_port(port, log=lambda m: st.__setitem__("log", m))
            except Exception as e:
                st["err"] = f"{type(e).__name__}: {e}"
            st["done"] = True

        threading.Thread(target=work, daemon=True).start()
        self._probe = (st, port)
        self.conn_btn.configure(state="disabled")
        self._status("Recherche du débit et du format…", D["accent"])

    def _poll_probe(self):
        if not self._probe:
            return
        st, port = self._probe
        if not st["done"]:
            self._status(f"Recherche : {st['log']}", D["accent"])
            return
        self._probe = None
        self.conn_btn.configure(state="normal")
        if st["err"]:
            return self._port_error(port, st["err"])
        if st["res"] is None:
            self._status(f"Rien de reconnu sur {port}", D["error"])
            messagebox.showwarning("Aucune donnée reconnue",
                                   f"Aucune donnée lidar reconnue sur {port} (115200, 921600, 230400 bauds).\n\n"
                                   "• Le lidar tourne-t-il ?\n• Le programme du robot envoie-t-il bien les scans "
                                   "(printScanTeleplot ou printScanCSV) ?\n• Le moniteur série de l'IDE Arduino "
                                   "est-il fermé ?\n• Est-ce le bon port ?")
            return
        fmt, baud = st["res"]
        self.baud_var.set(str(baud))
        self.fmt_var.set([k for k, v in FORMATS.items() if v == fmt][0])
        self._open(port, fmt, baud)

    def move_sim(self):
        from carto.simulate import TRUE_POSES
        if isinstance(self.source, SimSource):
            self._sim_index = (self._sim_index + 1) % len(TRUE_POSES)
            name, pose = list(TRUE_POSES.items())[self._sim_index]
            self.source.true_pose = pose
            self._msg(f"Lidar virtuel déplacé ({name}).", D["accent"])

    # ================================================================ direct
    def toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.frozen = (self.live, self.live_raw) if self.live is not None else None
            self.pause_btn.configure(text="▶  Reprendre", style="Accent.TButton")
            self.cap_btn.configure(style="Ok.TButton")
            self._msg("Pause : l'image est figée. « Capturer » enregistre exactement ce qui est affiché.", D["warn"])
        else:
            self.frozen = None
            self.pause_btn.configure(text="⏸  Pause", style="TButton")
            self.cap_btn.configure(style="Accent.TButton")
            self._msg("")
        self._draw_live()

    def _shown(self):
        return self.frozen if self.paused and self.frozen else (self.live, self.live_raw)

    def _tick(self):
        self._poll_probe()
        src = self.source
        now = time.time()
        if src is not None:
            if src.error:
                self.source = None
                self.conn_btn.configure(text="Connecter", style="Ok.TButton")
                self._port_error(getattr(src, "port", "?"), src.error)
            else:
                latest = None
                while not src.queue.empty():
                    latest = src.queue.get_nowait()
                    self.arrivals.append(now)
                if latest is not None:
                    self.live_raw = latest
                    self.live = scan_from_dict(latest)
                    fmt = latest.get("source", "binaire LD06" if isinstance(src, SerialSource) else "simulation")
                    fmt = "Teleplot" if fmt.startswith("teleplot") else fmt.upper() if fmt == "csv" else fmt
                    self._status(f"Connecté · {src.n_scans} tours reçus · {fmt}", D["ok"])
                    if not self.paused:
                        self._update_stats(self.live, fmt)
                        if now - self._last_draw > 0.08:
                            self._draw_live()
                elif src.n_scans == 0 and now - getattr(self, "_connected_at", now) > 6:
                    self._status("Connecté mais aucune donnée lidar reconnue (voir la console)", D["error"])
                elif src.n_scans and self.arrivals and now - self.arrivals[-1] > 3:
                    self._status(f"Plus de données depuis {now - self.arrivals[-1]:.0f} s", D["error"])
            if now - self._last_slow > 0.5:
                self._last_slow = now
                self._update_console_vars(src)
        self.root.after(50, self._tick)

    def _update_stats(self, scan: Scan, fmt: str):
        r = scan.ranges
        v = r[r > 0.05]
        hz = (len(self.arrivals) - 1) / (self.arrivals[-1] - self.arrivals[0]) \
            if len(self.arrivals) > 2 and self.arrivals[-1] > self.arrivals[0] else 0
        self.stats["pts"].configure(text=f"{len(r)}")
        self.stats["valid"].configure(text=f"{len(v) / max(len(r), 1):.0%}")
        self.stats["hz"].configure(text=f"{hz:.1f} /s" if hz else "—")
        self.stats["dmin"].configure(text=f"{v.min():.2f} m" if len(v) else "—")
        self.stats["dmax"].configure(text=f"{v.max():.2f} m" if len(v) else "—")
        self.stats["fmt"].configure(text=fmt)

    def _update_console_vars(self, src):
        if isinstance(src, TextSerialSource):
            lines = list(src.console)[-40:]
            text = "\n".join(lines)
            if src.variables:
                self.vars_lbl.configure(text="Variables Teleplot : " + "   ".join(
                    f"{k} = {v:g}" for k, v in list(src.variables.items())[:8]), fg=D["text"])
        elif isinstance(src, SerialSource):
            text = (f"[LD06 binaire] {src.bytes_received} octets · {src.packets_ok} paquets valides · "
                    f"{src.crc_failures} CRC faux")
        else:
            text = "[simulation] scans générés en interne"
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.insert("end", text)
        self.console.see("end")
        self.console.configure(state="disabled")

    # ============================================================== captures
    def capture(self):
        scan, raw = self._shown()
        if scan is None:
            return self._msg("Rien à capturer : connectez le robot et attendez le scan en direct.", D["error"])
        k = 1 + max([c["k"] for c in self.captures], default=0)
        name = f"scan{k}"
        pose = Pose(0, 0, 0)
        if self.captures:  # par défaut : même pose que le scan précédent (on corrige ensuite)
            pose = Pose(self.captures[-1]["pose"].x, self.captures[-1]["pose"].y, self.captures[-1]["pose"].theta)
        cap = {"k": k, "name": name, "color": SCAN_COLORS[(k - 1) % len(SCAN_COLORS)],
               "scan": Scan(name, scan.angles, scan.ranges, scan.intensities, dict(scan.meta)),
               "pose": pose, "visible": tk.BooleanVar(value=True), "time": time.strftime("%H:%M:%S"),
               "source": (raw or {}).get("source", "")}
        self.captures.append(cap)
        self._save_capture(cap)
        if self.paused:
            self.toggle_pause()  # on repart en direct pour le scan suivant
        self.selected = len(self.captures) - 1
        self._refresh_list()
        self._draw_captures()
        n = len(cap["scan"])
        self._msg(f"Scan {k} capturé ({n} points) → {self.folder / (name + '.csv')}", cap["color"])

    def _save_capture(self, cap):
        self.folder.mkdir(parents=True, exist_ok=True)
        s = cap["scan"]
        save_scan_csv(self.folder / f"{cap['name']}.csv", np.degrees(s.angles), s.ranges * 1000, s.intensities,
                      meta={"heure": cap["time"], "source": cap["source"] or "?"})
        self._save_poses()

    def _save_poses(self):
        if self.folder.exists():
            save_poses(self.folder / "poses.json", {c["name"]: c["pose"] for c in self.captures})
        self.folder_lbl.configure(text=str(self.folder.resolve()))

    # ---------------------------------------------------------------- sessions
    SESSIONS_ROOT = Path("data")
    LAST_FILE = SESSIONS_ROOT / ".derniere_session"

    def _last_session(self) -> Path:
        """Au lancement : la dernière session utilisée, sinon celle du jour."""
        try:
            p = Path(self.LAST_FILE.read_text(encoding="utf-8").strip())
            if p.exists():
                return p
        except OSError:
            pass
        return self.SESSIONS_ROOT / f"captures_{time.strftime('%Y-%m-%d')}"

    def _remember_session(self):
        try:
            self.SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
            self.LAST_FILE.write_text(str(self.folder), encoding="utf-8")
        except OSError:
            pass

    def new_session(self):
        from tkinter import simpledialog
        default = f"salle_{time.strftime('%Y-%m-%d_%Hh%M')}"
        name = simpledialog.askstring("Nouvelle session",
                                      "Nom de la nouvelle session (ex. : salle B204) :\n\n"
                                      f"Les scans actuels restent enregistrés dans\n{self.folder.resolve()}",
                                      initialvalue=default, parent=self.root)
        if not name:
            return
        slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in name.strip()).strip("_") or default
        folder = self.SESSIONS_ROOT / slug
        k = 2
        while folder.exists() and any(folder.glob("scan*.csv")):
            folder = self.SESSIONS_ROOT / f"{slug}_{k}"
            k += 1
        folder.mkdir(parents=True, exist_ok=True)
        self._switch_session(folder)
        self._msg(f"Nouvelle session « {folder.name} » : la carte repart de zéro.", D["ok"])

    def open_session(self):
        self.SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)
        d = filedialog.askdirectory(initialdir=self.SESSIONS_ROOT.resolve(), title="Ouvrir une session (dossier)",
                                    mustexist=True)
        if d:
            self._switch_session(Path(d))

    def _switch_session(self, folder: Path):
        if self.paused:
            self.toggle_pause()
        self.folder = folder
        self._load_session()
        if not self.captures:
            self._msg(f"Session « {folder.name} » ouverte (aucun scan pour l'instant).", D["accent"])

    def _load_session(self):
        self.captures, self.selected = [], None
        self.folder_lbl.configure(text=str(self.folder.resolve()))
        self.session_lbl.configure(text=f"📁 {self.folder.name}")
        self._remember_session()
        if not self.folder.exists():
            self._refresh_list()
            return self._draw_captures()
        poses = {}
        if (self.folder / "poses.json").exists():
            poses = {k: Pose.from_list_deg(v) for k, v in
                     json.loads((self.folder / "poses.json").read_text(encoding="utf-8")).items()}
        files = sorted(self.folder.glob("scan*.csv"), key=lambda f: int("".join(c for c in f.stem if c.isdigit()) or 0))
        for f in files:
            digits = "".join(c for c in f.stem if c.isdigit())
            if not digits:
                continue
            scans = load_scan_file(f)
            if not scans:
                continue
            k = int(digits)
            self.captures.append({"k": k, "name": f.stem, "color": SCAN_COLORS[(k - 1) % len(SCAN_COLORS)],
                                  "scan": scans[0], "pose": poses.get(f.stem, Pose()),
                                  "visible": tk.BooleanVar(value=True), "time": scans[0].meta.get("heure", ""),
                                  "source": scans[0].meta.get("source", "")})
        if self.captures:
            self._msg(f"{len(self.captures)} scan(s) repris depuis la session « {self.folder.name} ».", D["accent"])
        self._refresh_list()
        self._draw_captures(fit=bool(self.captures))

    def _refresh_list(self):
        px = self.px
        n = len(self.captures)
        self.session_lbl.configure(text=f"📁 {self.folder.name}   ·   {n} scan{'s' if n > 1 else ''}")
        for w in self.cap_list.winfo_children():
            if w is not self.empty_lbl:
                w.destroy()
        if not self.captures:
            self.empty_lbl.pack(anchor="w")
            self.pose_frame.pack_forget()
            return
        self.empty_lbl.pack_forget()
        for i, c in enumerate(self.captures):
            sel = i == self.selected
            bg = D["panel2"] if sel else D["panel"]
            row = tk.Frame(self.cap_list, bg=bg, highlightthickness=1,
                           highlightbackground=c["color"] if sel else D["panel"])
            row.pack(fill="x", pady=px(1))
            sw = tk.Label(row, text="", bg=c["color"], width=2)
            sw.pack(side="left", fill="y", padx=(0, px(6)))
            cb = tk.Checkbutton(row, variable=c["visible"], bg=bg, activebackground=bg, selectcolor=D["panel2"],
                                fg=D["text"], command=self._draw_captures, highlightthickness=0, bd=0)
            cb.pack(side="left")
            p = c["pose"]
            txt = tk.Label(row, text=f"Scan {c['k']}", bg=bg, fg=D["text"], font=(FONT, 10, "bold"))
            txt.pack(side="left")
            info = tk.Label(row, text=f"{len(c['scan'])} pts · {c['time']}"
                                      + (f" · ({p.x:.1f}, {p.y:.1f}, {np.degrees(p.theta):.0f}°)"
                                         if (p.x, p.y, p.theta) != (0, 0, 0) else ""),
                            bg=bg, fg=D["muted"], font=(FONT, 8))
            info.pack(side="left", padx=px(6))
            for w in (row, txt, info, sw):
                w.bind("<Button-1>", lambda e, i=i: self.select(i))
        if self.selected is not None and self.selected < len(self.captures):
            c = self.captures[self.selected]
            self.pose_title.configure(text=f"Position du lidar — Scan {c['k']}", fg=c["color"])
            for k, v in (("x", c["pose"].x), ("y", c["pose"].y), ("t", np.degrees(c["pose"].theta))):
                self.pose_vars[k].set(f"{v:.2f}" if k != "t" else f"{v:.1f}")
            # en bas, juste au-dessus d'« Exporter » (packé avant la liste pour garder sa place)
            self.pose_frame.pack(side="bottom", fill="x", pady=(px(6), 0), before=self.list_box)
            if self.selected == len(self.captures) - 1:  # nouvelle capture : on montre la fin de la liste
                self.root.after(80, lambda: self.list_canvas.yview_moveto(1.0))
        else:
            self.pose_frame.pack_forget()

    def select(self, i):
        self.selected = None if self.selected == i else i
        self._refresh_list()
        self._draw_captures()

    def apply_pose(self):
        if self.selected is None:
            return
        try:
            x, y, t = (float(self.pose_vars[k].get().replace(",", ".")) for k in ("x", "y", "t"))
        except ValueError:
            return self._msg("x, y, θ doivent être des nombres.", D["error"])
        c = self.captures[self.selected]
        new = Pose(x, y, np.radians(t))
        if (new.x, new.y, round(new.theta, 6)) == (c["pose"].x, c["pose"].y, round(c["pose"].theta, 6)):
            return
        c["pose"] = new
        self._save_poses()
        self._refresh_list()
        self._draw_captures()

    def nudge(self, k, step):
        try:
            v = float(self.pose_vars[k].get().replace(",", "."))
        except ValueError:
            v = 0.0
        self.pose_vars[k].set(f"{v + step:.2f}" if k != "t" else f"{v + step:.1f}")
        self.apply_pose()

    def refine_selected(self):
        if self.selected is None:
            return
        c = self.captures[self.selected]
        others = [(o["scan"].filtered(), o["pose"]) for o in self.captures if o is not c and o["visible"].get()]
        if not others:
            return self._msg("Il faut au moins un autre scan visible pour recaler celui-ci.", D["warn"])
        grid = build_grid(others)
        new, before, after = refine_pose(grid, c["scan"], c["pose"])
        if after is None or after <= before + 0.02:
            return self._msg(f"Recalage : pas d'amélioration (recouvrement {before:.0%}). Rapprochez d'abord "
                             "la pose à la main (à 40 cm / 8° près).", D["warn"])
        c["pose"] = new
        self._save_poses()
        self._refresh_list()
        self._draw_captures()
        self._msg(f"Scan {c['k']} recalé : recouvrement {before:.0%} → {after:.0%}.", D["ok"])

    def delete_selected(self):
        if self.selected is None:
            return
        c = self.captures[self.selected]
        if not messagebox.askyesno("Supprimer", f"Supprimer le Scan {c['k']} ?\n"
                                                "Son fichier est déplacé dans le sous-dossier _supprimes/."):
            return
        f = self.folder / f"{c['name']}.csv"
        if f.exists():
            (self.folder / "_supprimes").mkdir(exist_ok=True)
            shutil.move(str(f), str(self.folder / "_supprimes" / f"{c['name']}_{time.strftime('%H%M%S')}.csv"))
        self.captures.pop(self.selected)
        self.selected = None
        self._save_poses()
        self._refresh_list()
        self._draw_captures()

    # ================================================================ carte
    def _setup_axes(self):
        ax = self.ax
        ax.clear()
        ax.set_facecolor(D["plot_bg"])
        for sp in ax.spines.values():
            sp.set_color(D["border"])
        ax.tick_params(colors=D["muted"], labelsize=8, length=3)
        ax.grid(True, color=D["grid"], lw=0.8)
        ax.set_axisbelow(True)
        ax.set_aspect("auto")  # l'échelle 1:1 est gérée par _set_view (la carte remplit toute la zone)
        ax.axhline(0, color=D["ring"], lw=0.8, zorder=1)
        ax.axvline(0, color=D["ring"], lw=0.8, zorder=1)
        th = np.linspace(0, 2 * np.pi, 200)
        for r in range(1, 13):
            ax.plot(r * np.cos(th), r * np.sin(th), color=D["ring"], lw=0.7, ls=(0, (3, 4)), zorder=1)
            ax.text(r * 0.707, r * 0.707, f"{r} m", color=D["muted"], fontsize=7, zorder=1, alpha=0.8)
        ax.plot(0, 0, marker=">", ms=11, color=D["live"], mec="white", mew=1, zorder=8)
        self.live_art = ax.scatter([], [], s=4, color=D["live"], lw=0, zorder=6)
        self.cap_arts = []
        self.legend = None
        self._set_view(0.0, 0.0, 6.0)

    def _set_view(self, cx, cy, half):
        """Centre la vue en (cx, cy) ; `half` = demi-largeur du plus petit côté (m).
        Les limites suivent le rapport largeur/hauteur de la zone : 1 m = 1 m en x et y."""
        bb = self.ax.get_window_extent()
        r = bb.width / bb.height if bb.height > 0 else 1.0
        hx, hy = (half * r, half) if r >= 1 else (half, half / r)
        self.ax.set_xlim(cx - hx, cx + hx)
        self.ax.set_ylim(cy - hy, cy + hy)
        self.canvas.draw_idle()

    def _view_center(self):
        (x0, x1), (y0, y1) = self.ax.get_xlim(), self.ax.get_ylim()
        return (x0 + x1) / 2, (y0 + y1) / 2

    def _view_half(self):
        (x0, x1), (y0, y1) = self.ax.get_xlim(), self.ax.get_ylim()
        return min(x1 - x0, y1 - y0) / 2

    def _draw_captures(self, fit=False):
        for a in self.cap_arts:
            a.remove()
        self.cap_arts = []
        handles = []
        for i, c in enumerate(self.captures):
            if not c["visible"].get():
                continue
            pts = c["scan"].filtered().world_xy(c["pose"])
            sel = i == self.selected
            self.cap_arts.append(self.ax.scatter(pts[:, 0], pts[:, 1], s=7 if sel else 4, color=c["color"], lw=0,
                                                 zorder=5 if sel else 4, alpha=1 if sel else 0.85))
            p = c["pose"]
            self.cap_arts += self.ax.plot([p.x, p.x + 0.35 * np.cos(p.theta)], [p.y, p.y + 0.35 * np.sin(p.theta)],
                                          color=c["color"], lw=2, zorder=7)
            self.cap_arts += self.ax.plot(p.x, p.y, "o", ms=6, color=c["color"], mec="white", mew=1, zorder=7)
            handles.append(Line2D([], [], marker="o", ls="", ms=7, color=c["color"],
                                  label=f"Scan {c['k']} · {len(c['scan'])} pts"))
        if self.legend:
            self.legend.remove()
            self.legend = None
        handles.insert(0, Line2D([], [], marker="o", ls="", ms=7, color=D["live"],
                                 label="Direct" + (" (pause)" if self.paused else "")))
        self.legend = self.ax.legend(handles=handles, loc="upper left", fontsize=8, facecolor=D["panel"],
                                     edgecolor=D["border"], labelcolor=D["text"], framealpha=0.9)
        if fit:
            self.fit_view()
        self.canvas.draw_idle()

    def _draw_live(self):
        self._last_draw = time.time()
        scan, _ = self._shown()
        if scan is not None and self.show_live.get():
            pts = scan.filtered().local_xy()
            self.live_art.set_offsets(pts if len(pts) else np.empty((0, 2)))
            self.live_art.set_color(D["warn"] if self.paused else D["live"])
            if not self._fitted and len(pts):
                self._fitted = True
                self.fit_view()
        else:
            self.live_art.set_offsets(np.empty((0, 2)))
        self.canvas.draw_idle()

    def fit_view(self):
        pts = [c["scan"].filtered().world_xy(c["pose"]) for c in self.captures if c["visible"].get()]
        scan, _ = self._shown()
        if scan is not None and self.show_live.get():
            pts.append(scan.filtered().local_xy())
        pts = [p for p in pts if len(p)]
        if not pts:
            return
        allp = np.vstack(pts + [np.zeros((1, 2))])
        lo, hi = np.percentile(allp, 1, axis=0), np.percentile(allp, 99, axis=0)
        c, half = (lo + hi) / 2, max((hi - lo).max() / 2 * 1.1, 1.0)
        self._set_view(c[0], c[1], half)

    # ----------------------------------------------------- zoom / déplacement
    def _on_scroll(self, e):
        if e.inaxes is not self.ax:
            return
        f = 1 / 1.2 if e.button == "up" else 1.2
        x0, x1 = self.ax.get_xlim()
        y0, y1 = self.ax.get_ylim()
        self.ax.set_xlim(e.xdata + (x0 - e.xdata) * f, e.xdata + (x1 - e.xdata) * f)
        self.ax.set_ylim(e.ydata + (y0 - e.ydata) * f, e.ydata + (y1 - e.ydata) * f)
        self.canvas.draw_idle()

    def _on_press(self, e):
        if e.inaxes is not self.ax:
            return
        if e.dblclick:
            return self.fit_view()
        if e.button in (1, 2, 3):
            self._pan = (e.xdata, e.ydata)
            self.canvas.get_tk_widget().configure(cursor="fleur")

    def _on_motion(self, e):
        if e.inaxes is self.ax and e.xdata is not None:
            d = np.hypot(e.xdata, e.ydata)
            self.cursor_lbl.configure(text=f"x = {e.xdata:+7.3f} m   y = {e.ydata:+7.3f} m   "
                                           f"d = {d:6.3f} m   θ = {np.degrees(np.arctan2(e.ydata, e.xdata)):+7.1f}°")
            if self._pan:
                dx, dy = self._pan[0] - e.xdata, self._pan[1] - e.ydata
                x0, x1 = self.ax.get_xlim()
                y0, y1 = self.ax.get_ylim()
                self.ax.set_xlim(x0 + dx, x1 + dx)
                self.ax.set_ylim(y0 + dy, y1 + dy)
                self.canvas.draw_idle()

    def _on_release(self, e):
        self._pan = None
        self.canvas.get_tk_widget().configure(cursor="")

    # =============================================================== export
    def _export_targets(self):
        caps = [c for c in self.captures if c["visible"].get()]
        if caps:
            return caps
        scan, _ = self._shown()
        if scan is None:
            return []
        return [{"k": 0, "name": "direct", "color": D["live"], "scan": scan, "pose": Pose(),
                 "time": time.strftime("%H:%M:%S"), "source": ""}]

    def _render_each_png(self, folder: Path) -> list[Path]:
        """Une image par scan visible : images_par_scan/scanK.png."""
        folder.mkdir(parents=True, exist_ok=True)
        out = []
        for c in self._export_targets():
            r = c["scan"].ranges
            v = r[r > 0.05]
            title = (f"Scan {c['k']} — {len(r)} points, {len(v) / max(len(r), 1):.0%} valides"
                     + (f", {v.min():.2f} à {v.max():.2f} m" if len(v) else "") + (f" — {c['time']}" if c["time"] else ""))
            path = folder / f"{c['name'] if c['k'] else 'direct'}.png"
            self._render_png(path, [c], title)
            out.append(path)
        return out

    def _render_png(self, path, caps=None, title=None):
        caps = self._export_targets() if caps is None else caps
        fig = Figure(figsize=(10, 8.5), dpi=150, facecolor="white")
        FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_aspect("equal", adjustable="datalim")
        ax.grid(True, color="#E5E7EB", lw=0.8)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for c in caps:
            pts = c["scan"].filtered().world_xy(c["pose"])
            col = c["color"] if c["k"] else "#0284C7"
            ax.scatter(pts[:, 0], pts[:, 1], s=4, color=col, lw=0,
                       label=f"Scan {c['k']} — {len(c['scan'])} points" if c["k"] else "Scan en direct")
            p = c["pose"]
            ax.plot([p.x, p.x + 0.35 * np.cos(p.theta)], [p.y, p.y + 0.35 * np.sin(p.theta)], color=col, lw=2.5)
            ax.plot(p.x, p.y, "o", ms=8, color=col, mec="white", mew=1.5)
        ax.set_xlabel("x (m)")
        ax.set_ylabel("y (m)")
        ax.set_title(title or f"Scans LD06 — {time.strftime('%d/%m/%Y %H:%M')}", loc="left", fontsize=12,
                     weight="bold")
        ax.legend(loc="upper right", fontsize=9, markerscale=3, framealpha=0.95)
        fig.tight_layout()
        fig.savefig(path, format="png")  # path : fichier ou BytesIO
        return len(caps)

    def _write_xlsx(self, path):
        """Classeur Excel : onglets Carte (image), Graphique (nuage de points Excel natif),
        Résumé (un scan par ligne) et Points (tous les points, en vrais nombres)."""
        import io
        from openpyxl import Workbook
        from openpyxl.chart import Reference, ScatterChart, Series
        from openpyxl.drawing.image import Image as XLImage
        from openpyxl.styles import Alignment, Font, PatternFill

        caps = self._export_targets()
        hex_ = lambda c: c.lstrip("#").upper()
        bold, head_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F2937")
        wb = Workbook()

        # --- Carte : l'image PNG
        ws = wb.active
        ws.title = "Carte"
        ws["A1"] = f"Scans LD06 — {time.strftime('%d/%m/%Y %H:%M')}"
        ws["A1"].font = Font(bold=True, size=14)
        ws["A2"] = "Une couleur par scan. Onglet « Graphique » : la même carte en graphique Excel modifiable."
        buf = io.BytesIO()
        self._render_png(buf)
        buf.seek(0)
        img = XLImage(buf)
        img.width, img.height = int(img.width * 0.55), int(img.height * 0.55)
        ws.add_image(img, "A4")

        # --- Points : valides d'abord (plage continue par scan pour le graphique), puis sans écho
        wp = wb.create_sheet("Points")
        cols = ["scan", "point", "angle (°)", "distance (mm)", "intensité", "x lidar (m)", "y lidar (m)",
                "pose x (m)", "pose y (m)", "pose θ (°)", "x carte (m)", "y carte (m)", "valide"]
        wp.append(cols)
        ranges, n = [], 0
        for c in caps:
            s, p = c["scan"], c["pose"]
            loc = s.local_xy()
            world = p.transform(loc)
            valid = (s.ranges >= 0.05) & (s.ranges <= 12.0)
            start = wp.max_row + 1
            for only_valid in (True, False):
                for i in np.nonzero(valid if only_valid else ~valid)[0]:
                    wp.append([c["k"] or "direct", int(i), round(float(np.degrees(s.angles[i])), 2),
                               round(float(s.ranges[i] * 1000)), round(float(s.intensities[i])),
                               round(float(loc[i, 0]), 4), round(float(loc[i, 1]), 4), round(p.x, 3), round(p.y, 3),
                               round(float(np.degrees(p.theta)), 2), round(float(world[i, 0]), 4),
                               round(float(world[i, 1]), 4), "oui" if only_valid else "non"])
                    n += 1
                if only_valid:
                    ranges.append((c, start, wp.max_row))
        for cell in wp[1]:
            cell.font, cell.fill = bold, head_fill
            cell.alignment = Alignment(horizontal="center")
        for i, w in enumerate((8, 7, 10, 13, 10, 12, 12, 11, 11, 11, 12, 12, 8), 1):
            wp.column_dimensions[chr(64 + i)].width = w
        wp.freeze_panes = "A2"
        wp.auto_filter.ref = wp.dimensions

        # --- Résumé
        wr = wb.create_sheet("Résumé", 1)
        wr.append(["scan", "couleur", "heure", "points", "valides (%)", "distance min (m)", "distance max (m)",
                   "pose x (m)", "pose y (m)", "pose θ (°)", "source"])
        for c in caps:
            r = c["scan"].ranges
            v = r[r > 0.05]
            p = c["pose"]
            wr.append([c["k"] or "direct", "", c["time"], len(r), round(100 * len(v) / max(len(r), 1), 1),
                       round(float(v.min()), 3) if len(v) else None, round(float(v.max()), 3) if len(v) else None,
                       round(p.x, 3), round(p.y, 3), round(float(np.degrees(p.theta)), 2), c["source"] or ""])
            wr.cell(row=wr.max_row, column=2).fill = PatternFill("solid", fgColor=hex_(c["color"] if c["k"] else "#0284C7"))
        wr.append([])
        wr.append(["total", "", "", sum(len(c["scan"]) for c in caps)])
        for cell in wr[1]:
            cell.font, cell.fill = bold, head_fill
        for i, w in enumerate((8, 9, 10, 9, 12, 16, 16, 11, 11, 11, 16), 1):
            wr.column_dimensions[chr(64 + i)].width = w

        # --- Graphique : nuage de points Excel, une série par scan, axes à la même échelle
        wg = wb.create_sheet("Graphique", 1)
        ch = ScatterChart()
        ch.title = "Scans LD06 (x, y en mètres)"
        ch.style = 13
        ch.x_axis.title, ch.y_axis.title = "x (m)", "y (m)"
        ch.x_axis.delete = ch.y_axis.delete = False
        allxy = []
        for c, r0, r1 in ranges:
            if r1 < r0:
                continue
            xs = Reference(wp, min_col=11, min_row=r0, max_row=r1)
            ys = Reference(wp, min_col=12, min_row=r0, max_row=r1)
            se = Series(ys, xs, title=f"Scan {c['k']}" if c["k"] else "Direct")
            col = hex_(c["color"] if c["k"] else "#0284C7")
            se.marker.symbol, se.marker.size = "circle", 3
            se.marker.graphicalProperties.solidFill = col
            se.marker.graphicalProperties.line.solidFill = col
            se.graphicalProperties.line.noFill = True
            ch.series.append(se)
            allxy.append(c["scan"].filtered().world_xy(c["pose"]))
        if allxy:
            pts = np.vstack(allxy)
            lo, hi = pts.min(axis=0), pts.max(axis=0)
            cx, cy = (lo + hi) / 2
            half = np.ceil(max(hi - lo) / 2 + 0.5)
            ch.x_axis.scaling.min, ch.x_axis.scaling.max = float(np.floor(cx - half)), float(np.ceil(cx + half))
            ch.y_axis.scaling.min, ch.y_axis.scaling.max = float(np.floor(cy - half)), float(np.ceil(cy + half))
            ch.x_axis.majorUnit = ch.y_axis.majorUnit = 1.0
        # graduations sur les bords (et non sur les axes x=0 / y=0 au milieu), graphique carré = même échelle
        ch.x_axis.crosses = ch.y_axis.crosses = "min"
        ch.x_axis.tickLblPos = ch.y_axis.tickLblPos = "low"
        ch.legend.position = "r"
        ch.width, ch.height = 25, 22  # la légende à droite prend ~3 cm : zone de tracé ≈ carrée
        wg.add_chart(ch, "A1")
        wb.save(path)
        return n

    def _write_csv(self, path):
        """Tous les points : séparateur « ; » et virgule décimale (ouverture directe dans Excel français)."""
        caps = self._export_targets()
        n = 0
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            f.write("scan;point;angle_deg;distance_mm;intensite;x_lidar_m;y_lidar_m;"
                    "pose_x_m;pose_y_m;pose_theta_deg;x_m;y_m\n")
            for c in caps:
                s, p = c["scan"], c["pose"]
                loc = s.local_xy()
                world = p.transform(loc)
                for i in range(len(s)):
                    vals = [f"{np.degrees(s.angles[i]):.2f}", f"{s.ranges[i] * 1000:.0f}", f"{s.intensities[i]:.0f}",
                            f"{loc[i, 0]:.4f}", f"{loc[i, 1]:.4f}", f"{p.x:.3f}", f"{p.y:.3f}",
                            f"{np.degrees(p.theta):.2f}", f"{world[i, 0]:.4f}", f"{world[i, 1]:.4f}"]
                    f.write(f"{c['k'] or 'direct'};{i};" + ";".join(v.replace(".", ",") for v in vals) + "\n")
                    n += 1
        return n

    def export_png(self):
        if not self._export_targets():
            return self._msg("Rien à exporter.", D["warn"])
        self.folder.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(initialdir=self.folder.resolve(), initialfile="carte_scans.png",
                                            defaultextension=".png", filetypes=[("Image PNG", "*.png")])
        if path:
            n = self._render_png(path)
            self._msg(f"Image enregistrée ({n} scan(s)) : {path}", D["ok"])

    def export_csv(self):
        if not self._export_targets():
            return self._msg("Rien à exporter.", D["warn"])
        self.folder.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(initialdir=self.folder.resolve(), initialfile="points_scans.csv",
                                            defaultextension=".csv", filetypes=[("Tableau CSV", "*.csv")])
        if path:
            n = self._write_csv(path)
            self._msg(f"Tableau enregistré ({n} points) : {path}", D["ok"])

    def _xlsx_or_explain(self, path) -> int | None:
        try:
            return self._write_xlsx(path)
        except ImportError:
            messagebox.showerror("Excel indisponible", "Il manque la bibliothèque openpyxl.\n\n"
                                                       "Dans un terminal :  pip install openpyxl\npuis relancez Lidar Plot.")
        except PermissionError:
            messagebox.showerror("Fichier ouvert", f"Impossible d'écrire {path} :\n"
                                                   "le fichier est probablement ouvert dans Excel. Fermez-le et réessayez.")
        return None

    def export_xlsx(self):
        if not self._export_targets():
            return self._msg("Rien à exporter.", D["warn"])
        self.folder.mkdir(parents=True, exist_ok=True)
        path = filedialog.asksaveasfilename(initialdir=self.folder.resolve(), initialfile="scans_lidar.xlsx",
                                            defaultextension=".xlsx", filetypes=[("Classeur Excel", "*.xlsx")])
        if path:
            n = self._xlsx_or_explain(path)
            if n is not None:
                self._msg(f"Classeur Excel enregistré ({n} points) : {path}", D["ok"])
                if messagebox.askyesno("Excel", "Classeur enregistré (onglets Carte, Graphique, Résumé, Points).\n\n"
                                                "L'ouvrir maintenant ?"):
                    try:
                        os.startfile(path)
                    except (AttributeError, OSError):
                        pass

    def export_all(self):
        caps = self._export_targets()
        if not caps:
            return self._msg("Rien à exporter : capturez au moins un scan.", D["warn"])
        self.folder.mkdir(parents=True, exist_ok=True)
        self._render_png(self.folder / "carte_scans.png")
        each = self._render_each_png(self.folder / "images_par_scan")
        n = self._write_csv(self.folder / "points_scans.csv")
        nx = self._xlsx_or_explain(self.folder / "scans_lidar.xlsx")
        (self.folder / "resume.md").write_text(self._summary_md(caps, n), encoding="utf-8")
        files = (f"carte_scans.png, images_par_scan/ ({len(each)} images), "
                 + ("scans_lidar.xlsx, " if nx is not None else "") + "points_scans.csv, resume.md")
        self._msg(f"Exporté dans {self.folder} : {files} ({n} points)", D["ok"])
        if messagebox.askyesno("Export terminé", f"{files}\nenregistrés dans :\n"
                                                f"{self.folder.resolve()}\n\nOuvrir le dossier ?"):
            self.open_folder()

    def _summary_md(self, caps, n_points):
        L = [f"# Scans LD06 — {time.strftime('%d/%m/%Y %H:%M')}", "",
             "| scan | heure | points | valides | distance min | distance max | pose x (m) | pose y (m) | pose θ (°) | source |",
             "|---|---|---|---|---|---|---|---|---|---|"]
        for c in caps:
            r = c["scan"].ranges
            v = r[r > 0.05]
            p = c["pose"]
            L.append(f"| {c['k'] or 'direct'} | {c['time']} | {len(r)} | {len(v) / max(len(r), 1):.0%} | "
                     f"{v.min():.2f} m | {v.max():.2f} m | {p.x:.2f} | {p.y:.2f} | {np.degrees(p.theta):.1f} | "
                     f"{c['source'] or '—'} |" if len(v) else f"| {c['k']} | {c['time']} | {len(r)} | 0 % | — | — | | | | |")
        L += ["", f"Total : {n_points} points.", "", "![carte](carte_scans.png)", "",
              "Fichiers :", "",
              "- `carte_scans.png` : image des scans (une couleur par scan)",
              "- `scans_lidar.xlsx` : classeur Excel (onglets Carte = image, Graphique = nuage de points Excel, "
              "Résumé, Points)",
              "- `points_scans.csv` : tous les points (séparateur « ; », virgule décimale pour Excel) : "
              "angle, distance, intensité, coordonnées dans le repère du lidar et dans le repère de la carte",
              "- `scanK.csv` + `poses.json` : scans au format du projet (angle_deg, distance_mm, intensity), "
              "réutilisables avec `python -m carto view|grid|vector`", ""]
        return "\n".join(L)

    def open_folder(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(self.folder.resolve())
        except (AttributeError, OSError):
            pass

    def close(self):
        if self.source:
            self.source.stop()
        self.root.quit()
        self.root.destroy()


def run_plot(folder=None):
    theme.enable_dpi_awareness()
    root = tk.Tk()
    LidarPlot(root, folder)
    root.mainloop()
