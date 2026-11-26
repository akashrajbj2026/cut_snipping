"""Central configuration. Every secret comes from the environment."""

import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Only the real .env is read (local development). On Render / Docker there is
# no .env file - keys come from the host's Environment Variables, which always
# take precedence (override=False). .env.example is NEVER read: it only holds
# placeholders, and reading it used to make the app think a fake key was real.
load_dotenv(os.path.join(BASE_DIR, ".env"), override=False)

JOBS_DIR = os.path.join(BASE_DIR, "jobs")
os.makedirs(JOBS_DIR, exist_ok=True)

# --- Provider selection -----------------------------------------------------
# Only genuinely free-tier providers are wired up: Gemini (native video
# understanding, no credit card required) and Groq (fast, free, text/transcript
# only). Anthropic, Together AI and Twelve Labs were removed on purpose -
# none of them offer an ongoing free tier (see README.md).
PRIMARY_PROVIDER = os.getenv("PRIMARY_PROVIDER", "gemini").lower()
FALLBACK_PROVIDERS = [
    p.strip().lower()
    for p in os.getenv("FALLBACK_PROVIDERS", "groq").split(",")
    if p.strip()
]

# --- API keys (placeholders only; put real values in .env) ------------------
_PLACEHOLDERS = {
    "your_api_key", "your_api_key_here", "paste_key_here", "replace_me",
    "none", "null", "changeme", "xxx",
}


def _is_placeholder(value: str) -> bool:
    v = value.strip().lower()
    return (
        not v
        or v in _PLACEHOLDERS
        or v.startswith("your_")
        or v.startswith("paste")
        or v.endswith("_here")
        or v.endswith("_api_key")
    )


def _read_key(name: str) -> str:
    """Read a key, treating blank / example-placeholder values as absent.

    Also strips the quotes, spaces and stray newlines that commonly sneak in
    when a key is pasted into a dashboard (Render) or a .env file.
    """
    value = os.getenv(name, "")
    value = value.strip().strip('"').strip("'").strip()
    if name.upper() in value.upper() and "=" in value:
        # Someone pasted "GROQ_API_KEY=gsk_..." as the VALUE in the dashboard.
        value = value.split("=", 1)[1].strip().strip('"').strip("'").strip()
    return "" if _is_placeholder(value) else value


def key_status(name: str) -> str:
    """'missing' | 'placeholder' | 'set' - never reveals the key itself."""
    raw = os.getenv(name, "").strip().strip('"').strip("'").strip()
    if not raw:
        return "missing"
    return "placeholder" if _is_placeholder(raw) else "set"


GEMINI_API_KEY = _read_key("GEMINI_API_KEY")
GROQ_API_KEY = _read_key("GROQ_API_KEY")

# --- Model names ------------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
# Tried in order when the main model is overloaded (503) or rate limited (429).
GEMINI_FALLBACK_MODELS = [
    m.strip() for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite").split(",") if m.strip()
]
# Tries per model, waiting 15s, 30s, 60s... between tries.
GEMINI_RETRIES_PER_MODEL = int(os.getenv("GEMINI_RETRIES_PER_MODEL", "3"))
# NOTE: llama-3.3-70b-versatile was shut down by Groq on 2026-08-16 for
# free/developer-tier traffic. openai/gpt-oss-120b is their recommended,
# still-free replacement - do not switch this back to the old name.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")

# --- Transcription ----------------------------------------------------------
# "groq"  -> Groq's hosted Whisper endpoint (fast, needs GROQ_API_KEY)
# "local" -> faster-whisper running on this machine (no key, no network)
TRANSCRIPT_PROVIDER = os.getenv("TRANSCRIPT_PROVIDER", "groq").lower()
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "small")
# Groq's Whisper endpoint hard-rejects anything over 25MB, free tier or not.
# We compress to a low-bitrate mono MP3 before sending, but even that can
# cross this line on a long enough video - checked in transcript_service.py.
GROQ_MAX_AUDIO_MB = float(os.getenv("GROQ_MAX_AUDIO_MB", "24"))

# --- Long-video timeouts -----------------------------------------------------
# Gemini's Files API processes video asynchronously; bigger/longer videos
# take longer to go from PROCESSING to ACTIVE, and the generate_content call
# itself needs longer to think through a big video. Both are generous on
# purpose - a low timeout is the #1 cause of "it works on short clips, fails
# on long ones."
GEMINI_PROCESSING_TIMEOUT_SECONDS = int(os.getenv("GEMINI_PROCESSING_TIMEOUT_SECONDS", "1800"))
GEMINI_REQUEST_TIMEOUT_MS = int(os.getenv("GEMINI_REQUEST_TIMEOUT_MS", "900000"))

# --- Tunables ---------------------------------------------------------------
CHUNK_TARGET_SECONDS = int(os.getenv("CHUNK_TARGET_SECONDS", "25"))
FRAME_INTERVAL_SECONDS = int(os.getenv("FRAME_INTERVAL_SECONDS", "20"))
MAX_FRAMES = int(os.getenv("MAX_FRAMES", "20"))
MERGE_GAP_THRESHOLD = float(os.getenv("MERGE_GAP_THRESHOLD", "8.0"))
SEGMENT_PAD_SECONDS = float(os.getenv("SEGMENT_PAD_SECONDS", "1.0"))
MIN_CONFIDENCE = float(os.getenv("MIN_CONFIDENCE", "0.0"))

# --- Long-video chunking ----------------------------------------------------
# Videos longer than ~1.25x ANALYSIS_CHUNK_MINUTES are split into parts for
# analysis. Each part is sent to Gemini on its own, the timestamps are shifted
# back onto the full timeline, and the final cut is made from the ORIGINAL
# file. Set ANALYSIS_CHUNK_MINUTES=0 to turn chunking off.
ANALYSIS_CHUNK_MINUTES = float(os.getenv("ANALYSIS_CHUNK_MINUTES", "10"))
# Each part also includes this many seconds of the next part, so a sentence that
# straddles a boundary is never cut in half.
CHUNK_OVERLAP_SECONDS = float(os.getenv("CHUNK_OVERLAP_SECONDS", "15"))
# Free-tier rate limits (429) / overload (503) are retried per part.
CHUNK_MAX_RETRIES = int(os.getenv("CHUNK_MAX_RETRIES", "2"))
CHUNK_RETRY_WAIT_SECONDS = int(os.getenv("CHUNK_RETRY_WAIT_SECONDS", "30"))
