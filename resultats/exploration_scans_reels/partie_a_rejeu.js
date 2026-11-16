"use strict";
// Partie A (protocole écrit avant) : rejeu des décisions de l'explorateur sur les 48 scans réels du 10/11.
const fs = require("fs");
const path = require("path");
const C = require("./commun.js");
const { E } = C;
const out = process.argv[2] || path.join(__dirname, "version_1");
const o = { ...E.DEFAULTS };
const HALF_ROBOT = 0.15, FRONT = 0.12, MIN_PTS = 3;

const d = C.loadSeance();
const full = d.reg.flatMap((s) => C.worldPoints(s, d.filter)); // carte complète (points des 48 scans)
const rows = [];
for (let k = 0; k < d.reg.length; k++) {
  const sc = d.reg[k], pose = sc.pose;
  const list = d.reg.slice(0, k + 1);
  const grid = C.gridOf(list, d.all, d.settings, d.filter);
  const pts = (sc.pts || []).filter((p) => p.r >= o.rangeMin && p.r <= o.rangeMax);
  const t0 = Date.now();
  const ch = E.chooseDirection(pts, pose, grid, list.map((s) => s.pose), o);
  const row = { scan: sc.name, k: k + 1, pose, temps_ms: Date.now() - t0 };
  if (!ch) { rows.push({ ...row, mode: "aucune", decision: "terminé" }); continue; }
  const front = E.corridorClearance(pts, ch.turnDeg, o.halfWidth);
  const blocked = front < o.safety + ch.step;
  Object.assign(row, { mode: ch.mode, turnDeg: Math.round(ch.turnDeg), pas: +ch.step.toFixed(3), degagement_scan: +front.toFixed(3), bloque: blocked });
  if (!blocked && ch.step > 0) {
    const h = ((pose[2] + ch.turnDeg) * Math.PI) / 180, c = Math.cos(h), s = Math.sin(h);
    let n = 0, nearest = Infinity;
    for (const p of full) {
      const dx = p[0] - pose[0], dy = p[1] - pose[1], fwd = dx * c + dy * s, lat = -dx * s + dy * c;
      if (Math.abs(lat) <= HALF_ROBOT && fwd > 0) {
        if (fwd <= ch.step + FRONT) n++;
        nearest = Math.min(nearest, fwd);
      }
    }
    Object.assign(row, { points_zone_balayee: n, obstacle_carte_complete: +nearest.toFixed(3), decision: n >= MIN_PTS ? "dangereuse" : "sûre" });
  } else row.decision = blocked ? "pas bloqué (robot reste sur place)" : "pas nul";
  rows.push(row);
  console.log(row.k, row.scan, row.mode, row.turnDeg ?? "", row.pas ?? "", row.decision, row.points_zone_balayee ?? "", row.temps_ms + " ms");
}
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, "partie_a.json"), JSON.stringify(rows, null, 1));
const cnt = (f) => rows.filter(f).length;
console.log(`\nscans ${rows.length} | dangereuses ${cnt((r) => r.decision === "dangereuse")} | sûres ${cnt((r) => r.decision === "sûre")} | bloqués ${cnt((r) => r.bloque)} | aucune direction ${cnt((r) => r.mode === "aucune")}`);
