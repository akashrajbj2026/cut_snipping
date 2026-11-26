// The backend serves this page itself, so the API lives on the SAME origin.
// That is true on Render (https://your-app.onrender.com, port 443), behind any
// reverse proxy, and on http://127.0.0.1:8000 locally.
// The ONLY time we point somewhere else is the old two-terminal dev setup where
// this page is served by `python -m http.server 5500` (or opened as file://),
// in which case the backend is on port 8000 of the same host name.
const IS_STATIC_DEV_SERVER = location.protocol === "file:" || location.port === "5500";
const API_BASE = IS_STATIC_DEV_SERVER
  ? `http://${location.hostname || "127.0.0.1"}:8000`
  : "";
// ---- Upload helper (kept at the very top so it always exists before any click handler runs) ----
function uploadWithProgress(formData) {
  return new Promise((resolve, reject) => {
    const fill = document.getElementById("upload-progress-fill");
    const text = document.getElementById("upload-progress-text");
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/upload`);
    xhr.upload.addEventListener("progress", (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.round((e.loaded / e.total) * 100);
      if (fill) fill.style.width = `${pct}%`;
      if (text) text.textContent = `${pct}%`;
    });
    xhr.onload = () => {
      let body = {};
      try { body = JSON.parse(xhr.responseText); } catch (_) {}
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else reject(new Error(body.detail || "Upload failed."));
    };
    xhr.onerror = () => reject(new Error(`Couldn't reach the backend. Start it with: cd backend, then uvicorn main:app --reload --port 8000 (backend URL: ${API_BASE || location.origin}).`));
    xhr.send(formData);
  });
}
window.uploadWithProgress = uploadWithProgress;

const screens={upload:document.getElementById("screen-upload"),interest:document.getElementById("screen-interest"),result:document.getElementById("screen-result")};
const railItems=document.querySelectorAll(".rail-item");const statusBanner=document.getElementById("status-banner");const sessionState=document.getElementById("session-state");const coreStatus=document.getElementById("core-status");const scanReadout=document.getElementById("scan-readout");const rangeReadout=document.getElementById("range-readout");const sourceStat=document.getElementById("source-stat");const targetStat=document.getElementById("target-stat");const monitorTitle=document.getElementById("monitor-title");const timelineState=document.getElementById("timeline-state");const timelineProgress=document.getElementById("timeline-progress");const filmstrip=document.getElementById("filmstrip");
const tabUpload=document.getElementById("tab-upload"),tabLink=document.getElementById("tab-link"),panelUpload=document.getElementById("panel-upload"),panelLink=document.getElementById("panel-link"),videoInput=document.getElementById("video-input"),videoLink=document.getElementById("video-link"),dropzone=document.getElementById("dropzone"),dropzoneText=document.querySelector(".dropzone-text");const uploadProgress=document.getElementById("upload-progress"),uploadProgressFill=document.getElementById("upload-progress-fill"),uploadProgressText=document.getElementById("upload-progress-text");const btnCompleteUpload=document.getElementById("btn-complete-upload"),btnGenerate=document.getElementById("btn-generate"),btnChangeVideo=document.getElementById("btn-change-video"),btnStartOver=document.getElementById("btn-start-over"),btnDownload=document.getElementById("btn-download");const interestInput=document.getElementById("interest-input"),quoteText=document.getElementById("quote-text"),resultVideo=document.getElementById("result-video"),resultPlaceholder=document.getElementById("result-placeholder"),durationReadout=document.getElementById("duration-readout"),resultRangeCount=document.getElementById("result-range-count");
let activeTab="upload",jobId=null;
function showStatus(message){statusBanner.textContent=message;statusBanner.classList.remove("hidden")}function clearStatus(){statusBanner.classList.add("hidden");statusBanner.textContent=""}
function showScreen(name){Object.entries(screens).forEach(([key,el])=>el.classList.toggle("hidden",key!==name));const step={upload:1,interest:2,result:3}[name];railItems.forEach((item,i)=>{item.classList.toggle("is-active",i===step-1)});sessionState.textContent=name==="upload"?"READY":name==="interest"?"BRIEFING":"COMPLETE";coreStatus.textContent=name==="upload"?"STANDBY":name==="interest"?"ARMED":"DONE"}
function formatTimecode(seconds){if(seconds===undefined||seconds===null)return"";const total=Math.max(0,Math.round(seconds));return `${String(Math.floor(total/60)).padStart(2,"0")}:${String(total%60).padStart(2,"0")}`}
function setTab(tab){activeTab=tab;const upload=tab==="upload";tabUpload.classList.toggle("active",upload);tabLink.classList.toggle("active",!upload);tabUpload.setAttribute("aria-selected",String(upload));tabLink.setAttribute("aria-selected",String(!upload));panelUpload.classList.toggle("hidden",!upload);panelLink.classList.toggle("hidden",upload)}
tabUpload.addEventListener("click",()=>setTab("upload"));tabLink.addEventListener("click",()=>setTab("link"));
videoInput.addEventListener("change",()=>{if(videoInput.files.length){const file=videoInput.files[0];dropzoneText.textContent=file.name;sourceStat.textContent=file.name.length>18?file.name.slice(0,15)+"…":file.name;monitorTitle.textContent=file.name;timelineState.textContent="SOURCE READY"}});
["dragover","dragleave","drop"].forEach(evt=>dropzone.addEventListener(evt,e=>{e.preventDefault();dropzone.classList.toggle("dragover",evt==="dragover")}));dropzone.addEventListener("drop",e=>{const file=e.dataTransfer.files[0];if(file){videoInput.files=e.dataTransfer.files;videoInput.dispatchEvent(new Event("change"))}});
document.querySelectorAll("[data-prompt]").forEach(btn=>btn.addEventListener("click",()=>{interestInput.value=btn.dataset.prompt;interestInput.focus()}));
btnCompleteUpload.addEventListener("click",async()=>{clearStatus();const formData=new FormData();if(activeTab==="upload"){if(!videoInput.files.length){showStatus("Choose a video file first.");return}formData.append("file",videoInput.files[0])}else{if(!videoLink.value.trim()){showStatus("Paste a video link first.");return}formData.append("url",videoLink.value.trim())}btnCompleteUpload.disabled=true;btnCompleteUpload.innerHTML="Importing… <span>↗</span>";if(activeTab==="upload"){uploadProgress.classList.remove("hidden");uploadProgressFill.style.width="0%";uploadProgressText.textContent="0%"}try{const data=await uploadWithProgress(formData);jobId=data.job_id;sourceStat.textContent=activeTab==="upload"?(videoInput.files[0].name.length>18?videoInput.files[0].name.slice(0,15)+"…":videoInput.files[0].name):"REMOTE LINK";timelineState.textContent="SOURCE READY";showScreen("interest")}catch(err){showStatus(err.message)}finally{btnCompleteUpload.disabled=false;btnCompleteUpload.innerHTML="Import source <span>→</span>";uploadProgress.classList.add("hidden")}});
btnChangeVideo.addEventListener("click",()=>{clearStatus();showScreen("upload")});
btnGenerate.addEventListener("click",async()=>{clearStatus();if(!interestInput.value.trim()){showStatus("Write a brief so the engine knows what to look for.");return}if(!jobId){showStatus("Import a source first.");return}btnGenerate.disabled=true;btnGenerate.innerHTML="Scanning the full source… <span>↗</span>";quoteText.textContent=`“${interestInput.value.trim()}”`;coreStatus.textContent="ANALYZING";timelineState.textContent="ANALYZING SOURCE";filmstrip.classList.add("is-processing");try{const formData=new FormData();formData.append("job_id",jobId);formData.append("interest",interestInput.value.trim());const res=await fetch(`${API_BASE}/generate`,{method:"POST",body:formData});if(!res.ok){let message="Could not start generation.";try{message=(await res.json()).detail||message}catch(_){}throw new Error(message)}await pollStatus();showScreen("result")}catch(err){showStatus(err.message);coreStatus.textContent="ERROR"}finally{btnGenerate.disabled=false;btnGenerate.innerHTML="Analyze & cut <span>→</span>";filmstrip.classList.remove("is-processing")}});
async function pollStatus(){let tick=0;while(true){let res;try{res=await fetch(`${API_BASE}/status/${jobId}`,{cache:"no-store"})}catch(_){throw new Error(`Lost the connection to the backend. Make sure it's still running (backend URL: ${API_BASE || location.origin}).`)}if(!res.ok){let message="Could not read job status.";try{message=(await res.json()).detail||message}catch(_){}throw new Error(message)}const data=await res.json();if(data.status==="done"){scanReadout.textContent="100%";timelineProgress.style.width="100%";rangeReadout.textContent=String((data.segments||[]).length);resultRangeCount.textContent=String((data.segments||[]).length);resultVideo.src=`${API_BASE}/result/${jobId}?t=${Date.now()}`;resultVideo.classList.remove("hidden");resultPlaceholder.classList.add("hidden");const from=formatTimecode(data.original_duration),to=formatTimecode(data.cut_duration);durationReadout.textContent=from&&to?`${from} → ${to}`:"CUT READY";targetStat.textContent=to||"READY";timelineState.textContent="CUT READY";coreStatus.textContent="DONE";return}if(data.status==="error")throw new Error(data.error||"Generation failed. Check the backend terminal for the detailed error.");tick=Math.min(94,tick+1);scanReadout.textContent=`${tick}%`;timelineProgress.style.width=`${tick}%`;if(data.progress)btnGenerate.innerHTML=`${data.progress} <span>↗</span>`;await new Promise(resolve=>setTimeout(resolve,2000))}}
btnStartOver.addEventListener("click",()=>{clearStatus();jobId=null;videoInput.value="";videoLink.value="";interestInput.value="";dropzoneText.textContent="Choose a source or drag it here";sourceStat.textContent="—";monitorTitle.textContent="Waiting for a source";resultVideo.classList.add("hidden");resultVideo.src="";resultPlaceholder.classList.remove("hidden");durationReadout.textContent="";rangeReadout.textContent="0";scanReadout.textContent="0%";timelineProgress.style.width="0";timelineState.textContent="NO MEDIA LOADED";showScreen("upload")});btnDownload.addEventListener("click",()=>{if(jobId)window.location.href=`${API_BASE}/result/${jobId}`});showScreen("upload");

// ---- Preflight: tell the user what is wrong BEFORE they upload anything ----
(async function preflight() {
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    if (!res.ok) throw new Error("bad status");
    const h = await res.json();
    const problems = [];
    if (h.ffmpeg === false || h.ffprobe === false) problems.push("FFmpeg is not installed or not on PATH (needed to cut video). Install it, then restart the backend.");
    if (Array.isArray(h.configured_providers) && h.configured_providers.length === 0) problems.push("No API key found. Set GEMINI_API_KEY and/or GROQ_API_KEY (backend/.env locally, or Environment Variables on Render), then restart the backend.");
    if (problems.length) { showStatus(problems.join("  ")); return; }

    // Keys exist - now check they are actually accepted (cheap, read-only calls).
    try {
      const dr = await fetch(`${API_BASE}/diagnose`, { cache: "no-store" });
      if (dr.ok) {
        const d = await dr.json();
        const bad = Object.entries(d.providers || {})
          .filter(([, v]) => v.configured && !v.ok)
          .map(([name, v]) => `${name}: ${v.detail}`);
        if (bad.length) showStatus("API key problem - " + bad.join("  |  "));
      }
    } catch (_) { /* diagnose is a bonus; never block the page on it */ }
  } catch (_) {
    showStatus(`Backend not reachable at ${API_BASE || location.origin}. Locally run: cd backend, activate venv, then: uvicorn main:app --reload --port 8000`);
  }
})();
