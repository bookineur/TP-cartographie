import numpy as np
import pytest

from carto.gridmap import OccupancyGrid, bresenham
from carto.scan import Pose, Scan, load_scan_file, save_scan_csv
from carto.simulate import TRUE_POSES, raycast
from carto.vectormap import VectorMap
from ld06.protocol import CRC_TABLE, Packet, PacketParser, ScanAssembler, crc8, decode_packet, encode_packet

# Exemple de la doc "LD06 Development manual" §3.3
DOC_PACKET = bytes.fromhex(
    "54 2C 68 08 AB 7E E0 00 E4 DC 00 E2 D9 00 E5 D5 00 E3 D3 00 E4 D0 00 E9 CD 00 E4 CA 00 E2 C7 00 E9 "
    "C5 00 E5 C2 00 E5 C0 00 E5 BE 82 3A 1A 50".replace(" ", ""))


def test_crc_table_matches_library():
    assert CRC_TABLE[:8] == [0x00, 0x4D, 0x9A, 0xD7, 0x79, 0x34, 0xE3, 0xAE]
    assert CRC_TABLE[-3:] == [0x32, 0xE5, 0xA8]


def test_doc_packet():
    assert len(DOC_PACKET) == 47
    assert crc8(DOC_PACKET[:-1]) == DOC_PACKET[-1] == 0x50
    p = decode_packet(DOC_PACKET)
    assert p.speed_dps == 2152
    assert p.start_angle == pytest.approx(324.27)
    assert p.end_angle == pytest.approx(334.70)
    assert p.distances[0] == 224 and p.intensities[0] == 228
    assert p.distances[1] == 220 and p.intensities[1] == 226
    a = p.sensor_angles()
    assert a[0] == pytest.approx(324.27) and a[-1] == pytest.approx(334.70)


def test_parser_resync_and_crc():
    corrupted = bytearray(DOC_PACKET)
    corrupted[10] ^= 0xFF
    stream = b"\x54\x00\x12" + bytes(corrupted) + b"\x54" + DOC_PACKET + DOC_PACKET[:20]
    parser = PacketParser()
    pkts = parser.feed(stream[:30]) + parser.feed(stream[30:])
    assert len(pkts) == 1 and parser.crc_failures == 1
    assert len(parser.feed(DOC_PACKET[20:])) == 1  # paquet coupé entre deux lectures


def test_angle_wrap_and_assembler():
    pk = Packet(3600, 355.0, 6.0, [1000] * 12, [200] * 12, 0)
    a = pk.sensor_angles()
    assert a[0] == pytest.approx(355) and a[-1] == pytest.approx(6) and a[6] == pytest.approx(1)
    # 3 tours de 38 paquets de 12 points (~456 pts/tour)
    asm, scans = ScanAssembler(), []
    step = 360 / 456
    for k in range(38 * 3 + 1):
        s = (k * 12 * step) % 360
        raw = encode_packet(Packet(3600, s, (s + 11 * step) % 360, [1500] * 12, [200] * 12, k))
        for p in PacketParser().feed(raw):
            out = asm.add(p)
            if out:
                scans.append(out)
    assert len(scans) == 2 and all(440 <= len(s["angle_deg"]) <= 460 for s in scans)


def test_csv_roundtrip(tmp_path):
    f = tmp_path / "s.csv"
    save_scan_csv(f, [0, 90, 180], [1000, 2000, 0], [200, 100, 0], meta={"a": 1})
    (s,) = load_scan_file(f)
    assert len(s) == 3 and s.meta["a"] == "1"
    assert np.allclose(s.filtered().local_xy(), [[1, 0], [0, 2]], atol=1e-9)
    # format printScanCSV de la librairie, 2 scans
    g = tmp_path / "lib.csv"
    g.write_text("N,Angle(°),Distance(mm),Intensity,x(mm),y(mm)\n0,0.50,623,12,622,5\n1,1.50,624,11,623,16\n\n"
                 "0,0.40,700,12,0,0\n", encoding="utf-8")
    scans = load_scan_file(g)
    assert len(scans) == 2 and len(scans[0]) == 2 and scans[1].ranges[0] == pytest.approx(0.7)


def test_pose_transform():
    p = Pose(1, 2, np.pi / 2)
    assert np.allclose(p.transform(np.array([[1.0, 0.0]])), [[1, 3]])


def test_bresenham():
    assert bresenham(0, 0, 3, 1) == [(0, 0), (1, 0), (2, 1), (3, 1)]
    assert bresenham(2, 2, 2, 2) == [(2, 2)]
    assert bresenham(0, 0, -2, -2) == [(0, 0), (-1, -1), (-2, -2)]


def _sim_scan(name, pose):
    ang = np.radians(np.arange(0, 360, 0.8))
    return Scan(name, ang, raycast(pose, ang), np.full(len(ang), 200.0)).filtered()


def test_grid_from_scan_and_update():
    p1, p2 = TRUE_POSES["pos1"], TRUE_POSES["pos3"]
    g = OccupancyGrid.from_scan(_sim_scan("a", p1), p1, 0.05)
    ix, iy = g.world_to_cell([p1.x, p1.y])[0]
    assert g.logodds[iy, ix] == pytest.approx(g.l_free)   # traversée 1 fois (pas 450)
    wx, wy = g.world_to_cell([1.5, 0.01])[0]               # mur y = 0
    assert g.logodds[wy, wx] == pytest.approx(g.l_occ)
    assert (g.classify() == 1).sum() > 100
    shape0 = g.shape
    g.update(_sim_scan("b", p2), p2)
    assert g.n_scans == 2 and g.shape[0] >= shape0[0] and g.shape[1] >= shape0[1]
    # zone vue par les deux scans : libre confirmé (2 x l_free -> p < 0.35)
    cx, cy = g.world_to_cell([3.6, 2.4])[0]  # vue de pos1 à travers la porte, et de pos3
    assert g.logodds[cy, cx] == pytest.approx(2 * g.l_free) and g.classify()[cy, cx] == 0


def test_grid_grows_and_keeps_alignment():
    g = OccupancyGrid(0.1, (0, 0), (10, 10))
    g.logodds[5, 5] = 2.0
    c = g.cell_center(5, 5)
    g.ensure_contains(-3, -2, 0.5, 0.5, margin=0)
    ix, iy = g.world_to_cell(c)[0]
    assert g.logodds[iy, ix] == 2.0


def test_vector_map_finds_walls():
    vm = VectorMap()
    for name in ("pos1", "pos2", "pos3", "pos4"):
        vm.add_scan(_sim_scan(name, TRUE_POSES[name]), TRUE_POSES[name])
    long_ = [s for s in vm.segments if s.length > 2.5]
    assert len(long_) >= 4
    assert any(abs(s.p1[1]) < 0.05 and abs(s.p2[1]) < 0.05 and s.length > 6 for s in vm.segments)  # mur y=0
