"use strict";
// Diagnostic (aucune modification) : pour les points « dans du vide confirmé », distance au mur (cellule occupée)
// le plus proche de la carte. À la pose enregistrée (bonne pose ?) et, pour comparer, à une pose FAUSSE
// (même position tournée de 90°, cas réel de faux positif du 04/11).
const path = require("path");
const C = require("../exploration_scans_reels/commun.js");
const { LC } = C;
const filter = { minRange: 0.05, maxRange: 12, minIntensity: 0 }, res = 0.05;
const SEANCES = { "04/11": path.join(__dirname, "..", "..", "data", "robot_wifi", "seance_2026-11-04_17h42m59"), "10/11": C.SEANCE };
const OCC = 0.85; // log-odds > 0 : occupé (même convention que cellsToGrid : on prend les cellules à valeur positive)
function freePointsDist(pts, pose, cells) {
  const occ = [];
  for (const [k, v] of cells) if (v > 0) occ.push(k.split(",").map(Number));
  const occSet = new Set(occ.map((c) => c.join(",")));
  const dists = [];
  for (const p of pts) {
    const r = LC.freeSpaceConsistency([p], pose, cells, res);
    if (r.freeHit < 1) continue;
    const w = LC.transformed(p, pose), cx = Math.floor(w[0] / res), cy = Math.floor(w[1] / res);
    let best = 99;
    for (let R = 0; R <= 30 && best === 99; R++) // anneaux de cellules jusqu'à 1,5 m
      for (let dx = -R; dx <= R; dx++) for (let dy = -R; dy <= R; dy++) if (Math.max(Math.abs(dx), Math.abs(dy)) === R && occSet.has(cx + dx + "," + (cy + dy))) best = Math.min(best, Math.hypot(dx, dy) * res);
    dists.push(best);
  }
  return dists;
}
const q = (v, f) => (v.length ? v[Math.min(v.length - 1, Math.floor(v.length * f))] : NaN);
for (const [nom, dir] of Object.entries(SEANCES)) {
  const d = C.loadSeance(dir);
  const bonne = [], fausse = [];
  for (const t of d.reg) {
    const ref = d.reg.filter((s) => s !== t && Math.hypot(s.pose[0] - t.pose[0], s.pose[1] - t.pose[1]) >= 0.15);
    const cells = LC.computeGridCells(ref, (s) => LC.filterScanPoints(s, filter), res);
    const pts = LC.filterScanPoints(t, filter);
    bonne.push(...freePointsDist(pts, t.pose, cells));
    fausse.push(...freePointsDist(pts, [t.pose[0], t.pose[1], t.pose[2] + 90], cells));
  }
  for (const [lab, v] of [["pose enregistrée", bonne], ["pose tournée de 90°", fausse]]) {
    v.sort((a, b) => a - b);
    const part = (lim) => (v.filter((x) => x <= lim).length / v.length * 100).toFixed(0) + " %";
    console.log(nom, lab, ": points dans le vide", v.length, "| distance au mur : médiane", q(v, 0.5).toFixed(2), "m, p90", q(v, 0.9).toFixed(2), "m | à ≤ 0,25 m d'un mur :", part(0.25), "| ≤ 0,40 m :", part(0.4));
  }
}
