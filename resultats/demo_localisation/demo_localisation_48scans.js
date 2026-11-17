"use strict";
// Même calcul que la démo de Lidar Lab (demo_localisation.js) pour CHACUN des 48 scans recalés du 10/11 :
// carte sans le scan ni les scans pris à moins de 15 cm, recherche globale sans pose de départ,
// refus (recouvrement 35 %, ambiguïté sur le recouvrement, contradiction 14,2 %).
const fs = require("fs");
const path = require("path");
const C = require("../exploration_scans_reels/commun.js");
const { LC } = C;
const d = C.loadSeance();
const filter = { minRange: 0.05, maxRange: 12, minIntensity: 0 }, res = 0.05; // réglages par défaut de l'interface
const rows = [];
for (const t of d.reg) {
  const ref = d.reg.filter((s) => s !== t && Math.hypot(s.pose[0] - t.pose[0], s.pose[1] - t.pose[1]) >= 0.15);
  const cells = LC.computeGridCells(ref, (s) => LC.filterScanPoints(s, filter), res), g = LC.cellsToGrid(cells, res);
  const t0 = Date.now();
  const opts = { minOverlap: 0.35, overlapAmbiguity: true };
  if (process.argv[2] !== "sans_contradiction") opts.contradictionCheck = { cells, res, maxFreeHit: 0.142 };
  const r = LC.locateScanOnGrid(LC.filterScanPoints(t, filter), g, opts);
  const p = r.pose, q = t.pose;
  const row = { scan: t.name, ok: !!r.ok, raison: r.reason || "", recouvrement: r.overlap == null ? null : +r.overlap.toFixed(3), exclus: d.reg.length - 1 - ref.length,
    ecart_cm: p ? +(Math.hypot(p[0] - q[0], p[1] - q[1]) * 100).toFixed(1) : null, ecart_deg: p ? +Math.abs(((((p[2] - q[2]) % 360) + 540) % 360) - 180).toFixed(1) : null, temps_ms: Date.now() - t0 };
  rows.push(row);
  console.log(row.scan, row.ok ? "accepté" : "refusé (" + row.raison + ")", row.ecart_cm, "cm", row.ecart_deg, "°", row.temps_ms, "ms");
}
const acc = rows.filter((r) => r.ok), far = acc.filter((r) => r.ecart_cm >= 30 || r.ecart_deg >= 5);
const bilan = { scans: rows.length, acceptes: acc.length, acceptes_a_moins_10cm_2deg: acc.filter((r) => r.ecart_cm < 10 && r.ecart_deg < 2).length, faux_positifs_30cm_5deg: far.length,
  refus: rows.filter((r) => !r.ok).map((r) => r.scan + " (" + r.raison + ")") };
console.log(JSON.stringify(bilan, null, 1));
const out = path.join(__dirname, "version_1");
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(path.join(out, process.argv[2] === "sans_contradiction" ? "demo_48scans_sans_contradiction.json" : "demo_48scans.json"), JSON.stringify({ bilan, rows }, null, 1));
