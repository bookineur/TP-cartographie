"""Sources de scans « en direct », lues dans un thread pour ne pas bloquer l'interface.

Toutes les sources produisent des dicts :
    {"angle_deg": [...], "distance_mm": [...], "intensity": [...], "speed_dps": int}
(angle en sens trigo, 0 = avant du lidar) et les déposent dans une file.
"""
from __future__ import annotations

import collections
import queue
import threading
import time

import numpy as np

from ld06.protocol import PacketParser, ScanAssembler


class ArduinoCSVAssembler:
    """Reconstitue les tours à partir des lignes de LD06::printScanCSV
    ('N,Angle,Distance,Intensity,x,y', ligne vide = fin de tour)."""

    MIN_POINTS = 50

    def __init__(self):
        self._cur = None

    def feed_line(self, line: str):
        line = line.strip()
        done = None
        if not line or line.startswith("N,"):
            done, self._cur = self._finish(), None
            return done
        parts = line.split(",")
        if len(parts) < 4:
            return None
        try:
            n, ang, dist, inten = int(parts[0]), float(parts[1]), int(parts[2]), int(parts[3])
        except ValueError:
            return None
        if n == 0 or self._cur is None:
            done = self._finish()
            self._cur = {"angle_deg": [], "distance_mm": [], "intensity": [], "speed_dps": 0}
        self._cur["angle_deg"].append(ang)
        self._cur["distance_mm"].append(dist)
        self._cur["intensity"].append(inten)
        return done

    def _finish(self):
        cur = self._cur
        return cur if cur and len(cur["angle_deg"]) >= self.MIN_POINTS else None


def parse_teleplot_line(line: str):
    """Une ligne Teleplot -> ("xy", nom, [(x, y), ...]) ou ("var", nom, valeur) ou None.

    Formats (https://github.com/nesnes/teleplot) :
        >nom:valeur              >nom:timestamp_ms:valeur
        >nom:x:y;x:y;...|xy      (nuage de points, ce qu'envoie LD06::printScanTeleplot)
    """
    line = line.strip()
    if not line.startswith(">") or ":" not in line:
        return None
    body, _, flags = line[1:].partition("|")
    name, _, rest = body.partition(":")
    name = name.split("§")[0].strip()
    if "xy" in flags.split(","):
        pts = []
        for pair in rest.split(";"):
            parts = pair.split(":")
            if len(parts) >= 2:
                try:
                    pts.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    continue
        return ("xy", name, pts)
    try:
        return ("var", name, float(rest.split(":")[-1]))
    except ValueError:
        return None


def xy_mm_to_scan(points, mirror=True) -> dict:
    """Points (x, y) en mm de la librairie -> scan polaire (angle trigo, distance).

    La librairie calcule y = -d·sin(angle_trigo) : ses x, y sont en miroir
    (repère horaire du capteur). mirror=True remet le repère trigo
    (y vers la gauche du lidar)."""
    a = np.asarray(points, float).reshape(-1, 2)
    x, y = a[:, 0], (-a[:, 1] if mirror else a[:, 1])
    d = np.hypot(x, y)
    ang = np.degrees(np.arctan2(y, x)) % 360.0
    keep = d > 0
    return {"angle_deg": ang[keep].tolist(), "distance_mm": d[keep].tolist(),
            "intensity": [0] * int(keep.sum()), "speed_dps": 0}


class _ThreadedSource:
    """Base : un thread remplit une file bornée (on garde les scans les plus récents)."""

    def __init__(self):
        self.queue: queue.Queue = queue.Queue(maxsize=50)
        self.error: str | None = None
        self.n_scans = 0
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._safe_run, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def _push(self, scan):
        self.n_scans += 1
        scan["t"] = time.time()
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
        self.queue.put(scan)

    def _safe_run(self):
        try:
            self._run()
        except Exception as e:  # remonté à l'interface
            self.error = f"{type(e).__name__}: {e}"

    def _run(self):
        raise NotImplementedError


class SerialSource(_ThreadedSource):
    """Port série : mode 'arduino' (CSV du sketch LD06_capture) ou 'raw' (LD06 direct)."""

    def __init__(self, port: str, mode="arduino", baud=None):
        super().__init__()
        self.port, self.mode = port, mode
        self.baud = baud or (230400 if mode == "raw" else 921600)
        self.crc_failures = 0
        self.packets_ok = 0
        self.bytes_received = 0   # pour le diagnostic : rien n'arrive / arrive mais illisible
        self.lines_received = 0

    def _run(self):
        import serial
        with serial.Serial(self.port, self.baud, timeout=0.1) as ser:
            if self.mode == "raw":
                parser, asm = PacketParser(), ScanAssembler()
                while not self._stop.is_set():
                    data = ser.read(512)
                    self.bytes_received += len(data)
                    for p in parser.feed(data):
                        s = asm.add(p)
                        if s:
                            self._push(s)
                    self.crc_failures, self.packets_ok = parser.crc_failures, parser.packets_ok
            else:
                asm = ArduinoCSVAssembler()
                while not self._stop.is_set():
                    raw = ser.readline()
                    if raw:
                        self.bytes_received += len(raw)
                        self.lines_received += 1
                        s = asm.feed_line(raw.decode("ascii", errors="ignore"))
                        if s:
                            self._push(s)


class TextSerialSource(_ThreadedSource):
    """Port série « texte », comme Teleplot : accepte en même temps
      - les nuages Teleplot  >lidar:x:y;x:y;...|xy   (sketch Basic de la librairie)
      - les variables        >nom:valeur             (affichées à part)
      - le CSV de printScanCSV (sketch LD06_capture)
    et garde les dernières lignes reçues pour la console."""

    def __init__(self, port: str, baud=115200, mirror=True):
        super().__init__()
        self.port, self.baud, self.mirror = port, baud, mirror
        self.mode = "texte"
        self.variables: dict[str, float] = {}
        self.console = collections.deque(maxlen=300)
        self.bytes_received = self.lines_received = 0
        self.packets_ok = self.crc_failures = 0
        self.formats_seen: set[str] = set()

    def feed_line(self, text: str, csv_asm: ArduinoCSVAssembler):
        self.lines_received += 1
        short = text if len(text) <= 160 else text[:157] + "…"
        self.console.append(short)
        tp = parse_teleplot_line(text)
        if tp:
            kind, name, val = tp
            if kind == "xy" and len(val) >= 20:
                self.formats_seen.add("Teleplot")
                scan = xy_mm_to_scan(val, self.mirror)
                scan["source"] = f"teleplot:{name}"
                self._push(scan)
            elif kind == "var":
                self.variables[name] = val
            return
        s = csv_asm.feed_line(text)
        if s:
            self.formats_seen.add("CSV")
            s["source"] = "csv"
            self._push(s)

    def _run(self):
        import serial
        csv_asm = ArduinoCSVAssembler()
        with serial.Serial(self.port, self.baud, timeout=0.1) as ser:
            while not self._stop.is_set():
                raw = ser.readline()
                if raw:
                    self.bytes_received += len(raw)
                    self.feed_line(raw.decode("utf-8", errors="replace").rstrip("\r\n"), csv_asm)


class SimSource(_ThreadedSource):
    """Lidar virtuel dans la salle simulée : pour s'entraîner sans matériel.
    `true_pose` (Pose) peut être changée à tout moment (= on déplace le lidar)."""

    def __init__(self, true_pose, rate_hz=5.0, noise_m=0.03, seed=None):
        super().__init__()
        self.true_pose, self.rate, self.noise = true_pose, rate_hz, noise_m
        self.rng = np.random.default_rng(seed)

    def _run(self):
        from carto.simulate import raycast
        while not self._stop.is_set():
            n = 450
            ang = (np.arange(n) * 360.0 / n + self.rng.uniform(0, 0.8)) % 360.0
            r = raycast(self.true_pose, np.radians(ang))
            valid = r > 0
            r = r + self.rng.normal(0, self.noise, n) * valid
            r[self.rng.random(n) < 0.02] = 0.0
            inten = np.where(r > 0, np.clip(self.rng.normal(200, 20, n) - 8 * r, 0, 255), 0)
            self._push({"angle_deg": ang.tolist(), "distance_mm": (np.maximum(r, 0) * 1000).tolist(),
                        "intensity": inten.tolist(), "speed_dps": 3600})
            time.sleep(1.0 / self.rate)


def classify_stream(text_sample: bytes, raw_sample: bytes) -> str | None:
    """Devine le montage d'après deux échantillons lus sur le port :
    text_sample à 921600 bauds, raw_sample à 230400 bauds.
    'arduino' si on reçoit des lignes CSV du sketch, 'raw' si on reçoit des
    paquets LD06 valides (en-tête + CRC), None sinon."""
    lines = text_sample.decode("ascii", errors="ignore").splitlines()
    csv_like = sum(1 for l in lines if l.count(",") >= 3 and l.split(",")[0].strip().isdigit())
    if csv_like >= 5 or any(l.startswith("N,Angle") for l in lines):
        return "arduino"
    if raw_sample and PacketParser().feed(raw_sample):
        return "raw"
    return None


def detect_port_and_mode(ports=None, listen_s=2.5, log=None) -> tuple[str, str] | None:
    """Essaie chaque port : écoute en 921600 (sketch) puis en 230400 (LD06 direct).
    L'ouverture du port redémarre la plupart des Arduino : on écoute assez
    longtemps pour laisser passer le bootloader et le premier tour."""
    import serial
    ports = ports if ports is not None else [p for p, _ in list_serial_ports()]
    for port in ports:
        samples = {}
        for baud in (921600, 230400):
            if log:
                log(f"{port} @ {baud}…")
            try:
                with serial.Serial(port, baud, timeout=0.1) as ser:
                    buf, t0 = bytearray(), time.time()
                    while time.time() - t0 < listen_s and len(buf) < 20000:
                        buf += ser.read(2048)
                    samples[baud] = bytes(buf)
            except Exception as e:  # port occupé, débranché...
                if log:
                    log(f"{port} : {e}")
                break
            mode = classify_stream(samples.get(921600, b""), samples.get(230400, b""))
            if mode:
                return port, mode
    return None


def probe_port(port: str, listen_s=2.5, log=None) -> tuple[str, int] | None:
    """Trouve le format et le débit d'UN port : texte (Teleplot ou CSV) à
    115200 (exemple Basic) ou 921600 (sketch LD06_capture), sinon LD06 brut à
    230400. Renvoie ("texte" | "raw", baud) ou None."""
    import serial
    for baud in (115200, 921600, 230400):
        if log:
            log(f"{port} @ {baud} bauds…")
        try:
            with serial.Serial(port, baud, timeout=0.1) as ser:
                buf, t0 = bytearray(), time.time()
                while time.time() - t0 < listen_s and len(buf) < 30000:
                    buf += ser.read(4096)
        except Exception as e:
            if log:
                log(f"{port} : {e}")
            raise  # port occupé / introuvable : l'appelant affiche la vraie cause
        if baud == 230400:
            if PacketParser().feed(bytes(buf)):
                return "raw", baud
            continue
        lines = bytes(buf).decode("utf-8", errors="ignore").splitlines()
        if any(parse_teleplot_line(l) for l in lines) or classify_stream(bytes(buf), b"") == "arduino":
            return "texte", baud
    return None


def list_serial_ports() -> list[tuple[str, str]]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    return [(p.device, p.description) for p in list_ports.comports()]
