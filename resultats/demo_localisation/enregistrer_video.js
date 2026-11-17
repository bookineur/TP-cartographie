"use strict";
// Enregistre la vidéo de la démo « Où le robot a-t-il pris ce scan ? » dans un Edge sans fenêtre (headless),
// piloté par le protocole DevTools : seule la page de Lidar Lab est filmée.
// Usage : node enregistrer_video.js <url> <dossier_images> [capture|video] [nombre_de_tirages]
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const URL_ = process.argv[2] || "http://localhost:8012/";
const OUT = process.argv[3];
const MODE = process.argv[4] || "video";
const ROUNDS = +(process.argv[5] || 3);
const W = 1600, H = 900, PORT = 9339;
const EDGE = ["C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "C:/Program Files/Microsoft/Edge/Application/msedge.exe"].find((p) => fs.existsSync(p));
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const prof = path.join(OUT, "_profil_edge");
  const edge = spawn(EDGE, ["--headless=new", "--disable-gpu", "--remote-debugging-port=" + PORT, "--user-data-dir=" + prof, `--window-size=${W},${H}`, "about:blank"], { stdio: "ignore" });
  let targets;
  for (let i = 0; i < 50; i++) {
    try { targets = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); if (targets.some((t) => t.type === "page")) break; } catch {}
    await wait(200);
  }
  const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0;
  const pending = new Map(), frames = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    if (m.method === "Page.screencastFrame") {
      const f = path.join(OUT, `f_${String(frames.length).padStart(5, "0")}.jpg`);
      fs.writeFileSync(f, Buffer.from(m.params.data, "base64"));
      frames.push({ f: path.basename(f), t: m.params.metadata.timestamp });
      send("Page.screencastFrameAck", { sessionId: m.params.sessionId });
    }
  };
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; pending.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  const js = async (expr) => (await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true })).result.result.value;
  await send("Page.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  await send("Page.navigate", { url: URL_ });
  for (let i = 0; i < 100; i++) { if (await js("typeof scans!=='undefined' && scans.filter(s=>s.mapRegistered).length>=40 && !!window.demoLocalisation")) break; await wait(200); }
  // mise en page pour la vidéo : la carte en grand, bandeau de titre (vidéo seulement)
  await js(`(function(){document.getElementById('layer').value='grid';const p=document.getElementById('plot');p.scrollIntoView({block:'center'});
    const b=document.createElement('div');b.id='bandeau';b.style.cssText='position:fixed;left:0;right:0;top:0;z-index:60;background:#1F4E79;color:#fff;font:600 17px system-ui;padding:8px 14px';
    b.textContent='Lidar Lab · séance réelle du 10/11 (48 scans) · on prend un scan au hasard : le robot peut-il retrouver où il était ?';document.body.appendChild(b);draw();return 1})()`);
  await wait(800);
  const rect = await js(`(function(){const r=document.getElementById('plot').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()`);
  console.log("carte à l'écran :", rect.map(Math.round).join(" "));
  const flash = (idb) => js(`(function(){const e=document.getElementById('${idb}');e.style.outline='4px solid #f2c94c';setTimeout(()=>e.style.outline='',700);e.click();return 1})()`);
  const cadrer = () => js("(function(){const r=scans.filter(s=>s.mapRegistered);const x=r.reduce((a,s)=>a+s.pose[0],0)/r.length,y=r.reduce((a,s)=>a+s.pose[1],0)/r.length;demoLocalisation.frame(x,y,1.7);return 1})()");
  if (MODE === "capture") {
    await js("demoLocalisation.pick()");
    await cadrer();
    await js("demoLocalisation.locate()");
    const shot = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, "capture.png"), Buffer.from(shot.result.data, "base64"));
    console.log(await js("document.getElementById('demoStatus').innerText"));
    console.log(JSON.stringify(await js("(function(){const d=demoLocalisation.state();return {scan:d.target.name,pose:d.result.pose,rec:d.recorded}})()")));
  } else {
    await send("Page.startScreencast", { format: "jpeg", quality: 85, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
    await wait(2500);
    const log = [];
    for (let k = 0; k < ROUNDS; k++) {
      await flash("demoPick");
      await cadrer();
      await wait(3500);
      await flash("demoLocate");
      for (let i = 0; i < 200; i++) { if (await js("!!(demoLocalisation.state()&&demoLocalisation.state().result)")) break; await wait(100); }
      log.push(await js("document.getElementById('demoStatus').innerText"));
      await wait(6000);
      if (k < ROUNDS - 1) { await flash("demoReset"); await wait(1500); }
    }
    await send("Page.stopScreencast");
    await wait(300);
    fs.writeFileSync(path.join(OUT, "frames.json"), JSON.stringify(frames));
    fs.writeFileSync(path.join(OUT, "tirages.txt"), log.join("\n----\n"));
    console.log(frames.length, "images ;", log.join("\n----\n"));
  }
  ws.close();
  edge.kill();
})();
