"""Recompresse chaque image PNG de l'historique (palette de 256 couleurs, blanc pur conservé) ; écrit la table ancien -> nouveau blob."""
import io, subprocess, sys
from PIL import Image
out = open(sys.argv[1], "w")
objs = subprocess.run(["git", "rev-list", "--objects", "--all"], capture_output=True, text=True).stdout.splitlines()
blobs = {l.split(" ", 1)[0] for l in objs if l.lower().endswith(".png")}
avant = apres = 0
for h in sorted(blobs):
    data = subprocess.run(["git", "cat-file", "blob", h], capture_output=True).stdout
    try:
        im = Image.open(io.BytesIO(data)); im.load()
    except Exception:
        continue
    if im.mode == "P":
        avant += len(data); apres += len(data); continue
    q = im.quantize(256, method=Image.FASTOCTREE) if im.mode == "RGBA" else im.convert("RGB").quantize(256, method=Image.MEDIANCUT)
    pal = q.getpalette()
    for k in range(0, len(pal) - 2, 3):
        if min(pal[k:k + 3]) >= 240 and max(pal[k:k + 3]) - min(pal[k:k + 3]) <= 6:
            pal[k:k + 3] = [255, 255, 255]
    q.putpalette(pal)
    b = io.BytesIO(); q.save(b, "PNG", optimize=True)
    avant += len(data)
    if b.tell() < len(data) * 0.9:
        new = subprocess.run(["git", "hash-object", "-w", "--stdin"], input=b.getvalue(), capture_output=True).stdout.decode().strip()
        out.write(f"{h} {new}\n"); apres += b.tell()
    else:
        apres += len(data)
print(f"{len(blobs)} images : {avant/1e6:.1f} Mo -> {apres/1e6:.1f} Mo")
