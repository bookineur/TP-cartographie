"use strict";
// Captures d'écran de l'interface de Lidar Lab (Edge sans fenêtre), séance chargée par le serveur.
// Usage : node captures_interface.js <url> <dossier_sortie>
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const URL_ = process.argv[2] || "http://localhost:8012/", OUT = process.argv[3];
const W = 1920, H = 1080, PORT = 9341;
const EDGE = ["C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe"].find((p) => fs.existsSync(p));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const edge = spawn(EDGE, ["--headless=new", "--disable-gpu", "--remote-debugging-port=" + PORT, "--user-data-dir=" + path.join(OUT, "_profil_edge"), `--window-size=${W},${H}`, "about:blank"], { stdio: "ignore" });
  let targets;
  for (let i = 0; i < 50; i++) { try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (targets.some((t) => t.type === "page")) break; } catch {} await wait(200); }
  const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0; const pending = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  const js = async (e) => (await send("Runtime.evaluate", { expression: e, awaitPromise: true, returnByValue: true })).result.result.value;
  const shot = async (name, clip) => { const r = await send("Page.captureScreenshot", { format: "png", ...(clip ? { clip: { ...clip, scale: 1 } } : {}) }); fs.writeFileSync(path.join(OUT, name), Buffer.from(r.result.data, "base64")); console.log("->", name); };
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: URL_ });
  for (let i = 0; i < 100; i++) { if (await js("typeof scans!=='undefined' && scans.filter(s=>s.mapRegistered).length>=40")) break; await wait(200); }
  await wait(1500);
  // 1. vue d'ensemble (haut de page)
  await js("window.scrollTo(0,0);document.getElementById('demoLoc').style.display='none';const f=document.getElementById('rwFolder');if(f)f.style.display='none';1");
  await wait(400); await shot("lidarlab_vue_ensemble.png");
  // 2-4. la carte avec les trois couches
  const rect = await js("(function(){const p=document.getElementById('plot');p.scrollIntoView({block:'center'});const r=p.getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()");
  await wait(400);
  const r2 = await js("(function(){const r=document.getElementById('plot').getBoundingClientRect();return [r.left+scrollX,r.top+scrollY,r.width,r.height]})()");
  const clip = { x: r2[0], y: r2[1], width: r2[2], height: r2[3] };
  for (const [layer, name] of [["points", "lidarlab_couche_scans.png"], ["grid", "lidarlab_couche_grid.png"], ["vector", "lidarlab_couche_vectorielle.png"]]) {
    const ok = await js(`(function(){const s=document.getElementById('layer');if(![...s.options].some(o=>o.value==='${layer}'))return [...s.options].map(o=>o.value).join(',');s.value='${layer}';s.dispatchEvent(new Event('change'));draw();return 'ok'})()`);
    if (ok !== "ok") console.log("couches disponibles :", ok);
    await wait(1200); await shot(name, clip);
  }
  // 5. panneau robot Wi-Fi (pilotage + exploration)
  const r3 = await js("(function(){const e=document.getElementById('rwExplore');if(!e)return null;const c=e.closest('section')||e.closest('.card');c.scrollIntoView({block:'start'});const r=c.getBoundingClientRect();return [r.left,r.top,r.width,Math.min(r.height,1040)]})()");
  await wait(500);
  if (r3) { const r4 = await js("(function(){const c=document.getElementById('rwExplore').closest('section')||document.getElementById('rwExplore').closest('.card');const r=c.getBoundingClientRect();return [r.left+scrollX,r.top+scrollY,r.width,Math.min(r.height,1040)]})()"); await shot("lidarlab_panneau_robot.png", { x: r4[0], y: r4[1], width: r4[2], height: r4[3] }); }
  ws.close(); edge.kill();
})();
