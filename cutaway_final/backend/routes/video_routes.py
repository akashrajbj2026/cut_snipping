"""HTTP routes. The frontend contract is unchanged from the Groq-only version."""

import os
import shutil
import traceback
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse

import config
from providers import PROVIDERS, configured_providers
from services import video_analyzer, video_editor

router = APIRouter()

JOBS: dict[str, dict] = {}


@router.get("/providers")
async def list_providers():
    """Which providers exist, which are actually usable right now."""
    ready = configured_providers()
    return {
        "primary": config.PRIMARY_PROVIDER,
        "fallbacks": config.FALLBACK_PROVIDERS,
        "providers": [
            {
                "name": name,
                "accepts_video": provider.accepts_video,
                "needs_transcript": provider.needs_transcript,
                "configured": name in ready,
            }
            for name, provider in PROVIDERS.items()
        ],
    }


@router.post("/upload")
async def upload(file: UploadFile | None = File(None), url: str | None = Form(None)):
    job_id = str(uuid.uuid4())
    workdir = os.path.join(config.JOBS_DIR, job_id)
    os.makedirs(workdir, exist_ok=True)
    video_path = os.path.join(workdir, "input.mp4")

    if file is not None:
        # This copy is the #1 reason a big upload dies with "Failed to
        # fetch": it used to run synchronously right here, which freezes
        # uvicorn's single event loop for as long as the copy takes - no
        # other request (including this one's own keep-alive) gets served
        # in the meantime, and the browser eventually gives up on the
        # connection. Running it in a worker thread keeps the event loop
        # free the whole time.
        def _save() -> None:
            with open(video_path, "wb") as f:
                shutil.copyfileobj(file.file, f, length=1024 * 1024)

        try:
            await run_in_threadpool(_save)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Could not save the upload: {exc}")
    elif url:
        try:
            await run_in_threadpool(video_editor.download_from_url, url, video_path)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not fetch that link: {exc}")
    else:
        raise HTTPException(status_code=400, detail="Provide either a file or a url.")

    JOBS[job_id] = {"status": "uploaded", "video_path": video_path, "workdir": workdir}
    return {"job_id": job_id}


@router.post("/generate")
async def generate(
    bg: BackgroundTasks,
    job_id: str = Form(...),
    interest: str = Form(...),
    provider: str | None = Form(None),
):
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    JOBS[job_id]["status"] = "processing"
    JOBS[job_id]["interest"] = interest
    bg.add_task(run_job, job_id, interest, provider)
    return {"status": "processing"}


def run_job(job_id: str, interest: str, provider: str | None = None) -> None:
    job = JOBS[job_id]
    try:
        result = video_analyzer.generate_cut(
            job["video_path"], interest, job["workdir"], provider,
            progress=lambda msg: job.update(progress=msg),
        )
        job.update(status="done", **result)
    except Exception as exc:
        print(f"\n[job {job_id}] FAILED: {exc}\n")
        traceback.print_exc()
        job.update(status="error", error=str(exc))


@router.get("/status/{job_id}")
async def status(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")

    payload = {"status": job["status"]}
    if job["status"] == "processing" and job.get("progress"):
        payload["progress"] = job["progress"]
    if job["status"] == "done":
        payload.update(
            provider=job.get("provider"),
            segments=job.get("segments", []),
            warnings=job.get("warnings", []),
            original_duration=job.get("original_duration"),
            cut_duration=job.get("cut_duration"),
        )
    elif job["status"] == "error":
        payload["error"] = job.get("error")
    return payload


@router.get("/result/{job_id}")
async def result(job_id: str):
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job_id")
    if job.get("status") != "done":
        raise HTTPException(status_code=409, detail="Job is not finished yet")
    return FileResponse(job["output_path"], media_type="video/mp4", filename="cut.mp4")
