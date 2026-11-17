"use strict";
// Bouton « Localiser et construire la carte » (LidarCore.assembleSession) sur les deux séances réelles,
// avec l'étape 4 (réglages par défaut) et sans (contradiction: null). Comparaison avec les poses de l'Auto-SLAM
// (pas une vérité terrain). Aucune modification du code testé.
const fs = require("fs");
const path = require("path");
const C = require("../exploration_scans_reels/commun.js");
const { LC } = C;
const SEANCES = { "04/11": path.join(__dirname, "..", "..", "data", "robot_wifi", "seance_2026-11-04_17h42m59"), "10/11": C.SEANCE };
const res = {};
for (const [nom, dir] of Object.entries(SEANCES)) {
  const d = C.loadSeance(dir);
  const ref = Object.fromEntries(d.reg.map((s) => [s.name, s.pose]));
  for (const [cfg, opts] of [["avec étape 4", {}], ["sans étape 4", { contradiction: null }]]) {
    const scans = d.all.map((s) => ({ ...s, pose: [0, 0, 0] })); // les poses enregistrées ne sont PAS données à l'assemblage
    const t0 = Date.now();
    const end = LC.assembleSession(scans, opts);
    const R = end.resultats.filter((r) => r.pose);
    const cmp = R.filter((r) => ref[r.nom]).map((r) => { const q = ref[r.nom]; return [Math.hypot(r.pose[0] - q[0], r.pose[1] - q[1]), Math.abs(((r.pose[2] - q[2] + 540) % 360) - 180)]; });
    const out = { places: end.places, total: end.resultats.length, compares: cmp.length, a_moins_10cm_2deg: cmp.filter(([e, a]) => e < 0.1 && a < 2).length, a_plus_1m_ou_10deg: cmp.filter(([e, a]) => e >= 1 || a >= 10).length, refuses: end.resultats.filter((r) => r.statut === "refusé").length, duree_s: Math.round((Date.now() - t0) / 1000) };
    res[nom + " · " + cfg] = out;
    console.log(nom, cfg, JSON.stringify(out));
  }
}
fs.mkdirSync(path.join(__dirname, "version_1"), { recursive: true });
fs.writeFileSync(path.join(__dirname, "version_1", "assemblage_avec_sans_etape4.json"), JSON.stringify(res, null, 1));
