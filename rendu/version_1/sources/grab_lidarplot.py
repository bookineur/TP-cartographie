"""Capture de Lidar Plot ouvert sur la session assemblée (scans réels, une couleur par scan)."""
import os, sys, time, tkinter as tk
from pathlib import Path
sys.path.insert(0, r"C:\Users\HP\TP-cartographie")
os.chdir(r"C:\Users\HP\TP-cartographie")
from carto import plot_app as P, theme

theme.enable_dpi_awareness()
last = Path("data/.derniere_session")
saved = last.read_text(encoding="utf-8") if last.exists() else None
root = tk.Tk()
app = P.LidarPlot(root, r"data\salle_2026-11-02_18h31\carte\version_2\session_assemblee")
app.select(1)
root.attributes("-topmost", True)
t = time.time()
while time.time() - t < 2.0:
    root.update(); time.sleep(0.02)
app.fit_view()
t = time.time()
while time.time() - t < 0.8:
    root.update(); time.sleep(0.02)
from PIL import ImageGrab
x, y = root.winfo_rootx(), root.winfo_rooty()
ImageGrab.grab((x, y, x + root.winfo_width(), y + root.winfo_height()), all_screens=True).save(sys.argv[1])
app.close()
if saved is not None:  # ne pas changer la « dernière session » de l'utilisateur
    last.write_text(saved, encoding="utf-8")
