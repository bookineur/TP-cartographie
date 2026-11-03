"""Thème visuel de l'assistant : palette, styles ttk, couleurs de la carte."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

C = {
    "bg": "#F1F4F9", "card": "#FFFFFF", "border": "#E2E8F0", "text": "#0F172A", "muted": "#64748B",
    "primary": "#2563EB", "primary_dark": "#1D4ED8", "primary_soft": "#DBEAFE",
    "ok": "#16A34A", "ok_soft": "#DCFCE7", "warn": "#D97706", "warn_soft": "#FEF3C7",
    "error": "#DC2626", "error_soft": "#FEE2E2",
    "header": "#0F172A", "header_text": "#F8FAFC", "header_muted": "#94A3B8",
    "free": "#FFFFFF", "unknown": "#D5DCE6", "wall": "#1E293B",
    "live": "#EF4444", "pose": "#2563EB", "star": "#F59E0B", "ghost": "#94A3B8",
}
FONT = "Segoe UI"

# carte d'occupation : p=0 (libre) blanc, p=0.5 (inconnu) gris bleuté, p=1 (mur) bleu nuit
OCC_CMAP = LinearSegmentedColormap.from_list(
    "occupation", [(0.0, C["free"]), (0.5, C["unknown"]), (1.0, C["wall"])])


def tk_figure_canvas(figure, master):
    """FigureCanvasTkAgg sans double mise à l'échelle.

    Avec `enable_dpi_awareness()`, 1 pixel Tk = 1 pixel écran : la mise à l'échelle
    Windows (125 %, 150 %…) est déjà prise en compte (dpi de la figure × échelle).
    Matplotlib, lui, ré-applique ce facteur (device_pixel_ratio = 1,25) : la figure
    devient plus grande que la zone (carte rognée en bas / à droite) et la position
    de la souris ne correspond plus aux points affichés (rotation impossible).
    On force donc un rapport de 1."""
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    class _Canvas(FigureCanvasTkAgg):
        def _update_device_pixel_ratio(self, event=None):
            if self._set_device_pixel_ratio(1.0):
                w, h = self.get_width_height(physical=True)
                self._tkcanvas.configure(width=w, height=h)

    canvas = _Canvas(figure, master=master)
    canvas._update_device_pixel_ratio()
    return canvas


def enable_dpi_awareness():
    """Fenêtre nette sur les écrans à 125-150 % (sinon Windows l'agrandit en la floutant).
    À appeler AVANT de créer la fenêtre Tk."""
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


def apply(root: tk.Tk) -> float:
    """Applique les styles ; renvoie le facteur d'échelle (1.0 à 96 dpi)."""
    scale = root.winfo_fpixels("1i") / 96.0
    root.configure(bg=C["bg"])
    s = ttk.Style(root)
    s.theme_use("clam")
    base = (FONT, 10)
    s.configure(".", font=base, background=C["card"], foreground=C["text"], bordercolor=C["border"],
                lightcolor=C["border"], darkcolor=C["border"], focuscolor=C["primary"])
    s.configure("Bg.TFrame", background=C["bg"])
    s.configure("Card.TFrame", background=C["card"])
    s.configure("TLabel", background=C["card"], foreground=C["text"])
    s.configure("Muted.TLabel", background=C["card"], foreground=C["muted"], font=(FONT, 9))
    s.configure("TRadiobutton", background=C["card"])
    s.map("TRadiobutton", background=[("active", C["card"])])

    pad = (int(10 * scale), int(5 * scale))
    s.configure("TButton", background="#F1F5F9", padding=pad, relief="flat", borderwidth=1)
    s.map("TButton", background=[("disabled", "#F8FAFC"), ("pressed", "#E2E8F0"), ("active", "#E8EEF6")],
          foreground=[("disabled", "#94A3B8")])
    s.configure("Small.TButton", padding=(int(4 * scale), int(1 * scale)), font=(FONT, 10, "bold"))
    for name, col, dark in (("Accent", C["primary"], C["primary_dark"]), ("Success", C["ok"], "#15803D")):
        s.configure(f"{name}.TButton", background=col, foreground="white", bordercolor=col,
                    font=(FONT, 10, "bold"), padding=(pad[0], int(8 * scale)))
        s.map(f"{name}.TButton", background=[("disabled", "#CBD5E1"), ("pressed", dark), ("active", dark)],
              foreground=[("disabled", "white")], bordercolor=[("active", dark)])

    s.configure("TEntry", fieldbackground="white", padding=int(4 * scale))
    s.map("TEntry", bordercolor=[("focus", C["primary"])], lightcolor=[("focus", C["primary"])])
    s.configure("TCombobox", fieldbackground="white", padding=int(4 * scale), arrowsize=int(14 * scale))
    s.map("TCombobox", fieldbackground=[("readonly", "white")], bordercolor=[("focus", C["primary"])])
    s.configure("TSpinbox", fieldbackground="white", padding=int(3 * scale), arrowsize=int(12 * scale))

    s.configure("Treeview", background="white", fieldbackground="white", rowheight=int(24 * scale),
                bordercolor=C["border"], font=(FONT, 9))
    s.configure("Treeview.Heading", background="#F8FAFC", foreground=C["muted"], font=(FONT, 9, "bold"),
                relief="flat", padding=int(3 * scale))
    s.map("Treeview", background=[("selected", C["primary_soft"])], foreground=[("selected", C["text"])])

    for lvl in ("ok", "warn", "error", "muted"):
        col = C[lvl] if lvl != "muted" else "#CBD5E1"
        s.configure(f"{lvl}.Horizontal.TProgressbar", troughcolor="#EEF2F7", background=col,
                    bordercolor="#EEF2F7", lightcolor=col, darkcolor=col, thickness=int(10 * scale))
    s.configure("Vertical.TScrollbar", background="#E2E8F0", troughcolor=C["card"], bordercolor=C["card"],
                arrowsize=int(12 * scale))
    return scale


def card(parent, title: str, scale: float, subtitle: str = ""):
    """Encadré blanc à bord fin avec un titre ; renvoie le cadre intérieur."""
    outer = tk.Frame(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["border"])
    outer.pack(fill="x", pady=(0, int(8 * scale)))
    head = tk.Frame(outer, bg=C["card"])
    head.pack(fill="x", padx=int(12 * scale), pady=(int(9 * scale), int(2 * scale)))
    tk.Label(head, text=title, bg=C["card"], fg=C["text"], font=(FONT, 11, "bold")).pack(side="left")
    if subtitle:
        tk.Label(head, text=subtitle, bg=C["card"], fg=C["muted"], font=(FONT, 9)).pack(side="left", padx=6)
    inner = ttk.Frame(outer, style="Card.TFrame")
    inner.pack(fill="both", expand=True, padx=int(12 * scale), pady=(int(2 * scale), int(10 * scale)))
    return inner, outer


# ------------------------------------------------------------------ thème sombre (façon Teleplot)
D = {
    "bg": "#0D1117", "panel": "#161B22", "panel2": "#1C2128", "border": "#30363D", "text": "#E6EDF3",
    "muted": "#8B949E", "accent": "#2F81F7", "accent_dark": "#1F6FEB", "ok": "#3FB950", "ok_dark": "#2EA043",
    "warn": "#D29922", "error": "#F85149", "error_dark": "#DA3633",
    "plot_bg": "#0D1117", "grid": "#21262D", "ring": "#30363D", "live": "#38BDF8",
}
# couleurs des scans capturés : 1er vert, puis une couleur différente à chaque capture
SCAN_COLORS = ["#22C55E", "#F97316", "#D946EF", "#EAB308", "#3B82F6", "#EF4444", "#14B8A6", "#A3E635"]


def apply_dark(root: tk.Tk) -> float:
    scale = root.winfo_fpixels("1i") / 96.0
    root.configure(bg=D["bg"])
    for k, v in (("*TCombobox*Listbox.background", D["panel2"]), ("*TCombobox*Listbox.foreground", D["text"]),
                 ("*TCombobox*Listbox.selectBackground", D["accent"]), ("*TCombobox*Listbox.font", (FONT, 10))):
        root.option_add(k, v)
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", font=(FONT, 10), background=D["panel"], foreground=D["text"], bordercolor=D["border"],
                lightcolor=D["border"], darkcolor=D["border"], troughcolor=D["bg"], focuscolor=D["accent"],
                fieldbackground=D["panel2"], selectbackground=D["accent"], insertcolor=D["text"])
    s.configure("Bg.TFrame", background=D["bg"])
    s.configure("Panel.TFrame", background=D["panel"])
    s.configure("TLabel", background=D["panel"], foreground=D["text"])
    s.configure("Muted.TLabel", background=D["panel"], foreground=D["muted"], font=(FONT, 9))
    s.configure("TCheckbutton", background=D["panel"], foreground=D["text"], indicatorbackground=D["panel2"],
                indicatorforeground=D["text"])
    s.map("TCheckbutton", background=[("active", D["panel"])], indicatorbackground=[("selected", D["accent"])])
    pad = (int(10 * scale), int(5 * scale))
    s.configure("TButton", background=D["panel2"], foreground=D["text"], padding=pad, relief="flat")
    s.map("TButton", background=[("disabled", D["panel"]), ("pressed", D["border"]), ("active", "#262C36")],
          foreground=[("disabled", "#484F58")])
    s.configure("Small.TButton", padding=(int(5 * scale), int(1 * scale)))
    for name, col, dark in (("Accent", D["accent"], D["accent_dark"]), ("Ok", D["ok_dark"], "#238636"),
                            ("Danger", D["error_dark"], "#B62324")):
        s.configure(f"{name}.TButton", background=col, foreground="white", bordercolor=col,
                    font=(FONT, 10, "bold"), padding=(pad[0], int(7 * scale)))
        s.map(f"{name}.TButton", background=[("disabled", D["border"]), ("pressed", dark), ("active", dark)],
              foreground=[("disabled", D["muted"])], bordercolor=[("active", dark)])
    s.configure("TEntry", fieldbackground=D["panel2"], foreground=D["text"], padding=int(3 * scale))
    s.map("TEntry", bordercolor=[("focus", D["accent"])], lightcolor=[("focus", D["accent"])])
    s.configure("TCombobox", fieldbackground=D["panel2"], foreground=D["text"], background=D["panel2"],
                arrowcolor=D["text"], padding=int(3 * scale), arrowsize=int(13 * scale))
    s.map("TCombobox", fieldbackground=[("readonly", D["panel2"])], foreground=[("readonly", D["text"])],
          selectbackground=[("readonly", D["panel2"])], selectforeground=[("readonly", D["text"])],
          bordercolor=[("focus", D["accent"])])
    s.configure("Horizontal.TScale", background=D["panel"], troughcolor=D["panel2"])
    s.configure("Vertical.TScrollbar", background=D["panel2"], troughcolor=D["panel"], bordercolor=D["panel"],
                arrowcolor=D["muted"], arrowsize=int(11 * scale))
    return scale


def style_axes(ax):
    ax.set_facecolor(C["unknown"])
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#CBD5E1")
    ax.tick_params(colors=C["muted"], labelsize=8, length=3)
    ax.xaxis.label.set_color(C["muted"])
    ax.yaxis.label.set_color(C["muted"])
    ax.grid(True, color="white", lw=0.6, alpha=0.6)
    ax.set_axisbelow(False)


def legend_handles(with_live=True, with_stars=True):
    h = [Patch(facecolor=C["wall"], label="mur"), Patch(facecolor=C["free"], edgecolor="#CBD5E1", label="libre"),
         Patch(facecolor=C["unknown"], edgecolor="#CBD5E1", label="inconnu"),
         Line2D([], [], marker="o", ls="", ms=8, mfc=C["pose"], mec="white", label="position capturée")]
    if with_live:
        h.append(Line2D([], [], marker="o", ls="", ms=4, mfc=C["live"], mec=C["live"], label="scan en direct"))
    if with_stars:
        h.append(Line2D([], [], marker="*", ls="", ms=12, mfc=C["star"], mec="white", label="position suggérée"))
    return h
