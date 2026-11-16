"use strict";
// Validation du correctif selfMask sur la séance réelle du 04/11 (protocole version_2/PROTOCOLE_correctif.md).
const fs = require("fs");
const path = require("path");
const C = require("./commun.js");
const { E } = C;
const out = process.argv[2] || path.join(__dirname, "version_2");
const dir = path.join(__dirname, "..", "..", "data", "robot_wifi", "seance_2026-11-04_17h42m59");
const d = C.loadSeance(dir);
const withMask = { ...E.DEFAULTS }, without = { ...E.DEFAULTS, selfMask: null };
const rows = [];
let nearAll = 0, nearIn = 0;
for (let k = 0; k < d.reg.length; k++) {
  const sc = d.reg[k], list = d.reg.slice(0, k + 1), g = C.gridOf(list, d.all, d.settings, d.filter), vis = list.map((s) => s.pose);
  const pts = sc.pts || [];
  for (const p of pts) if (p.r < 0.2) { nearAll++; if (E.isSelfPoint(p, withMask.selfMask)) nearIn++; }
  const kept = pts.filter((p) => p.r >= withMask.rangeMin && p.r <= withMask.rangeMax);
  const ignored = kept.filter((p) => E.isSelfPoint(p, withMask.selfMask)).length;
  const plan = E.planToFrontier(g, sc.pose, withMask);
  const a = E.chooseDirection(E.localPoints(sc, without), sc.pose, g, vis, without);
  const b = E.chooseDirection(E.localPoints(sc, withMask), sc.pose, g, vis, withMask);
  rows.push({ k: k + 1, scan: sc.name, chemin_existe: !!plan, sans_masque: a ? a.mode : "aucune", avec_masque: b ? b.mode : "aucune",
    points: kept.length, ignores: ignored, part_ignoree: +(ignored / Math.max(1, kept.length)).toFixed(4) });
}
const wrong = (key) => rows.filter((r) => r.chemin_existe && r[key] === "aucune").length;
const maxPart = Math.max(...rows.map((r) => r.part_ignoree));
const v1 = wrong("avec_masque"), v2 = nearAll < 20 ? null : nearIn / nearAll;
const res = { seance: "04/11", scans: rows.length, arrets_a_tort_avant: wrong("sans_masque"), arrets_a_tort_apres: v1,
  points_proches_total: nearAll, points_proches_dans_secteur: nearIn, V2_part_secteur: v2 == null ? "non mesurable" : +v2.toFixed(3),
  V3_part_ignoree_max: maxPart,
  criteres: { V1: v1 === 0 ? "atteint" : "non atteint", V2: v2 == null ? "non mesurable" : v2 >= 0.8 ? "atteint" : "non atteint", V3: maxPart < 0.02 ? "atteint" : "non atteint" } };
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, "validation_0411.json"), JSON.stringify({ ...res, par_scan: rows }, null, 1));
console.log(JSON.stringify(res, null, 1));
for (const r of rows) if (r.sans_masque !== r.avec_masque) console.log("  changé :", r.k, r.scan, r.sans_masque, "->", r.avec_masque, "ignorés", r.ignores);
