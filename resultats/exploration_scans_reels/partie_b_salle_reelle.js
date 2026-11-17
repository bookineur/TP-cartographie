"use strict";
// Partie B (protocole écrit avant) : exploration SIMULÉE dans la salle réelle reconstruite (carte vectorielle brute du 10/11).
const fs = require("fs");
const path = require("path");
const C = require("./commun.js");
// dépôt Lidar Lab : variable LIDAR_LAB, sinon dossier lidar_lab placé à côté de ce dépôt
const CODEX = process.env.LIDAR_LAB || path.join(__dirname, "..", "..", "..", "lidar_lab");
const S = require(path.join(CODEX, "tests", "synthetic_ld06.js"));
const { createSimRobot } = require(path.join(CODEX, "tests", "simulateur_robot.js"));
const { E } = C;
const out = process.argv[2] || path.join(__dirname, "version_1");
const which = process.argv[3] ? process.argv[3].split(",").map(Number) : [0, 1, 2];

const d = C.loadSeance();
const walls = C.segmentsCsv(path.join(C.DATA, "carte_autoslam_v1", "segments.csv")).map((s) => S.seg(s.a[0], s.a[1], s.b[0], s.b[1]));
const ref = C.gridOf(d.reg, d.all, d.settings, d.filter); // surface de référence : cellules libres de la carte réelle
const freeRef = [];
for (let row = 0; row < ref.height; row++)
  for (let col = 0; col < ref.width; col++)
    if (ref.rows[row][col] === 0) freeRef.push([ref.origin[0] + (col + 0.5) * ref.resolution, ref.origin[1] + (ref.height - 1 - row + 0.5) * ref.resolution]);
const STARTS = [{ scan: 1, seed: 1 }, { scan: 20, seed: 2 }, { scan: 40, seed: 3 }];

(async () => {
  const res = [];
  for (const i of which) {
    const st = STARTS[i], start = d.reg[st.scan - 1].pose.slice();
    const t0r = Date.now();
    const sim = createSimRobot({ walls, start, seed: st.seed });
    const ex = E.createExplorer(sim.io, { maxSteps: 200, maxMs: 60 * 60 * 1000 });
    const timer = setInterval(() => console.log(`  départ scan ${st.scan} : pas ${ex.status().step} — ${ex.status().status}`), 30000);
    ex.start();
    await ex.wait();
    clearInterval(timer);
    const t0 = sim.map[0].truth;
    let emax = 0, amax = 0;
    for (const m of sim.map) {
      const t = S.relativePose(t0, m.truth);
      emax = Math.max(emax, Math.hypot(m.pose[0] - t[0], m.pose[1] - t[1]));
      amax = Math.max(amax, Math.abs(((m.pose[2] - t[2] + 540) % 360) - 180));
    }
    const g = sim.io.state().grid;
    let known = 0;
    for (const [x, y] of freeRef) {
      const p = S.relativePose(t0, [x, y, 0]),
        c = Math.floor((p[0] - g.origin[0]) / g.resolution),
        row = g.height - 1 - Math.floor((p[1] - g.origin[1]) / g.resolution);
      if (c >= 0 && c < g.width && row >= 0 && row < g.height && g.rows[row][c] !== -1) known++;
    }
    const r = { depart_scan: st.scan, graine: st.seed, pose_depart: start, pas: ex.status().step, scans: sim.map.length, distance_m: +sim.st.travelled.toFixed(2),
      collision: sim.st.collided, erreur_pos_max_m: +emax.toFixed(3), erreur_angle_max_deg: +amax.toFixed(2), couverture: +(known / freeRef.length).toFixed(3),
      statut: ex.status().status, duree_calcul_s: Math.round((Date.now() - t0r) / 1000),
      trajet_vrai: sim.map.map((m) => m.truth.map((v) => +v.toFixed(3))), poses_recalees: sim.map.map((m) => m.pose.map((v) => +v.toFixed(3))) };
    res.push(r);
    console.log(JSON.stringify({ ...r, trajet_vrai: undefined, poses_recalees: undefined }));
    fs.mkdirSync(out, { recursive: true });
    fs.writeFileSync(path.join(out, `partie_b_depart${st.scan}.json`), JSON.stringify(r, null, 1));
  }
})();
