<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Элла — HUD</title>
<meta name="theme-color" content="#030a1a">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Элла">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="icon" href="/icon-192.png">
<link rel="apple-touch-icon" href="/icon-192.png">
<style>
:root{--bg:#030a1a;--panel:#07142e;--sap:#0f52ba;--glow:#4aa8ff;--txt:#d6eaff;--dim:#7c98c0;--bad:#ff6b6b;--ok:#4be3b0}
*{box-sizing:border-box}
html,body{height:100%;margin:0}
body{background:radial-gradient(circle at 50% 30%,#0a2150 0%,var(--bg) 65%);color:var(--txt);
 font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;display:flex;flex-direction:column;
 padding:env(safe-area-inset-top,0) 0 env(safe-area-inset-bottom,0)}
header{display:flex;justify-content:space-between;align-items:center;padding:14px 18px;border-bottom:1px solid #123a7a}
h1{font-size:18px;letter-spacing:.25em;margin:0;color:var(--glow);text-shadow:0 0 12px var(--sap)}
#state{font-size:12px;color:var(--dim)}
#state i{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--bad);margin-right:6px}
#state.on i{background:var(--ok);box-shadow:0 0 8px var(--ok)}
main{flex:1;overflow-y:auto;padding:16px 18px;display:flex;flex-direction:column;gap:10px}
.msg{max-width:88%;padding:10px 14px;border-radius:12px;border:1px solid #123a7a;background:var(--panel);white-space:pre-wrap;word-break:break-word}
.me{align-self:flex-end;border-color:var(--sap);background:#0b2a63}
.ella{align-self:flex-start;box-shadow:0 0 14px rgba(15,82,186,.35)}
.err{border-color:var(--bad);color:var(--bad)}
.tool{align-self:flex-start;font-size:12px;color:var(--dim);padding:0 6px;margin-top:-4px}
footer{padding:12px 18px 16px;border-top:1px solid #123a7a;display:flex;flex-direction:column;gap:10px}
#live{min-height:20px;color:var(--dim);font-size:14px}
.row{display:flex;gap:8px;align-items:center}
input,select,button{font:inherit;color:var(--txt);background:var(--panel);border:1px solid #123a7a;border-radius:10px;padding:10px 12px}
input{flex:1;min-width:0}
button{cursor:pointer}
#mic{width:64px;height:64px;border-radius:50%;border:2px solid var(--glow);box-shadow:0 0 18px var(--sap);font-size:26px;padding:0;flex:none}
#mic.rec{background:var(--sap);animation:pulse 1.2s infinite}
@keyframes pulse{50%{box-shadow:0 0 34px var(--glow)}}
#login{position:fixed;inset:0;background:rgba(3,10,26,.96);display:none;align-items:center;justify-content:center;padding:24px;z-index:5}
#login .box{width:100%;max-width:360px;display:flex;flex-direction:column;gap:12px}
#loginErr{color:var(--bad);min-height:20px;font-size:14px}
.thumb{display:block;max-width:200px;max-height:200px;border-radius:10px;margin-bottom:6px}
#preview img{height:56px;border-radius:8px;border:1px solid var(--sap)}
</style>
</head>
<body>
<header><h1>ЭЛЛА</h1><div id="state"><i></i><span>нет связи</span></div></header>
<main id="log"></main>
<footer>
 <div id="live"></div>
 <div id="preview" class="row" style="display:none"><img id="prevImg" alt="Фото"><span style="font-size:13px;color:var(--dim)">фото готово к отправке</span><button id="prevDel" title="Убрать фото">✕</button></div>
 <div class="row">
  <button id="mic" title="Говорить" aria-label="Микрофон">🎙</button>
  <input id="text" placeholder="Команда текстом…" autocomplete="off">
  <button id="send">▶</button>
 </div>
 <div class="row" style="flex-wrap:wrap">
  <select id="provider"><option value="gemini">Gemini</option><option value="claude">Claude</option></select>
  <label style="font-size:14px;color:var(--dim)"><input type="checkbox" id="speak" checked style="flex:none"> озвучивать</label>
  <button id="cam" title="Сфотографировать" aria-label="Камера">📷</button>
  <button id="gal" title="Фото из галереи" aria-label="Галерея">🖼</button>
  <label style="font-size:14px;color:var(--dim)"><input type="checkbox" id="scan" style="flex:none"> скан</label>
  <input type="file" id="fileCam" accept="image/*" capture="environment" hidden>
  <input type="file" id="fileGal" accept="image/*" hidden>
 </div>
</footer>
<div id="login"><div class="box">
 <h1>ДОСТУП</h1>
 <input id="pass" type="password" placeholder="Кодовая фраза" autocomplete="current-password">
 <button id="enter">Войти</button>
 <div id="loginErr"></div>
</div></div>

<script>
"use strict";
const $ = id => document.getElementById(id);
const store = {
  get(k){ try { return sessionStorage.getItem(k); } catch(e){ return null; } },
  set(k,v){ try { sessionStorage.setItem(k,v); } catch(e){} }
};
let token = store.get("ella_token") || "";
let sessionId = store.get("ella_sid");
if (!sessionId) { sessionId = Math.random().toString(36).slice(2) + Date.now().toString(36); store.set("ella_sid", sessionId); }

function plain(t){                    // убираем markdown-разметку для показа
  return String(t).replace(/\*\*|__|`/g, "").replace(/^\s*#+\s*/gm, "")
    .replace(/^\s*[*-]\s+/gm, "• ").replace(/\*/g, "");
}
function add(text, cls, imgUrl){
  const d = document.createElement("div");
  d.className = "msg " + cls;
  if (imgUrl) { const i = document.createElement("img"); i.src = imgUrl; i.className = "thumb"; d.appendChild(i); }
  if (text) d.appendChild(document.createTextNode(cls === "ella" ? plain(text) : text));   // без XSS
  $("log").appendChild(d);
  $("log").scrollTop = $("log").scrollHeight;
}
function setState(on, label){
  $("state").className = on ? "on" : "";
  $("state").lastChild.textContent = label;
}

async function api(path, opts = {}){
  const headers = Object.assign({"Content-Type":"application/json"}, opts.headers || {});
  if (token) headers.Authorization = "Bearer " + token;
  const r = await fetch(path, Object.assign({}, opts, {headers}));
  if (r.status === 401) { showLogin(); throw new Error("Нужен вход"); }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.response || ("Ошибка " + r.status));
  return data;
}

function showLogin(){ $("login").style.display = "flex"; $("pass").focus(); }

async function login(){
  $("loginErr").textContent = "";
  try {
    const r = await fetch("/auth/login", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({passphrase: $("pass").value})});
    const data = await r.json().catch(() => ({}));
    if (!r.ok) { $("loginErr").textContent = data.response || "Не удалось войти"; return; }
    token = data.token; store.set("ella_token", token);
    $("pass").value = ""; $("login").style.display = "none";
    await checkStatus();
  } catch(e){ $("loginErr").textContent = "Нет связи с сервером"; }
}

async function checkStatus(){
  try {
    const s = await api("/status");
    const n = st => s.modules.filter(m => m.status === st).length;
    setState(true, `онлайн · актив. ${n("active")} · баз. ${n("basic")} · бета ${n("beta")} из ${s.modules.length}`);
  } catch(e){ setState(false, "нет связи"); }
}

// ---------- Озвучка (Web Speech API: speechSynthesis) ----------
function speak(text){
  if (!$("speak").checked || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const clean = text.replace(/[*#`_>|]/g, " ").replace(/\s+/g, " ").slice(0, 1200);
  const u = new SpeechSynthesisUtterance(clean);
  u.lang = "ru-RU";
  const v = speechSynthesis.getVoices().find(v => v.lang && v.lang.toLowerCase().startsWith("ru"));
  if (v) u.voice = v;
  speechSynthesis.speak(u);
}

async function send(command){
  command = command.trim();
  const img = pending;
  if (!command && !img) return;
  add(command || "Что на фото?", "me", img ? img.url : null);
  clearImage();
  $("text").value = ""; $("live").textContent = "Элла думает…";
  try {
    const r = await api("/command", {method:"POST", body: JSON.stringify(
      {command, provider: $("provider").value, session_id: sessionId,
       image: img ? {mime: img.mime, data: img.data} : undefined})});
    add(r.response, "ella");
    if (r.tools && r.tools.length) add("⚙ расчёт: " + [...new Set(r.tools)].join(", "), "tool");
    speak(r.response);
  } catch(e){ add(e.message, "err"); }
  $("live").textContent = "";
}

// ---------- Распознавание речи (Web Speech API: SpeechRecognition) ----------
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let rec = null, listening = false;
if (SR) {
  rec = new SR();
  rec.lang = "ru-RU";
  rec.interimResults = true;
  rec.continuous = false;
  rec.onresult = ev => {
    let interim = "", final = "";
    for (const res of ev.results) (res.isFinal ? (final += res[0].transcript) : (interim += res[0].transcript));
    $("live").textContent = interim || final;
    if (final) send(final);
  };
  rec.onerror = ev => { $("live").textContent = "Микрофон: " + ev.error; };
  rec.onend = () => { listening = false; $("mic").classList.remove("rec"); };
} else {
  $("mic").disabled = true;
  $("live").textContent = "Голосовой ввод не поддерживается этим браузером (нужен Chrome, Edge или Safari). Можно писать текстом.";
}

$("mic").onclick = () => {
  if (!rec) return;
  if (listening) { rec.stop(); return; }
  if ("speechSynthesis" in window) speechSynthesis.cancel();   // не слушаем собственный голос
  try { rec.start(); listening = true; $("mic").classList.add("rec"); $("live").textContent = "Слушаю…"; }
  catch(e){ $("live").textContent = "Не удалось включить микрофон"; }
};
$("send").onclick = () => send($("text").value);
$("text").onkeydown = e => { if (e.key === "Enter") send($("text").value); };
$("enter").onclick = login;
$("pass").onkeydown = e => { if (e.key === "Enter") login(); };

// ---------- Фото: камера, галерея, режим «скан» ----------
let pending = null;   // {mime, data, url}
function loadImage(file){
  return new Promise((resolve, reject) => {
    const img = new Image();
    const src = URL.createObjectURL(file);
    img.onload = () => {
      const scale = Math.min(1, 1280 / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = Math.round(img.width * scale); c.height = Math.round(img.height * scale);
      const ctx = c.getContext("2d");
      if ($("scan").checked && "filter" in ctx) ctx.filter = "grayscale(1) contrast(1.5) brightness(1.1)";
      ctx.drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(src);
      const url = c.toDataURL("image/jpeg", 0.82);
      resolve({mime: "image/jpeg", data: url.split(",")[1], url});
    };
    img.onerror = () => { URL.revokeObjectURL(src); reject(new Error("Не удалось открыть фото (формат не поддерживается браузером)")); };
    img.src = src;
  });
}
async function pick(file){
  if (!file) return;
  $("live").textContent = "Обрабатываю фото…";
  try {
    pending = await loadImage(file);
    $("prevImg").src = pending.url;
    $("preview").style.display = "flex";
    $("live").textContent = "Фото добавлено. Напишите вопрос или просто нажмите ▶";
  } catch(e){ add(e.message, "err"); $("live").textContent = ""; }
}
function clearImage(){
  pending = null; $("preview").style.display = "none"; $("prevImg").removeAttribute("src");
}
$("cam").onclick = () => $("fileCam").click();
$("gal").onclick = () => $("fileGal").click();
for (const id of ["fileCam", "fileGal"]) {
  $(id).onchange = e => { pick(e.target.files[0]); e.target.value = ""; };
}
$("prevDel").onclick = () => { clearImage(); $("live").textContent = ""; };

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});

checkStatus();
add("Системы Элла на связи. Нажмите на микрофон или введите команду.", "ella");
</script>
</body>
</html>
