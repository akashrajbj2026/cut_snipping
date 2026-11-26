"""Cut Away backend - entry point.

Free-tier-only provider stack:

    video
     |- audio -> transcript provider (Groq Whisper, free; or local
     |            faster-whisper - fully offline, no key at all)
     `- file  -> Gemini (native full-video understanding, free tier)

Groq also serves as a transcript-only fallback analyzer if Gemini's daily
free quota runs out. Every provider returns the same normalized segment
shape, so the cutting and merging logic never changes. Configure the chain
with PRIMARY_PROVIDER and FALLBACK_PROVIDERS in .env.

Run (one terminal, one command):
    uvicorn main:app --reload --port 8000
then open http://127.0.0.1:8000  (the backend also serves the frontend).
"""

import os
import shutil

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routes.video_routes import router

app = FastAPI(title="Cut Away", version="2.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.middleware("http")
async def no_stale_frontend(request, call_next):
    """Never let the browser reuse an old index.html / script.js / style.css.

    A stale cached script is the classic cause of errors like
    "uploadWithProgress is not defined" after the code was updated.
    """
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        response.headers["Cache-Control"] = "no-store, must-revalidate"
    return response


@app.on_event("startup")
async def _log_key_status():
    """Shows up in Render's Logs tab so a missing/misnamed key is obvious."""
    import config

    print("=" * 60)
    print("Cut Away starting")
    print(f"  GEMINI_API_KEY : {config.key_status('GEMINI_API_KEY')}")
    print(f"  GROQ_API_KEY   : {config.key_status('GROQ_API_KEY')}")
    print(f"  ffmpeg         : {'found' if shutil.which('ffmpeg') else 'MISSING'}")
    print("=" * 60)


@app.get("/health")
async def health():
    """Used by the frontend on page load to tell the user what is missing."""
    import config
    from providers import configured_providers

    return {
        "status": "ok",
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ffprobe": shutil.which("ffprobe") is not None,
        "yt_dlp": shutil.which("yt-dlp") is not None,
        "configured_providers": configured_providers(),
        "primary": config.PRIMARY_PROVIDER,
    }


@app.get("/diagnose")
async def diagnose():
    """Makes one cheap, read-only call per provider to prove each key works.

    Never returns the key itself. Open https://<your-site>/diagnose to see
    exactly which key is missing, wrong, or blocked.
    """
    import requests

    import config
    from fastapi.concurrency import run_in_threadpool

    def check_groq() -> dict:
        status = config.key_status("GROQ_API_KEY")
        if status != "set":
            return {"configured": False, "ok": False, "detail": f"GROQ_API_KEY is {status}"}
        try:
            r = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                timeout=15,
            )
        except requests.RequestException as exc:
            return {"configured": True, "ok": False, "detail": f"Could not reach Groq: {exc.__class__.__name__}"}
        if r.status_code == 200:
            return {"configured": True, "ok": True, "detail": "key accepted"}
        if r.status_code in (401, 403):
            return {"configured": True, "ok": False, "detail": f"Groq rejected the key (HTTP {r.status_code}) - create a new one at console.groq.com/keys"}
        return {"configured": True, "ok": False, "detail": f"Groq returned HTTP {r.status_code}"}

    def check_gemini() -> dict:
        status = config.key_status("GEMINI_API_KEY")
        if status != "set":
            return {"configured": False, "ok": False, "detail": f"GEMINI_API_KEY is {status}"}
        try:
            r = requests.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                headers={"x-goog-api-key": config.GEMINI_API_KEY},
                params={"pageSize": 1},
                timeout=15,
            )
        except requests.RequestException as exc:
            return {"configured": True, "ok": False, "detail": f"Could not reach Gemini: {exc.__class__.__name__}"}
        if r.status_code == 200:
            return {"configured": True, "ok": True, "detail": "key accepted"}
        if r.status_code in (400, 401, 403):
            return {"configured": True, "ok": False, "detail": f"Gemini rejected the key (HTTP {r.status_code}) - create a new one at aistudio.google.com/apikey"}
        return {"configured": True, "ok": False, "detail": f"Gemini returned HTTP {r.status_code}"}

    groq_result = await run_in_threadpool(check_groq)
    gemini_result = await run_in_threadpool(check_gemini)
    return {"providers": {"groq": groq_result, "gemini": gemini_result}}


# Serve the frontend from the same server -> same origin, no CORS / localhost
# / 127.0.0.1 problems, and only one terminal to run. Registered LAST so it
# never shadows the API routes above.
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
