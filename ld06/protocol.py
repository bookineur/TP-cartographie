"""Décodage du protocole série du LD06 (miroir Python de src/ld06.cpp).

Format d'un paquet (47 octets, little-endian) :

    offset  taille  champ
    0       1       header      = 0x54
    1       1       ver_len     = 0x2C  (3 bits "type" + 5 bits "nb points" -> 12)
    2       2       speed       vitesse de rotation en °/s
    4       2       start_angle angle du 1er point, en 0.01°
    6       36      12 x (distance u16 en mm, intensity u8)
    42      2       end_angle   angle du dernier point, en 0.01°
    44      2       timestamp   en ms (repasse à 0 après 30000)
    46      1       crc         CRC-8 (polynôme 0x4D) des 46 octets précédents

Les angles du capteur sont dans SON repère : 0° = devant, sens HORAIRE.
On les convertit ici en convention mathématique (sens TRIGO) comme le fait
la librairie Arduino : angle_trigo = 360 - angle_capteur.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass, field

HEADER = 0x54
VER_LEN = 0x2C
PTS_PER_PACKET = 12
PACKET_SIZE = 47
_STRUCT = struct.Struct("<BBHH" + "HB" * PTS_PER_PACKET + "HHB")
assert _STRUCT.size == PACKET_SIZE


def _make_crc_table(poly: int = 0x4D) -> list[int]:
    """Table CRC-8 (MSB first, init 0). Identique à CrcTable de ld06crc.h."""
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = ((crc << 1) ^ poly) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        table.append(crc)
    return table


CRC_TABLE = _make_crc_table()


def crc8(data: bytes) -> int:
    crc = 0
    for b in data:
        crc = CRC_TABLE[crc ^ b]
    return crc


@dataclass
class Packet:
    speed_dps: int          # °/s
    start_angle: float      # degrés, repère capteur (horaire)
    end_angle: float        # degrés, repère capteur (horaire)
    distances: list[int]    # mm (0 = pas d'écho)
    intensities: list[int]  # 0-255 ("confidence")
    timestamp_ms: int

    def sensor_angles(self) -> list[float]:
        """Angle (repère capteur, horaire) de chacun des 12 points.

        Seuls le premier et le dernier angle sont transmis : on interpole
        linéairement, en gérant le passage 359° -> 0°.
        """
        span = (self.end_angle - self.start_angle) % 360.0
        step = span / (PTS_PER_PACKET - 1)
        return [(self.start_angle + i * step) % 360.0 for i in range(PTS_PER_PACKET)]

    def math_angles(self) -> list[float]:
        """Mêmes angles en convention trigo (sens anti-horaire), comme la librairie."""
        return [(360.0 - a) % 360.0 for a in self.sensor_angles()]


def decode_packet(raw: bytes) -> Packet:
    v = _STRUCT.unpack(raw)
    measures = v[4:4 + 2 * PTS_PER_PACKET]
    return Packet(
        speed_dps=v[2],
        start_angle=v[3] / 100.0,
        distances=list(measures[0::2]),
        intensities=list(measures[1::2]),
        end_angle=v[-3] / 100.0,
        timestamp_ms=v[-2],
    )


def encode_packet(p: Packet) -> bytes:
    """Utile pour les tests et la simulation : fabrique un paquet valide."""
    measures = []
    for d, i in zip(p.distances, p.intensities):
        measures += [d, i]
    body = _STRUCT.pack(HEADER, VER_LEN, p.speed_dps, round(p.start_angle * 100) % 36000,
                        *measures, round(p.end_angle * 100) % 36000, p.timestamp_ms, 0)
    return body[:-1] + bytes([crc8(body[:-1])])


@dataclass
class PacketParser:
    """Machine à états : on accumule les octets et on cherche 0x54 0x2C.

    Différence volontaire avec la librairie : en cas de CRC faux, la librairie
    jette les 47 octets ; ici on ne jette que l'octet 0x54 et on recherche un
    nouvel en-tête juste après, ce qui évite de rater un vrai paquet qui
    commencerait au milieu du faux.
    """
    check_crc: bool = True
    crc_failures: int = 0
    packets_ok: int = 0
    _buf: bytearray = field(default_factory=bytearray)

    def feed(self, data: bytes) -> list[Packet]:
        self._buf += data
        out = []
        while True:
            start = self._buf.find(bytes([HEADER, VER_LEN]))
            if start < 0:
                # garder le dernier octet : il peut être le 0x54 d'un en-tête coupé
                del self._buf[:max(0, len(self._buf) - 1)]
                return out
            if len(self._buf) - start < PACKET_SIZE:
                del self._buf[:start]
                return out
            raw = bytes(self._buf[start:start + PACKET_SIZE])
            if self.check_crc and crc8(raw[:-1]) != raw[-1]:
                self.crc_failures += 1
                del self._buf[:start + 1]
                continue
            self.packets_ok += 1
            out.append(decode_packet(raw))
            del self._buf[:start + PACKET_SIZE]


@dataclass
class ScanAssembler:
    """Regroupe les paquets de 12 points en tours complets (~450 points à 10 Hz).

    Un nouveau tour commence quand l'angle capteur "retombe" (passage 360 -> 0).
    Le premier tour, incomplet car on a pris le train en marche, est jeté.
    """
    min_coverage_deg: float = 340.0
    _angles: list[float] = field(default_factory=list)       # trigo, degrés
    _sensor_angles: list[float] = field(default_factory=list)
    _dist: list[int] = field(default_factory=list)
    _inten: list[int] = field(default_factory=list)
    _last: float | None = None
    _synced: bool = False
    last_speed_dps: int = 0

    def add(self, packet: Packet) -> dict | None:
        """Ajoute un paquet ; renvoie un scan complet (dict) quand un tour se termine."""
        done = None
        self.last_speed_dps = packet.speed_dps
        for a_s, a_m, d, i in zip(packet.sensor_angles(), packet.math_angles(),
                                  packet.distances, packet.intensities):
            if self._last is not None and a_s < self._last - 180.0:  # wrap 360 -> 0
                if self._synced and self._coverage() >= self.min_coverage_deg:
                    done = {"angle_deg": self._angles, "distance_mm": self._dist,
                            "intensity": self._inten, "speed_dps": packet.speed_dps}
                self._synced = True
                self._angles, self._sensor_angles, self._dist, self._inten = [], [], [], []
            self._last = a_s
            if self._synced:
                self._angles.append(a_m)
                self._sensor_angles.append(a_s)
                self._dist.append(d)
                self._inten.append(i)
        return done

    def _coverage(self) -> float:
        if not self._sensor_angles:
            return 0.0
        return self._sensor_angles[-1] - self._sensor_angles[0]
