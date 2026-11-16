"use strict";
// Outils communs : lecture de la séance réelle du 10/11 avec les fonctions de Lidar Lab (lidar_core.js).
const fs = require("fs");
const path = require("path");
const CODEX = process.env.CODEX_LIDAR || "lidar_lab";
const LC = require(path.join(CODEX, "lidar_core.js"));
const E = require(path.join(CODEX, "serveur_robot", "exploration.js"));
const DATA = path.join(__dirname, "..", "..", "data", "mesures_phase19_2026-11-09");
const SEANCE = path.join(DATA, "capture", "seance_2026-11-09_13h06m10");

function loadSeance(dir = SEANCE) {
  const s = JSON.parse(fs.readFileSync(path.join(dir, "seance.json"), "utf8"));
  const f = { minRange: s.settings.rmin, maxRange: s.settings.rmax, minIntensity: s.settings.imin };
  const all = s.scans.map((e) => {
    const sc = LC.parseCsv(fs.readFileSync(path.join(dir, e.name), "utf8"), e.name);
    sc.pose = e.pose;
    sc.mapRegistered = sc.visible = !!e.reg;
    return sc;
  });
  return { settings: s.settings, filter: f, all, reg: all.filter((x) => x.mapRegistered) };
}
// même calcul de carte que le serveur (currentGrid) pour une liste de scans recalés
function gridOf(list, all, settings, filter) {
  const cells = LC.computeGridCells(list, (s) => LC.temporalFilter(s, all, { enabled: !!settings.tfilt, tolerance: 0.18, filter }), settings.gres);
  return LC.cellsToGrid(cells, settings.gres);
}
function worldPoints(sc, filter) {
  return LC.filterScanPoints(sc, filter).map((p) => LC.transformed(p, sc.pose)); // [x, y] repère carte
}
function segmentsCsv(file) {
  return fs.readFileSync(file, "utf8").trim().split(/\r?\n/).slice(1).map((l) => l.split(",").map(Number)).map((v) => ({ a: [v[0], v[1]], b: [v[2], v[3]], n: v[5] }));
}
function distSeg(x, y, s) {
  const vx = s.b[0] - s.a[0], vy = s.b[1] - s.a[1], L2 = vx * vx + vy * vy || 1e-12;
  const t = Math.max(0, Math.min(1, ((x - s.a[0]) * vx + (y - s.a[1]) * vy) / L2));
  return Math.hypot(x - s.a[0] - t * vx, y - s.a[1] - t * vy);
}
module.exports = { LC, E, DATA, SEANCE, loadSeance, gridOf, worldPoints, segmentsCsv, distSeg };
