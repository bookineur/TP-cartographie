// dépôt Lidar Lab : variable LIDAR_LAB, sinon dossier lidar_lab placé à côté de ce dépôt
const R = (process.env.LIDAR_LAB || require("path").join(__dirname, "..", "..", "..", "..", "..", "lidar_lab")) + "/";
const S = require(R + "tests/synthetic_ld06.js");
const { createSimRobot } = require(R + "tests/simulateur_robot.js");
const E = require(R + "serveur_robot/exploration.js");
const TWO = [S.seg(0, 0, 9, 0), S.seg(9, 0, 9, 3), S.seg(9, 3, 5, 3), S.seg(5, 3, 5, 4), S.seg(5, 4, 0, 4), S.seg(0, 4, 0, 0), S.seg(5, 0, 5, 1.2), S.seg(5, 2.2, 5, 3), ...S.rect(2.4, 1.6, 3.4, 2.2, "table"), ...S.rect(7.6, 0.3, 8.6, 0.8, "armoire")];
(async () => {
  const out = [];
  for (const seed of [11, 12, 13]) {
    const sim = createSimRobot({ walls: TWO, start: [1.5, 2, 0], seed });
    const ex = E.createExplorer(sim.io); ex.start(); await ex.wait();
    const t0 = sim.map[0].truth; let emax = 0;
    for (const m of sim.map) { const t = S.relativePose(t0, m.truth); emax = Math.max(emax, Math.hypot(m.pose[0]-t[0], m.pose[1]-t[1])); }
    const g = sim.io.state().grid;
    out.push({ seed, n: sim.map.length, collided: sim.st.collided, emax, travelled: sim.st.travelled, status: ex.status().status,
      truth: sim.map.map(m => m.truth), est: sim.map.map(m => m.pose), t0, grid: g });
  }
  out.walls = TWO;
  require("fs").writeFileSync(process.argv[2], JSON.stringify({ runs: out, walls: TWO.map(w => [w.a, w.b]) }));
  for (const r of out) console.log(r.seed, r.n, r.collided, r.emax.toFixed(3), r.travelled.toFixed(1), r.status);
})();
