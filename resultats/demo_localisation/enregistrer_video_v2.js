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
const W = 1920, H = 1080, PORT = 9339;
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
  // mise en page pour la vidéo : la carte occupe l'écran, le panneau à droite, un bandeau annonce chaque étape
  await js(`(function(){document.getElementById('layer').value='grid';
    const st=document.createElement('style');st.textContent='#plot{position:fixed!important;left:0;top:56px;width:calc(100vw - 400px)!important;height:calc(100vh - 56px)!important;z-index:40;background:#0c1118}#demoLoc{top:70px!important;bottom:auto!important;right:14px!important;width:370px!important;font-size:15px!important}body{overflow:hidden}';document.head.appendChild(st);
    const b=document.createElement('div');b.id='bandeau';b.style.cssText='position:fixed;left:0;right:0;top:0;height:56px;z-index:60;background:#1F4E79;color:#fff;font:600 21px system-ui;padding:14px 18px;box-sizing:border-box';
    document.body.appendChild(b);draw();return 1})()`);
  const titre = (t) => js("(function(){document.getElementById('bandeau').textContent=" + JSON.stringify(t) + ";return 1})()");
  await titre("Lidar Lab · séance réelle du 10/11 (48 scans recalés) · la grid map de la salle");
  await wait(800);
  const rect = await js(`(function(){const r=document.getElementById('plot').getBoundingClientRect();return [r.left,r.top,r.width,r.height]})()`);
  console.log("carte à l'écran :", rect.map(Math.round).join(" "));
  const flash = (idb) => js(`(function(){const e=document.getElementById('${idb}');e.style.outline='4px solid #f2c94c';setTimeout(()=>e.style.outline='',700);e.click();return 1})()`);
  const cadrer = () => js("(function(){const r=scans.filter(s=>s.mapRegistered);const x=r.reduce((a,s)=>a+s.pose[0],0)/r.length,y=r.reduce((a,s)=>a+s.pose[1],0)/r.length;demoLocalisation.frame(x,y,1.45);return 1})()");
  if (MODE === "capture") {
    await js("demoLocalisation.pick()");
    await cadrer();
    await js("demoLocalisation.locate()");
    const shot = await send("Page.captureScreenshot", { format: "png" });
    fs.writeFileSync(path.join(OUT, "capture.png"), Buffer.from(shot.result.data, "base64"));
    console.log(await js("document.getElementById('demoStatus').innerText"));
    console.log(JSON.stringify(await js("(function(){const d=demoLocalisation.state();return {scan:d.target.name,pose:d.result.pose,rec:d.recorded}})()")));
  } else {
    // captures d'écran régulières (le flux « screencast » ne filme que la partie visible de la fenêtre sans affichage)
    let filming = true;
    const filmer = (async () => {
      while (filming) {
        const t = Date.now() / 1000;
        const shot = await send("Page.captureScreenshot", { format: "jpeg", quality: 88 });
        const f = path.join(OUT, `f_${String(frames.length).padStart(5, "0")}.jpg`);
        fs.writeFileSync(f, Buffer.from(shot.result.data, "base64"));
        frames.push({ f: path.basename(f), t });
        await wait(150);
      }
    })();
    await wait(3500);
    const log = [];
    for (let k = 0; k < ROUNDS; k++) {
      await titre(`Essai ${k + 1}/${ROUNDS} · Étape 1 : on tire un scan au hasard. Il est retiré de la carte ; en haut à gauche, ce que voyait le robot`);
      await flash("demoPick");
      await cadrer();
      await wait(6000);
      await titre(`Essai ${k + 1}/${ROUNDS} · Étape 2 : localisation sur toute la grid map, sur 360°, sans position de départ…`);
      await flash("demoLocate");
      for (let i = 0; i < 300; i++) { if (await js("!!(demoLocalisation.state()&&demoLocalisation.state().result)")) break; await wait(100); }
      const r = await js("(function(){const d=demoLocalisation.state(),p=d.result.pose,q=d.recorded;if(!d.result.ok)return 'refusé';return [p[0].toFixed(2),p[1].toFixed(2),Math.hypot(p[0]-q[0],p[1]-q[1])*100]})()");
      await titre(r === "refusé" ? `Essai ${k + 1}/${ROUNDS} · Résultat : position refusée (le robot préfère ne pas choisir)` : `Essai ${k + 1}/${ROUNDS} · Résultat : le robot était en x = ${r[0]} m, y = ${r[1]} m · écart avec l'Auto-SLAM : ${r[2].toFixed(1)} cm`);
      log.push(await js("document.getElementById('demoStatus').innerText"));
      await wait(10000);
      if (k < ROUNDS - 1) { await flash("demoReset"); await titre("On recommence avec un autre scan"); await wait(2000); }
    }
    filming = false;
    await filmer;
    await wait(300);
    fs.writeFileSync(path.join(OUT, "frames.json"), JSON.stringify(frames));
    fs.writeFileSync(path.join(OUT, "tirages.txt"), log.join("\n----\n"));
    console.log(frames.length, "images ;", log.join("\n----\n"));
  }
  ws.close();
  edge.kill();
})();
