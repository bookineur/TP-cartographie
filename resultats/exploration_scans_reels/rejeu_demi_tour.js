"use strict";
// D4 (données de conception) : rejeu des décisions sur les deux séances réelles avec le correctif « demi-tour ».
const fs = require("fs");
const path = require("path");
const C = require("./commun.js");
const { E } = C;
const out = process.argv[2] || path.join(__dirname, "version_3");
const o = { ...E.DEFAULTS };
const SEANCES = { "10/11": C.SEANCE, "04/11": path.join(__dirname, "..", "..", "data", "robot_wifi", "seance_2026-11-04_17h42m59") };
const res = {};
for (const [nom, dir] of Object.entries(SEANCES)) {
  const d = C.loadSeance(dir), rows = [];
  for (let k = 0; k < d.reg.length; k++) {
    const sc = d.reg[k], list = d.reg.slice(0, k + 1), g = C.gridOf(list, d.all, d.settings, d.filter);
    const pts = E.localPoints(sc, o), plan = E.planToFrontier(g, sc.pose, o);
    const ch = E.chooseDirection(pts, sc.pose, g, list.map((s) => s.pose), o);
    const r = { k: k + 1, scan: sc.name, chemin_existe: !!plan };
    if (!ch) r.decision = "terminé";
    else if (ch.blocked) r.decision = "arrêt : aucune direction libre";
    else {
      const front = E.corridorClearance(pts, ch.turnDeg, o.halfWidth);
      Object.assign(r, { decision: ch.mode, turnDeg: ch.turnDeg, pas: +ch.step.toFixed(3), degagement: +front.toFixed(3), pas_bloque: front < o.safety + ch.step });
    }
    rows.push(r);
  }
  const n = (f) => rows.filter(f).length;
  res[nom] = { scans: rows.length, arrets_a_tort: n((r) => r.chemin_existe && r.decision === "terminé"), demi_tours: n((r) => r.decision === "demi-tour"),
    demi_tours_bloques: n((r) => r.decision === "demi-tour" && r.pas_bloque), arrets_aucune_direction: n((r) => r.decision === "arrêt : aucune direction libre"),
    detail: rows.filter((r) => r.decision === "demi-tour" || r.decision.startsWith("arrêt") || r.decision === "terminé") };
  console.log(nom, JSON.stringify({ ...res[nom], detail: undefined }));
  for (const r of res[nom].detail) console.log("   ", r.k, r.scan, r.decision, r.turnDeg ?? "", r.pas ?? "", r.degagement ?? "");
}
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, "rejeu_demi_tour.json"), JSON.stringify(res, null, 1));
