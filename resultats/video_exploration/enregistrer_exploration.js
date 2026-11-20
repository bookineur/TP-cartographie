"use strict";
// Enregistre, pas à pas, une exploration automatique : vrai code de Lidar Lab (serveur_robot/exploration.js)
// pilotant un robot SIMULÉ (tests/simulateur_robot.js) dans la salle réelle du 10/11 reconstruite à partir de sa
// carte vectorielle brute (166 segments). Même départ et même graine que la partie B de resultats/exploration_scans_reels.
// Sortie : un fichier JSON par étape (grille, poses, scan, cible), lu par images.py.
const fs = require("fs");
const path = require("path");
const C = require("../exploration_scans_reels/commun.js");
const LAB = process.env.LIDAR_LAB || path.join(__dirname, "..", "..", "..", "lidar_lab");
const S = require(path.join(LAB, "tests", "synthetic_ld06.js"));
const { createSimRobot } = require(path.join(LAB, "tests", "simulateur_robot.js"));
const E = require(path.join(LAB, "serveur_robot", "exploration.js"));
const LC = require(path.join(LAB, "lidar_core.js"));
const out = process.argv[2] || path.join(__dirname, "version_1", "etapes");
fs.mkdirSync(out, { recursive: true });

const d = C.loadSeance();
const segs = C.segmentsCsv(path.join(C.DATA, "carte_autoslam_v1", "segments.csv"));
const walls = segs.map((s) => S.seg(s.a[0], s.a[1], s.b[0], s.b[1]));
const ref = C.gridOf(d.reg, d.all, d.settings, d.filter);
const freeRef = [];
for (let row = 0; row < ref.height; row++)
  for (let col = 0; col < ref.width; col++)
    if (ref.rows[row][col] === 0) freeRef.push([ref.origin[0] + (col + 0.5) * ref.resolution, ref.origin[1] + (ref.height - 1 - row + 0.5) * ref.resolution]);
const start = d.reg[0].pose.slice();
const sim = createSimRobot({ walls, start, seed: 1 });
const enc = (g) => g.rows.map((r) => r.map((v) => (v === 1 ? "#" : v === 0 ? "." : " ")).join("")).join("\n");
let k = 0, pending = null, lastTurn = 0;
const io = {
  ...sim.io,
  scan: async () => {
    const st = sim.io.state();
    if (st.grid && !pending) {
      const plan = E.planToFrontier(st.grid, st.pose, E.DEFAULTS);
      pending = { cible: plan ? plan.waypoint : null, longueur_chemin: plan ? plan.length : null };
    }
    return sim.io.scan();
  },
  turn: async (deg) => ((lastTurn = deg), sim.io.turn(deg)),
  capture: async () => {
    const r = await sim.io.capture();
    const st = sim.io.state(), m = sim.map[sim.map.length - 1], t0 = sim.map[0].truth;
    const g = st.grid;
    let known = 0;
    for (const [x, y] of freeRef) {
      const p = S.relativePose(t0, [x, y, 0]), c = Math.floor((p[0] - g.origin[0]) / g.resolution), row = g.height - 1 - Math.floor((p[1] - g.origin[1]) / g.resolution);
      if (c >= 0 && c < g.width && row >= 0 && row < g.height && g.rows[row][c] !== -1) known++;
    }
    const pts = LC.filterScanPoints(m, sim.filter).map((q) => LC.transformed(q, m.pose));
    const vrai = S.relativePose(t0, m.truth);
    fs.writeFileSync(path.join(out, `etape_${String(k).padStart(4, "0")}.json`), JSON.stringify({
      k, ok: r.ok, pose: m.pose, vrai, scan: pts.filter((_, i) => i % 2 === 0).map((q) => [+q[0].toFixed(3), +q[1].toFixed(3)]),
      grille: { origine: g.origin, res: g.resolution, largeur: g.width, hauteur: g.height, cellules: enc(g) },
      cible: pending ? pending.cible : null, longueur_chemin: pending ? pending.longueur_chemin : null, rotation: lastTurn,
      couverture: +(known / freeRef.length).toFixed(4), distance: +sim.st.travelled.toFixed(2), statut: ex.status().status }));
    k++; pending = null; lastTurn = 0;
    return r;
  },
};
const ex = E.createExplorer(io, { maxSteps: 200, maxMs: 60 * 60 * 1000 });
// murs réels dans le repère de la carte (repère du premier scan)
(async () => {
  ex.start();
  await ex.wait();
  const t0 = sim.map[0].truth;
  const mursCarte = segs.map((s) => [S.relativePose(t0, [s.a[0], s.a[1], 0]).slice(0, 2), S.relativePose(t0, [s.b[0], s.b[1], 0]).slice(0, 2)]);
  let emax = 0;
  for (const m of sim.map) { const t = S.relativePose(t0, m.truth); emax = Math.max(emax, Math.hypot(m.pose[0] - t[0], m.pose[1] - t[1])); }
  fs.writeFileSync(path.join(out, "..", "bilan.json"), JSON.stringify({ etapes: k, statut: ex.status().status, collision: sim.st.collided, distance_m: +sim.st.travelled.toFixed(1),
    erreur_pose_max_m: +emax.toFixed(3), murs_reels_repere_carte: mursCarte, depart: start, graine: 1 }, null, 1));
  console.log("étapes", k, "|", ex.status().status, "| collision", sim.st.collided, "| distance", sim.st.travelled.toFixed(1), "m | erreur max", (emax * 100).toFixed(1), "cm");
})();
