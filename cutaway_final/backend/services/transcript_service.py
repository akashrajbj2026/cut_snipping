"""Transcription: Groq's hosted Whisper, or faster-whisper running locally."""

import os
import subprocess

import requests

import config

GROQ_TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

_local_model = None


def extract_audio(video_path: str, audio_path: str) -> None:
    """Mono 16kHz, compressed to MP3 - not raw WAV.

    Raw 16kHz mono WAV runs about 1.9MB per minute, so anything past ~13
    minutes already blows past Groq's hard 25MB upload cap. A 32kbps mono
    MP3 runs about 0.24MB per minute instead - roughly 8x smaller, comfortably
    under the cap for a full hour of audio - while Whisper barely notices
    the extra compression.
    """
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-ac", "1", "-ar", "16000",
            "-c:a", "libmp3lame", "-b:a", "32k",
            audio_path,
        ],
        check=True,
        capture_output=True,
    )


def transcribe(video_path: str, workdir: str) -> list[dict]:
    """Returns [{"start": float, "end": float, "text": str}, ...]."""
    audio_path = os.path.join(workdir, "audio.mp3")
    extract_audio(video_path, audio_path)

    size_mb = os.path.getsize(audio_path) / (1024 * 1024)
    fits_groq = size_mb <= config.GROQ_MAX_AUDIO_MB

    if config.TRANSCRIPT_PROVIDER == "groq" and config.GROQ_API_KEY and fits_groq:
        try:
            return _transcribe_groq(audio_path)
        except Exception as groq_exc:
            # Hosted transcription failed — try the local model, but NEVER hide
            # why Groq failed. On small hosts (Render) faster-whisper is not
            # installed, and the old code then reported a misleading
            # "install faster-whisper" error instead of the real Groq problem.
            print(f"[transcribe] Groq Whisper failed: {groq_exc}")
            try:
                return _transcribe_local(audio_path)
            except Exception as local_exc:
                raise RuntimeError(
                    f"Groq transcription failed ({groq_exc}) and the local fallback is unavailable ({local_exc})"
                ) from groq_exc

    # Either local-only by config, no key, or the audio is still too big for
    # Groq even compressed (a very long video) - go straight to local instead
    # of making a request we already know Groq will reject.
    return _transcribe_local(audio_path)


def _transcribe_groq(audio_path: str) -> list[dict]:
    with open(audio_path, "rb") as f:
        resp = requests.post(
            GROQ_TRANSCRIBE_URL,
            headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
            files={"file": (os.path.basename(audio_path), f, "audio/mpeg")},
            data={
                "model": config.GROQ_WHISPER_MODEL,
                "response_format": "verbose_json",
                "timestamp_granularities[]": "segment",
            },
            timeout=600,
        )
    if resp.status_code == 401:
        raise RuntimeError("Groq rejected GROQ_API_KEY (HTTP 401) - the key is wrong, revoked, or has extra characters")
    if resp.status_code == 429:
        raise RuntimeError("Groq rate limit reached (HTTP 429) - wait a minute and retry")
    if not resp.ok:
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            detail = resp.text[:300]
        raise RuntimeError(f"Groq transcription HTTP {resp.status_code}: {detail or 'request failed'}")
    data = resp.json()

    return [
        {
            "start": float(seg["start"]),
            "end": float(seg["end"]),
            "text": seg["text"].strip(),
        }
        for seg in data.get("segments", [])
    ]


def _transcribe_local(audio_path: str) -> list[dict]:
    global _local_model
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError(
            "Transcription needs either a working GROQ_API_KEY or the optional local model. "
            "Set GROQ_API_KEY in backend/.env, or run: pip install faster-whisper"
        ) from exc

    if _local_model is None:
        _local_model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")

    segments, _info = _local_model.transcribe(audio_path, beam_size=5)
    return [
        {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
        for seg in segments
    ]


def group_into_chunks(transcript: list[dict], target_seconds: int | None = None) -> list[dict]:
    """Merge whisper's short segments into coarser, more meaningful chunks."""
    target_seconds = target_seconds or config.CHUNK_TARGET_SECONDS
    chunks: list[dict] = []
    current = {"start": None, "end": None, "text": ""}

    for seg in transcript:
        if current["start"] is None:
            current["start"] = seg["start"]
        current["end"] = seg["end"]
        current["text"] += " " + seg["text"]

        if current["end"] - current["start"] >= target_seconds:
            current["text"] = current["text"].strip()
            chunks.append(current)
            current = {"start": None, "end": None, "text": ""}

    if current["text"].strip():
        current["text"] = current["text"].strip()
        chunks.append(current)

    return chunks
