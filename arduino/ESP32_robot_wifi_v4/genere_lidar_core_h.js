// Copie lidar_core.js (calculs de Lidar Lab) dans lidar_core_js.h pour que l'ESP32 le serve au téléphone.
// À relancer après toute modification de lidar_core.js :   node genere_lidar_core_h.js [chemin/lidar_core.js]
const fs = require("fs"), path = require("path");
const src = process.argv[2] || "lidar_lab/lidar_core.js";
const js = fs.readFileSync(src, "utf8");
if (js.includes(')LCJS"')) throw new Error('lidar_core.js contient le délimiteur )LCJS"');
const header = [
  "// Généré par genere_lidar_core_h.js à partir de " + src.split(path.sep).join("/"),
  "// Ne pas modifier à la main : relancer « node genere_lidar_core_h.js » après une modification de lidar_core.js.",
  "#pragma once",
].join("\n");
fs.writeFileSync(path.join(__dirname, "lidar_core_js.h"), header + '\nconst char LIDAR_CORE_JS[] PROGMEM = R"LCJS(' + js + ')LCJS";\n');
console.log("lidar_core_js.h écrit (" + js.length + " caractères)");
