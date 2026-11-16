"use strict";
// Analyse AJOUTÉE après le résultat de la partie A (pas un critère du protocole) : les décisions « dangereuses »
// le restent-elles si l'on retire de la carte complète les points à moins de 30 cm de leur propre lidar
// (points que l'on soupçonne d'appartenir au robot lui-même) ?
const fs = require("fs");
const path = require("path");
const C = require("./commun.js");
const { LC } = C;
const out = process.argv[2] || path.join(__dirname, "version_1");
const rows = JSON.parse(fs.readFileSync(path.join(out, "partie_a.json"), "utf8"));
const d = C.loadSeance();
const per = d.reg.map((s) => LC.filterScanPoints(s, d.filter).filter((p) => Math.hypot(p.x, p.y) >= 0.3).map((p) => LC.transformed(p, s.pose)));
const res = [];
for (const r of rows.filter((x) => x.decision === "dangereuse")) {
  const pose = r.pose, h = ((pose[2] + r.turnDeg) * Math.PI) / 180, c = Math.cos(h), s = Math.sin(h);
  let n = 0;
  for (const w of per) for (const p of w) {
    const dx = p[0] - pose[0], dy = p[1] - pose[1], f = dx * c + dy * s, l = -dx * s + dy * c;
    if (Math.abs(l) <= 0.15 && f > 0 && f <= r.pas + 0.12) n++;
  }
  res.push({ k: r.k, scan: r.scan, points_avant: r.points_zone_balayee, points_sans_proches: n, reste_dangereuse: n >= 3 });
}
fs.writeFileSync(path.join(out, "partie_a_sans_points_proches.json"), JSON.stringify(res, null, 1));
for (const x of res) console.log(x.k, x.points_avant, "->", x.points_sans_proches, x.reste_dangereuse ? "RESTE" : "");
console.log("restent dangereuses :", res.filter((x) => x.reste_dangereuse).length, "sur", res.length);
