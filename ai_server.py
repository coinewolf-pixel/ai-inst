<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Мой AI</title>
<style>
* {box-sizing: border-box;}
body {
  margin: 0;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
  background: #0f0f12;
  color: #e8e8e8;
  height: 100vh;
  display: flex;
  flex-direction: column;
}
header {
  padding: 16px 24px;
  border-bottom: 1px solid #2a2a2e;
  display: flex;
  align-items: center;
  gap: 12px;
  background: #0f0f12;
}
header h1 {margin: 0; font-size: 18px; font-weight: 600;}
#key {
  margin-left: auto;
  background: #1c1c21;
  border: 1px solid #333;
  color: #fff;
  padding: 8px 12px;
  border-radius: 8px;
  width: 220px;
}
#chat {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.msg {
  max-width: 720px;
  padding: 14px 18px;
  border-radius: 16px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.me {background: #2d5be3; align-self: flex-end; color: white;}
.ai {background: #1c1c21; border: 1px solid #2a2a2e; align-self: flex-start;}
.meta {font-size: 12px; color: #888; margin-top: 8px;}
.input-area {
  padding: 16px 24px 24px;
  border-top: 1px solid #2a2a2e;
  background: #0f0f12;
}
#task, #gen, #editPrompt {
  width: 100%;
  background: #1c1c21;
  border: 1px solid #333;
  color: #fff;
  padding: 14px 16px;
  border-radius: 12px;
  font: inherit;
  resize: none;
  min-height: 52px;
  max-height: 200px;
}
.row {display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap;}
button {
  background: #2d5be3;
  color: white;
  border: 0;
  padding: 10px 18px;
  border-radius: 10px;
  cursor: pointer;
  font: inherit;
}
button.grey {background: #2a2a2e;}
button:disabled {opacity: .5; cursor: not-allowed;}
details {
  background: #1c1c21;
  border: 1px solid #2a2a2e;
  border-radius: 12px;
  margin: 12px 24px;
  padding: 12px 16px;
}
summary {cursor: pointer; font-weight: 500; outline: none;}
#fgen, #fup {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  margin-top: 12px;
}
.card {
  background: #16161a;
  border: 1px solid #2a2a2e;
  border-radius: 10px;
  padding: 8px;
  font-size: 12px;
  overflow: hidden;
}
.card img, .card video {
  width: 100%;
  height: 120px;
  object-fit: cover;
  border-radius: 6px;
  display: block;
  background: #000;
}
</style>
</head>
<body>
<header>
  <h1>Мой AI</h1>
  <input id="key" type="password" placeholder="Пароль">
</header>

<div id="chat"></div>

<div class="input-area">
  <textarea id="task" placeholder="Напишите задачу..."></textarea>
  <div class="row">
    <button id="send">Отправить</button>
    <button id="mic" class="grey" title="Голосовой ввод">🎤</button>
  </div>
</div>

<details>
  <summary>Создать картинку или видео</summary>
  <p style="font-size:13px;color:#aaa;margin:8px 0">Картинка: опишите, что нарисовать. Видео: каждая строка — отдельная сцена.</p>
  <textarea id="gen" placeholder="Например: рыжий кот сидит на подоконнике, за окном дождь, акварель"></textarea>
  <div class="row">
    <button id="mkimg" class="grey">Создать картинку</button>
    <button id="mkvid" class="grey">Создать видео по строкам</button>
  </div>
  <div id="geninfo" class="meta"></div>
</details>

<details>
  <summary>Загрузить фото и изменить / сделать видео</summary>
  <p style="font-size:13px;color:#aaa;margin:8px 0">Загрузите фото, затем опишите, что с ним сделать.</p>
  <input id="photoFile" type="file" accept="image/*">
  <textarea id="editPrompt" placeholder="Что сделать с фото? Например: сделай в стиле аниме / добавь дождь / сделай видео"></textarea>
  <div class="row">
    <button id="editPhoto" class="grey">Обработать фото</button>
    <button id="photoToVideo" class="grey">Сделать видео из фото</button>
  </div>
  <div id="photoinfo" class="meta"></div>
</details>

<details id="filesbox">
  <summary>Мои файлы</summary>
  <div class="row"><button id="reload" class="grey">Обновить список</button></div>
  <div id="filesmsg" class="meta"></div>
  <h3 style="font-size:15px;margin:12px 0 6px">Создано AI</h3>
  <div id="fgen"></div>
  <h3 style="font-size:15px;margin:16px 0 6px">Загружено вами</h3>
  <div id="fup"></div>
</details>

<details>
  <summary>Добавить файл в базу знаний</summary>
  <p style="font-size:13px;color:#aaa;margin:8px 0">Тексты, код, PDF, фото, видео, аудио.</p>
  <input id="file" type="file" multiple>
  <div class="row"><button id="up" class="grey">Загрузить</button></div>
  <div id="upinfo" class="meta" style="white-space:pre-wrap"></div>
  <div id="jobs" class="meta" style="white-space:pre-wrap"></div>
</details>

<script>
const $=id=>document.getElementById(id);
function setCookie(){ document.cookie="aikey="+encodeURIComponent($("key").value.trim())+"; path=/; max-age=31536000; SameSite=Strict"; }
try{ $("key").value=localStorage.getItem("aikey")||""; }catch(e){}
setCookie();
$("key").onchange=()=>{ try{localStorage.setItem("aikey",$("key").value)}catch(e){} setCookie(); files(); };

function hdr(){return {"Content-Type":"application/json","Authorization":"Bearer "+encodeURIComponent($("key").value.trim())};}

function add(text,cls){
  const d=document.createElement("div");
  d.className="msg "+(cls||"ai");
  d.textContent=text;
  $("chat").appendChild(d);
  d.scrollIntoView({behavior:"smooth", block:"end"});
  return d;
}

async function api(path,body){
  const r=await fetch(path,{method:"POST",headers:hdr(),body:JSON.stringify(body)});
  const j=await r.json().catch(()=>({error:"Сервер вернул не JSON"}));
  if(!r.ok) throw new Error(j.error||("Ошибка "+r.status));
  return j;
}

$("send").onclick=async()=>{
  const task=$("task").value.trim(); if(!task) return;
  add(task,"me"); $("task").value=""; $("send").disabled=true;
  const wait=add("Думаю...");
  try{
    const j=await api("/api/ask",{task});
    wait.textContent=j.answer;
    wait.className="msg ai";
    const m=document.createElement("div"); m.className="meta";
    const src=[...j.memory.map(x=>"память: "+x.task.slice(0,40)),...j.files.map(x=>"файл: "+x.file)];
    m.textContent=src.length?("Опирался на: "+src.join("; ")):"Решал с нуля";
    const b=document.createElement("button"); b.className="grey"; b.textContent="Сработало, сохранить в память";
    b.onclick=async()=>{b.disabled=true;try{await api("/api/save",{task,solution:j.answer});b.textContent="Сохранено";}catch(e){b.textContent=e.message;}};
    wait.appendChild(m);
    wait.appendChild(document.createElement("br"));
    wait.appendChild(b);
  }catch(e){ wait.textContent="Ошибка: "+e.message; }
  $("send").disabled=false;
};

// Голосовой ввод
const micBtn = $("mic");
let recognition = null;
if ("webkitSpeechRecognition" in window || "SpeechRecognition" in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRecognition();
  recognition.lang = "ru-RU";
  recognition.interimResults = true;
  recognition.continuous = false;
  recognition.onstart = () => { micBtn.textContent = "⏹"; micBtn.style.background = "#c0392b"; };
  recognition.onresult = (event) => {
    let finalText = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      if (event.results[i].isFinal) finalText += event.results[i][0].transcript;
    }
    if (finalText) {
      const current = $("task").value.trim();
      $("task").value = current ? current + " " + finalText : finalText;
      $("task").focus();
    }
  };
  recognition.onend = () => { micBtn.textContent = "🎤"; micBtn.style.background = ""; };
  recognition.onerror = () => { micBtn.textContent = "🎤"; micBtn.style.background = ""; };
  micBtn.onclick = () => { micBtn.textContent === "⏹" ? recognition.stop() : recognition.start(); };
} else {
  micBtn.disabled = true;
  micBtn.title = "Голосовой ввод не поддерживается";
}

// Генерация
async function gen(kind){
  const t=$("gen").value.trim(); if(!t){ $("geninfo").textContent="Сначала напишите описание"; return; }
  if(!$("key").value.trim()){ $("geninfo").textContent="Сначала введите пароль"; return; }
  const body=kind==="image"?{prompt:t}:{scenes:t.split("\n").filter(x=>x.trim())};
  try{ await api("/api/"+kind,body); $("geninfo").textContent="Принято. Смотрите в «Мои файлы»."; jobs(); }
  catch(e){ $("geninfo").textContent=e.message; }
}
$("mkimg").onclick=()=>gen("image");
$("mkvid").onclick=()=>gen("video");

// Загрузка фото + обработка
$("editPhoto").onclick = async () => {
  const file = $("photoFile").files[0];
  const prompt = $("editPrompt").value.trim();
  if (!file) { $("photoinfo").textContent = "Сначала выберите фото"; return; }
  if (!prompt) { $("photoinfo").textContent = "Напишите, что сделать с фото"; return; }
  $("photoinfo").textContent = "Загружаю фото...";
  try {
    const data = await new Promise((ok, bad) => {
      const r = new FileReader();
      r.onload = () => ok(String(r.result).split(",")[1] || "");
      r.onerror = bad;
      r.readAsDataURL(file);
    });
    await api("/api/upload", {name: file.name, data});
    $("photoinfo").textContent = "Фото загружено. Генерирую по описанию...";
    await api("/api/image", {prompt: prompt + " на основе загруженного фото " + file.name});
    $("photoinfo").textContent = "Готово. Смотрите в «Мои файлы».";
    jobs();
  } catch(e) {
    $("photoinfo").textContent = "Ошибка: " + e.message;
  }
};

$("photoToVideo").onclick = async () => {
  const file = $("photoFile").files[0];
  const prompt = $("editPrompt").value.trim() || "сделай короткое видео из этого фото";
  if (!file) { $("photoinfo").textContent = "Сначала выберите фото"; return; }
  $("photoinfo").textContent = "Загружаю фото и создаю видео...";
  try {
    const data = await new Promise((ok, bad) => {
      const r = new FileReader();
      r.onload = () => ok(String(r.result).split(",")[1] || "");
      r.onerror = bad;
      r.readAsDataURL(file);
    });
    await api("/api/upload", {name: file.name, data});
    await api("/api/video", {scenes: [prompt + " с фото " + file.name]});
    $("photoinfo").textContent = "Видео в очереди. Смотрите в «Мои файлы».";
    jobs();
  } catch(e) {
    $("photoinfo").textContent = "Ошибка: " + e.message;
  }
};

// Загрузка в базу знаний
$("up").onclick=async()=>{
  const files=[...$("file").files]; if(!files.length) return;
  if(!$("key").value.trim()){ $("upinfo").textContent="Сначала введите пароль"; return; }
  $("up").disabled=true;
  const log=[]; const show=()=>{$("upinfo").textContent=log.join("\n");};
  let okN=0, badN=0;
  for(const f of files){
    log.push(f.name+": отправляю..."); show();
    try{
      const data=await new Promise((ok,bad)=>{const r=new FileReader();r.onload=()=>ok(String(r.result).split(",")[1]||"");r.onerror=bad;r.readAsDataURL(f);});
      await api("/api/upload",{name:f.name,data});
      log[log.length-1]=f.name+": принят"; okN++;
    }catch(e){ log[log.length-1]=f.name+": ошибка — "+e.message; badN++; }
    show();
  }
  log.push("Итого: принято "+okN+", ошибок "+badN); show();
  $("up").disabled=false; jobs();
};

function human(n){ return n>1048576?(n/1048576).toFixed(1)+" МБ":Math.max(1,Math.round(n/1024))+" КБ"; }
function card(f){
  const c=document.createElement("div"); c.className="card";
  if(/[.](png|jpe?g|webp|gif|bmp)$/i.test(f.name)){
    const im=document.createElement("img"); im.src=f.url; im.loading="lazy"; c.appendChild(im);
  } else if(/[.](mp4|webm|mov)$/i.test(f.name)){
    const v=document.createElement("video"); v.src=f.url; v.controls=true; v.preload="metadata"; c.appendChild(v);
  }
  const t=document.createElement("div"); t.textContent=f.name; t.style.cssText="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:6px"; c.appendChild(t);
  const m=document.createElement("div"); m.className="meta"; m.textContent=f.kind+", "+human(f.size); c.appendChild(m);
  const o=document.createElement("a"); o.href=f.url; o.target="_blank"; o.textContent="открыть"; o.style.color="#8ab4ff";
  const dl=document.createElement("a"); dl.href=f.url+"?download=1"; dl.textContent="скачать"; dl.style.marginLeft="10px"; dl.style.color="#8ab4ff";
  c.appendChild(o); c.appendChild(dl); return c;
}

async function files(){
  const msg=$("filesmsg"), gen=$("fgen"), up=$("fup");
  try{
    const r=await fetch("/api/files",{headers:hdr()});
    if(!r.ok){ msg.textContent="Введите пароль, чтобы увидеть файлы"; return; }
    const j=await r.json(); msg.textContent=""; gen.textContent=""; up.textContent="";
    const g=j.files.filter(f=>f.kind==="создано"), u=j.files.filter(f=>f.kind!=="создано");
    for(const f of g) gen.appendChild(card(f));
    for(const f of u) up.appendChild(card(f));
    if(!g.length) gen.textContent="Пока ничего не создано.";
    if(!u.length) up.textContent="Пока ничего не загружено.";
  }catch(e){ msg.textContent="Ошибка: "+e.message; }
}
$("reload").onclick=files;
$("filesbox").addEventListener("toggle",()=>{ if($("filesbox").open) files(); });

async function jobs(){
  try{
    const r=await fetch("/api/jobs",{headers:hdr()}); if(!r.ok) return;
    const j=await r.json();
    const box=$("jobs"); box.textContent="";
    for(const x of j.jobs.slice(-10).reverse()){
      const d=document.createElement("div"); d.textContent=x.file+" — "+x.status;
      if(x.url){
        const a=document.createElement("a"); a.href=x.url; a.target="_blank"; a.textContent=" открыть"; a.style.color="#8ab4ff";
        const dl=document.createElement("a"); dl.href=x.url+"?download=1"; dl.textContent=" скачать"; dl.style.color="#8ab4ff";
        d.appendChild(a); d.appendChild(dl);
      }
      box.appendChild(d);
    }
    if(j.jobs.some(x=>x.status==="в очереди"||x.status.startsWith("обрабатывается"))) setTimeout(jobs,5000);
    else if($("filesbox").open) files();
  }catch(e){}
}
jobs();
</script>
</body>
</html>
