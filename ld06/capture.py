"""Capture de scans réels LD06 et sauvegarde en CSV (coordonnées polaires).

Deux montages possibles :

  --mode arduino : LD06 -> carte Arduino/Teensy avec le sketch
                   arduino/LD06_capture -> USB -> PC. Le sketch utilise la
                   librairie fournie (printScanCSV) ; on lit le CSV texte.
  --mode raw     : LD06 -> adaptateur USB-UART (CP2102...) -> PC, 230400 bauds.
                   Le décodage des paquets est fait ici (ld06/protocol.py).

Exemples :
    python -m ld06.capture --port COM5 --mode arduino --count 5 --out data/salle --prefix pos1
    python -m ld06.capture --port COM6 --mode raw --count 5 --out data/salle --save-raw dump.bin
    python -m ld06.capture --replay dump.bin --out data/rejeu      (relit un dump brut)
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from carto.scan import save_scan_csv
from ld06.protocol import PacketParser, ScanAssembler
from ld06.sources import ArduinoCSVAssembler


def _open_serial(port: str, baud: int):
    try:
        import serial  # pyserial
    except ImportError:
        sys.exit("pyserial manquant : pip install pyserial")
    from serial.tools import list_ports
    try:
        return serial.Serial(port, baud, timeout=0.1)
    except serial.SerialException as e:
        ports = [f"  {p.device}  ({p.description})" for p in list_ports.comports()]
        sys.exit(f"Impossible d'ouvrir {port} : {e}\n"
                 + ("Ports disponibles :\n" + "\n".join(ports) if ports else
                    "Aucun port série détecté : carte non branchée, câble USB « charge seule », "
                    "ou pilote manquant (CH340/CP210x pour les clones, Teensyduino pour Teensy).")
                 + "\nAstuce : port déjà ouvert par le moniteur série de l'IDE Arduino ? Fermez-le.")


def capture_raw(stream, count: int, raw_dump=None, timeout_s: float = 30.0, stop_on_eof=False):
    """Lit des octets bruts LD06 et renvoie `count` scans complets."""
    parser, assembler = PacketParser(), ScanAssembler()
    scans, t0 = [], time.time()
    while len(scans) < count and time.time() - t0 < timeout_s:
        data = stream.read(512)
        if not data:
            if stop_on_eof:
                break  # fin du fichier en mode rejeu
            continue
        if raw_dump is not None:
            raw_dump.write(data)
        for packet in parser.feed(data):
            scan = assembler.add(packet)
            if scan:
                scans.append(scan)
                print(f"  scan {len(scans)}/{count} : {len(scan['angle_deg'])} points, "
                      f"{scan['speed_dps'] / 360:.1f} tr/s, CRC KO cumulés = {parser.crc_failures}")
    return scans


def capture_arduino(ser, count: int, timeout_s: float = 30.0):
    """Lit la sortie de LD06::printScanCSV : 'N,Angle,Distance,Intensity,x,y', ligne vide = fin de scan."""
    asm, scans, t0 = ArduinoCSVAssembler(), [], time.time()
    while len(scans) < count and time.time() - t0 < timeout_s:
        scan = asm.feed_line(ser.readline().decode("ascii", errors="ignore"))
        if scan:  # la librairie donne déjà l'angle en sens trigo
            scans.append(scan)
            print(f"  scan {len(scans)}/{count} : {len(scan['angle_deg'])} points")
    return scans


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="port série (COM5, /dev/ttyUSB0...)")
    ap.add_argument("--mode", choices=["arduino", "raw"], default="arduino")
    ap.add_argument("--baud", type=int, help="défaut : 230400 (raw) / 921600 (arduino)")
    ap.add_argument("--count", type=int, default=5, help="nombre de scans à enregistrer")
    ap.add_argument("--out", default="data/scans", help="dossier de sortie")
    ap.add_argument("--prefix", default="scan", help="préfixe des fichiers (ex : pos1)")
    ap.add_argument("--save-raw", help="(raw) enregistre aussi les octets bruts dans ce fichier")
    ap.add_argument("--replay", help="relit un dump brut au lieu d'un port série")
    ap.add_argument("--skip", type=int, default=2, help="scans ignorés au démarrage (moteur pas stable)")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    n = args.count + args.skip

    if args.replay:
        with open(args.replay, "rb") as f:
            scans = capture_raw(f, n, stop_on_eof=True)
    else:
        if not args.port:
            ap.error("--port est obligatoire (ou --replay)")
        baud = args.baud or (230400 if args.mode == "raw" else 921600)
        with _open_serial(args.port, baud) as ser:
            print(f"Lecture {args.port} @ {baud} bauds, mode {args.mode}...")
            if args.mode == "raw":
                dump = open(args.save_raw, "wb") if args.save_raw else None
                try:
                    scans = capture_raw(ser, n, dump)
                finally:
                    if dump:
                        dump.close()
            else:
                scans = capture_arduino(ser, n)

    scans = scans[args.skip:] if len(scans) > args.skip else scans
    if not scans:
        sys.exit("Aucun scan complet reçu : vérifier câblage, port, baudrate.")
    for k, s in enumerate(scans):
        path = out / f"{args.prefix}_{k:03d}.csv"
        save_scan_csv(path, s["angle_deg"], s["distance_mm"], s["intensity"],
                      meta={"speed_dps": s.get("speed_dps", 0), "mode": args.mode})
        print(f"-> {path}")


if __name__ == "__main__":
    main()
