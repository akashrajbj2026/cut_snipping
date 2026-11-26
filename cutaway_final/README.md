# Cut Away

> **Frontend refresh:** the included UI is now a cinematic editor console with an animated 3D analysis core, source monitor, intent brief, cut map timeline, upload progress, and recovered-cut preview. It remains dependency-free and uses the existing FastAPI endpoints.


Cut Away is a small FastAPI + HTML/CSS/JavaScript app that lets you upload a video,
describe what you care about, and generate a shorter video containing only the
relevant time ranges.


## Quick run (one terminal, one server)

The backend now serves the website too, so you only run ONE command and open ONE address.

**Windows (VS Code terminal):**

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# open backend\.env and paste GEMINI_API_KEY and/or GROQ_API_KEY
uvicorn main:app --reload --port 8000
```

(After the first time, `backend\run_backend.bat` does all of this for you.)

**macOS / Linux:**

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # then add GEMINI_API_KEY / GROQ_API_KEY
uvicorn main:app --reload --port 8000
```

Then open **<http://127.0.0.1:8000>**. FFmpeg must be installed and on your PATH (`ffmpeg -version` should work). The page checks this and your API keys on load and shows a red banner if something is missing.

Optional heavy extras (offline Whisper, shot-change snapping): `pip install -r requirements-optional.txt`.

The old two-terminal setup (`cd frontend` then `python -m http.server 5500`) still works too; the page automatically talks to the backend on port 8000 of the same host.

### New UI flow

Import a local file or URL on the Source screen, describe the content to keep on the Intent screen, and start the scan. The animated Analysis Core and Cut Map reflect the active job while the existing `/status/{job_id}` polling runs. When the backend finishes, the result screen exposes the merged video preview and the existing `/result/{job_id}` download.

## Deploying on Render (and checking your keys)

1. Push this repo to GitHub, then Render -> **New -> Web Service** (or **Blueprint**, which reads `render.yaml`). Runtime: **Docker**.
2. Open the service -> **Environment** and add `GEMINI_API_KEY` and `GROQ_API_KEY`. Paste only the key, no quotes, no spaces, no `NAME=` prefix. Save -> Render redeploys.
3. Open `https://<your-service>.onrender.com/diagnose`. Each provider must show `"ok": true`. Anything else tells you exactly what is wrong (missing / rejected / unreachable).
4. The **Logs** tab prints `GEMINI_API_KEY : set|missing|placeholder` on every start.

Free Render instances sleep and restart, which wipes in-memory jobs - if a job says "Unknown job_id", just upload again. Downloading from YouTube links often fails from cloud IPs; upload files instead.

## Free-tier only

This version uses **only two AI providers, both genuinely free with no credit
card**:

| Provider | What it does here | Free tier |
|---|---|---|
| **Gemini** (Google AI Studio) | Watches the *whole video* natively and returns timestamps matching your interest | Yes — no card, no expiry ([aistudio.google.com/apikey](https://aistudio.google.com/apikey)) |
| **Groq** | Transcribes the audio (Whisper) and, if Gemini is unavailable, finds relevant ranges from the transcript alone | Yes — no card, rate-limited only ([console.groq.com/keys](https://console.groq.com/keys)) |

Anthropic (Claude), Together AI and Twelve Labs have been **removed**. None of
them has an ongoing free tier — Anthropic and Together AI charge per token
after a small one-time signup credit, and Twelve Labs' free allowance is a
one-time 10-hour indexing quota tied to a paid console setup. Keeping them out
means this project never asks you to enter a card or spend a credit.

If Groq's own transcription API is ever unreachable, the app automatically
falls back to `faster-whisper` running **locally on your machine** — a fully
open-source model that needs no API key and no internet connection at all.
That's the one part of this pipeline that works with zero API keys.

### Why not go 100% API-key-free?

Groq has no full-video-understanding endpoint (it only ever sees the audio
transcript, not the picture), and there is currently no other ongoing free
API that watches an entire video and returns timestamps. So the "see the
whole video" part of your request genuinely needs Gemini's free tier — there
isn't a way to do that with zero API keys and still identify *visual* moments
(not just spoken ones). Everything else — merging, cutting, re-encoding,
transcription fallback — runs 100% locally with open-source tools (ffmpeg,
faster-whisper, PySceneDetect) and needs no key at all.

## Project structure

```text
cutaway/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── providers/      # gemini_provider.py, groq_provider.py
│   ├── routes/
│   ├── services/
│   └── jobs/
└── frontend/
    ├── index.html
    ├── style.css
    └── script.js
```

## Step 1: Get your two free API keys

### Gemini API key (free, no card)

1. Go to <https://aistudio.google.com/apikey>.
2. Sign in with any Google account.
3. Click **Create API key**. No billing project or card is required for the
   free tier.
4. Copy the key — it starts with `AIza...`.

### Groq API key (free, no card)

1. Go to <https://console.groq.com/keys>.
2. Sign up / sign in.
3. Click **Create API Key**, name it anything, and copy it — it starts with
   `gsk_...`.
4. You are on the Free tier by default. Groq shows what your usage *would*
   cost on a paid tier, but on the Free tier you are simply rate-limited
   (HTTP 429) when you go over — never charged.

Both keys are free indefinitely for personal/hackathon-scale use. Neither
requires adding a payment method.

## Step 2: Prerequisites on Windows

Install:

1. Python 3.10 or newer.
2. FFmpeg, with both `ffmpeg` and `ffprobe` available on PATH.
3. Visual Studio Code.
4. The two API keys from Step 1.

Verify FFmpeg in a new terminal:

```powershell
ffmpeg -version
ffprobe -version
```

Verify Python:

```powershell
python --version
```

## Step 3: VS Code setup

Open the `cutaway` folder itself in VS Code, not just the ZIP file.

Open:

```text
Terminal -> New Terminal
```

Create and activate a virtual environment:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use Command Prompt instead:

```cmd
cd backend
venv\Scripts\activate.bat
```

Upgrade pip and install dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create your environment file:

```powershell
copy .env.example .env
```

Edit `backend/.env` and paste your two keys into `GEMINI_API_KEY` and
`GROQ_API_KEY`. Leave everything else at its default.

Then start the backend:

```powershell
uvicorn main:app --reload --port 8000
```

You should see a message that Uvicorn is running on:

```text
http://127.0.0.1:8000
```

Leave this terminal running.

## Step 4: Start the frontend

Open a second VS Code terminal:

```powershell
cd frontend
python -m http.server 5500
```

Open:

```text
http://127.0.0.1:5500
```

Do not double-click `index.html`; use the local HTTP server above (the page
calls the backend with `fetch`, which most browsers block from a bare
`file://` page).

## Step 5: First test

1. Open the frontend.
2. Choose a small MP4 first (1-5 minutes is ideal for the first test).
3. Click `Complete Upload`.
4. Enter an interest such as `the part where the speaker explains the pricing`.
5. Click `Generate my cut`.
6. Wait while Gemini analyzes the video and FFmpeg creates the cut.
7. Play the result.
8. Use `Download this cut` when it is ready.

Check the backend terminal if anything fails.

## API smoke tests

With the backend running, open:

```text
http://127.0.0.1:8000/health
```

Expected:

```json
{"status":"ok"}
```

Then open:

```text
http://127.0.0.1:8000/providers
```

You should see both `gemini` and `groq` listed, each marked `"configured":
true` once your `.env` keys are loaded.

## Turning this into a website

There are two very different things people mean by "get a website" — pick
the one that matches what you actually need:

### A) Just for a hackathon demo (fastest, still free)

Keep running the backend and frontend on your own laptop as above, then
expose the backend with a free tunnel (e.g. `ngrok http 8000`) so a judge or
teammate on another network can hit it. Point `API_BASE` in
`frontend/script.js` at the tunnel URL, then serve the frontend the same
way (or host that single static folder for free on GitHub Pages / Netlify /
Vercel). This costs nothing and takes a few minutes, but it only works
while your laptop and the tunnel are running.

### B) A real, always-on deployment

This needs two pieces hosted separately, because the frontend is static
files and the backend is a long-running Python process that shells out to
FFmpeg:

- **Frontend** (`frontend/` folder): any static host works — GitHub Pages,
  Netlify, Vercel, or Cloudflare Pages all have free tiers that are enough
  for three plain HTML/CSS/JS files.
- **Backend** (`backend/` folder): needs a host that runs a persistent
  Python process with FFmpeg available, not a serverless function (video
  cutting takes too long and produces files too large for most serverless
  free tiers). Render, Railway and Fly.io all currently offer a free or
  low-cost tier for a small FastAPI service — check each one's current free
  tier limits yourself before you rely on it, since these change often. Add
  a `Dockerfile` (or a build command that runs `apt-get install ffmpeg`)
  so FFmpeg is present on the server, and set `GEMINI_API_KEY` /
  `GROQ_API_KEY` as environment variables in that host's dashboard — never
  commit them to your repo.

After deploying the backend, update `API_BASE` in `frontend/script.js` to
its public URL, and add that same URL to the CORS `allow_origins` list in
`backend/main.py` (replace the current `"*"` with your frontend's real
domain before you ship this beyond a demo).

One honest caveat: free tiers on most of these hosts either sleep after
inactivity (slow first request) or cap request duration/RAM, and a long
video plus FFmpeg re-encoding is exactly the kind of workload that bumps
into those caps. For a hackathon demo, option A is the reliable choice;
treat option B as the next step once you're past judging.

## Common errors

### `ffmpeg is not recognized`

FFmpeg is not on PATH. Install FFmpeg, add its `bin` directory to PATH, close
and reopen VS Code, then run:

```powershell
ffmpeg -version
ffprobe -version
```

### `GEMINI_API_KEY is not set` / `GROQ_API_KEY is not set`

Make sure `backend/.env` exists (copied from `.env.example`) and contains
your real keys, with no quotes around them. Restart Uvicorn after changing
`.env` — it only reads the file on startup.

### `google-genai is not installed`

Activate the virtual environment and run:

```powershell
pip install -r requirements.txt
```

### The browser says `Failed to fetch`

On a **short** video this almost always just means a server isn't running:

```text
Backend:  http://127.0.0.1:8000
Frontend: http://127.0.0.1:5500
```

Check the browser console (F12) for more detail, and check the Uvicorn
terminal for a printed traceback.

On a **large** video specifically, this used to have a second cause: the
upload handler wrote the file to disk synchronously, which froze the entire
server for as long as the copy took and could drop the connection outright.
That's fixed — uploads now run in a worker thread so the server stays
responsive during a big copy. If you still see this on a large file after
updating, it's most likely just a slow connection; the upload progress bar
should still be climbing, not stuck at 0%.

### The job reaches `error`

Look at the terminal where Uvicorn is running. The backend stores job data
under `backend/jobs/<job-id>/`. The `/status/<job-id>` endpoint also returns
the backend error.

### Groq returns a model error mentioning `llama-3.3-70b-versatile`

Groq shut that model down for free/developer-tier traffic on 2026-08-16.
Make sure `GROQ_MODEL` in your `.env` is `openai/gpt-oss-120b` (the current
default in `.env.example`), not the old Llama name.

### Longer videos fail where short clips work fine

Three separate things used to bite on longer/bigger videos, all fixed now:

1. **Groq transcription almost always failed on anything past ~13 minutes.**
   Audio was being sent to Groq as raw 16kHz WAV, which runs about 1.9MB per
   minute — so a 20-minute video already blew past Groq's hard 25MB upload
   cap. Audio is now compressed to a 32kbps mono MP3 first (about 8x
   smaller), and if a video is long enough that even that crosses 25MB, the
   code skips the doomed Groq request entirely and goes straight to the
   local `faster-whisper` fallback instead of failing first.
2. **Gemini's processing timeout was a hard 10 minutes.** A long video can
   legitimately take longer than that just to finish uploading and
   processing on Gemini's side. This is now a configurable 30 minutes
   (`GEMINI_PROCESSING_TIMEOUT_SECONDS` in `.env`) — raise it further if
   you're regularly testing hour-plus videos.
3. **The upload itself could freeze the server on a big file** (see
   "Failed to fetch" above) — also fixed.

If a long video still fails after all this, check the Uvicorn terminal for
the actual error — it'll tell you which of the two providers failed and why.

### Gemini free-tier rate limit (HTTP 429)

The free tier is rate-limited per day and per minute, not metered by cost.
If you hit it, wait a bit and retry, or switch `TRANSCRIPT_PROVIDER=local`
and `PRIMARY_PROVIDER=groq` in `.env` temporarily to keep testing on the
transcript-only path while Gemini's quota resets.

## Notes

- `.env` is ignored by Git. Never commit API keys.
- `backend/jobs/` is ignored by Git.
- The first `faster-whisper` use may download its model (a few hundred MB,
  one time only, fully local afterward).
- Gemini's File API is intended for larger/longer video uploads.
- The frontend is intentionally dependency-free; there is no npm install
  step.
