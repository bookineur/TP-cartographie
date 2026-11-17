"use strict";
// Diagnostic (aucune modification du code) : part de points « dans du vide confirmé » à la pose enregistrée,
// pour chaque scan des deux séances réelles, carte sans le scan ni les scans pris à moins de 15 cm.
// Découpage par distance au lidar.
const fs = require("fs");
const path = require("path");
const C = require("../exploration_scans_reels/commun.js");
const { LC } = C;
const filter = { minRange: 0.05, maxRange: 12, minIntensity: 0 }, res = 0.05;
const BINS = [[0, 0.3], [0.3, 1], [1, 3], [3, 6], [6, 13]];
const SEANCES = { "04/11": path.join(__dirname, "..", "..", "data", "robot_wifi", "seance_2026-11-04_17h42m59"), "10/11": C.SEANCE };
const out = {};
for (const [nom, dir] of Object.entries(SEANCES)) {
  const d = C.loadSeance(dir), rows = [];
  for (const t of d.reg) {
    const ref = d.reg.filter((s) => s !== t && Math.hypot(s.pose[0] - t.pose[0], s.pose[1] - t.pose[1]) >= 0.15);
    const cells = LC.computeGridCells(ref, (s) => LC.filterScanPoints(s, filter), res);
    const pts = LC.filterScanPoints(t, filter);
    const tot = LC.freeSpaceConsistency(pts, t.pose, cells, res).freeHit;
    const parBin = BINS.map(([a, b]) => {
      const sub = pts.filter((p) => p.r >= a && p.r < b);
      return Math.round(LC.freeSpaceConsistency(sub, t.pose, cells, res).freeHit * sub.length); // nb de points dans du vide
    });
    rows.push({ scan: t.name, points: pts.length, part_vide: +tot.toFixed(4), vide_par_distance: parBin });
  }
  const v = rows.map((r) => r.part_vide).sort((a, b) => a - b);
  const sum = BINS.map((_, i) => rows.reduce((a, r) => a + r.vide_par_distance[i], 0));
  out[nom] = { scans: rows.length, mediane: v[v.length >> 1], p90: v[Math.floor(v.length * 0.9)], max: v[v.length - 1], au_dessus_14_2: rows.filter((r) => r.part_vide > 0.142).length, points_vides_par_distance: Object.fromEntries(BINS.map((b, i) => [b.join("-") + " m", sum[i]])), rows };
  console.log(nom, JSON.stringify({ ...out[nom], rows: undefined }));
}
fs.mkdirSync(path.join(__dirname, "version_1"), { recursive: true });
fs.writeFileSync(path.join(__dirname, "version_1", "diagnostic.json"), JSON.stringify(out, null, 1));
