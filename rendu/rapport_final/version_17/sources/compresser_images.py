"""Rapport v17 allégé : recompresse les images PNG du .docx (largeur max 1600 px, palette de 256 couleurs).
Une image n'est remplacée que si elle devient plus petite ; mêmes noms de fichiers, donc mise en page inchangée.
Usage : python compresser_images.py <fichier.docx>"""
import io, shutil, sys, zipfile
from PIL import Image

src = sys.argv[1]; tmp = src + ".tmp"
avant = apres = 0
with zipfile.ZipFile(src) as zi, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
    for it in zi.infolist():
        data = zi.read(it)
        if it.filename.startswith("word/media/") and it.filename.endswith(".png"):
            im = Image.open(io.BytesIO(data)); im.load()
            if im.width > 1600:
                im = im.resize((1600, round(im.height * 1600 / im.width)), Image.LANCZOS)
            q = im.quantize(256, method=Image.FASTOCTREE) if im.mode == "RGBA" else im.convert("RGB").quantize(256, method=Image.MEDIANCUT)
            pal = q.getpalette()  # le blanc du fond doit rester blanc pur (sinon fond légèrement gris)
            for k in range(0, len(pal) - 2, 3):
                if min(pal[k:k + 3]) >= 240 and max(pal[k:k + 3]) - min(pal[k:k + 3]) <= 6:
                    pal[k:k + 3] = [255, 255, 255]
            q.putpalette(pal)
            b = io.BytesIO(); q.save(b, "PNG", optimize=True)
            avant += len(data)
            if b.tell() < len(data):
                data = b.getvalue()
            apres += len(data)
        zo.writestr(it, data)
shutil.move(tmp, src)
print(f"images : {avant/1e6:.2f} Mo -> {apres/1e6:.2f} Mo")
