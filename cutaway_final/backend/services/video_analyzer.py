"""Orchestration: pick a provider, fall back if it fails, then build the cut."""

import os
import time

import config
from providers import ProviderError, get_provider
from services import scene_service, timestamp_service, transcript_service, video_editor


def _provider_chain(requested: str | None) -> list[str]:
    """Primary first, then the fallbacks, with duplicates removed."""
    chain = [requested or config.PRIMARY_PROVIDER]
    chain += config.FALLBACK_PROVIDERS

    seen = set()
    ordered = []
    for name in chain:
        name = (name or "").lower()
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _analyze_single(
    video_path: str,
    interest: str,
    workdir: str,
    requested_provider: str | None = None,
    allow_empty: bool = False,
) -> dict:
    """Run the provider chain until one returns usable segments.

    Returns the normalized result dict, with an extra "attempts" list showing
    what was tried and why each attempt failed.
    """
    chain = _provider_chain(requested_provider)
    transcript: list[dict] | None = None
    attempts: list[dict] = []
    warnings: list[str] = []

    for name in chain:
        try:
            provider = get_provider(name)
        except ProviderError as exc:
            attempts.append({"provider": name, "status": "skipped", "error": str(exc)})
            continue

        if not provider.is_configured():
            attempts.append(
                {"provider": name, "status": "skipped", "error": "No API key configured"}
            )
            continue

        # Transcribe once, lazily, and reuse it for every provider that needs it.
        if provider.needs_transcript and transcript is None:
            try:
                transcript = transcript_service.transcribe(video_path, workdir)
            except Exception as exc:
                attempts.append(
                    {"provider": name, "status": "skipped", "error": f"Transcription failed: {exc}"}
                )
                continue

        try:
            result = provider.analyze(video_path, interest, transcript)
        except Exception as exc:
            attempts.append({"provider": name, "status": "failed", "error": str(exc)})
            continue

        if result.transcript:
            transcript = result.transcript

        if not result.segments:
            attempts.append(
                {"provider": name, "status": "empty", "error": "No relevant segments found"}
            )
            warnings.extend(result.warnings)
            if allow_empty:
                # Chunk mode: "nothing relevant in this part" is a real answer.
                # Fallbacks are only for providers that FAIL, not ones that say no.
                return {
                    "provider": name,
                    "segments": [],
                    "transcript": None,
                    "warnings": warnings,
                    "attempts": attempts,
                }
            continue

        attempts.append({"provider": name, "status": "ok", "error": None})
        payload = result.to_dict()
        payload["warnings"] = warnings + payload["warnings"]
        payload["attempts"] = attempts
        return payload

    raise ProviderError(
        "No provider produced usable segments:\n"
        + "\n".join(
            f"- {a['provider']} ({a['status']}): {a['error'] or 'no details'}"
            for a in attempts
        )
    )


def _fmt(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def plan_chunks(duration: float) -> list[tuple[float, float]]:
    """Split [0, duration] into (start, end) analysis parts.

    Parts are ANALYSIS_CHUNK_MINUTES long and each runs CHUNK_OVERLAP_SECONDS
    into the next part. A tiny leftover tail (<60s) is folded into the last part.
    """
    size = config.ANALYSIS_CHUNK_MINUTES * 60
    if size <= 0 or duration <= size * 1.25:
        return [(0.0, duration)]

    overlap = config.CHUNK_OVERLAP_SECONDS
    chunks: list[tuple[float, float]] = []
    start = 0.0
    while start < duration - 1:
        end = min(start + size + overlap, duration)
        if duration - end < 60:
            end = duration
        chunks.append((start, end))
        if end >= duration:
            break
        start += size
    return chunks


_TRANSIENT = ("429", "resource_exhausted", "quota", "rate limit", "503", "unavailable", "overloaded", "timed out", "timeout")


def _analyze_part_with_retry(path, interest, workdir, provider, progress, label):
    """Retry a part when the failure looks like a free-tier rate limit or overload."""
    for attempt in range(config.CHUNK_MAX_RETRIES + 1):
        try:
            return _analyze_single(path, interest, workdir, provider, allow_empty=True)
        except ProviderError as exc:
            transient = any(k in str(exc).lower() for k in _TRANSIENT)
            if transient and attempt < config.CHUNK_MAX_RETRIES:
                progress(f"{label}: rate limited, retrying in {config.CHUNK_RETRY_WAIT_SECONDS}s…")
                time.sleep(config.CHUNK_RETRY_WAIT_SECONDS)
                continue
            raise


def analyze(
    video_path: str,
    interest: str,
    workdir: str,
    requested_provider: str | None = None,
    duration: float = 0.0,
    progress=None,
) -> dict:
    """Analyze the whole video, in parts if it is long.

    Short videos go straight through. Long ones are cut into ~10 minute parts,
    each part is analyzed on its own, and every timestamp is shifted by the
    part's start time so it lands on the original video's timeline.
    """
    progress = progress or (lambda _msg: None)
    chunks = plan_chunks(duration) if duration > 0 else [(0.0, 0.0)]

    if len(chunks) == 1:
        progress("Analyzing video…")
        return _analyze_single(video_path, interest, workdir, requested_provider)

    n = len(chunks)
    all_segments: list[dict] = []
    warnings: list[str] = [f"Long video: analyzed in {n} parts of about {config.ANALYSIS_CHUNK_MINUTES:g} min"]
    attempts: list[dict] = []
    providers_used: list[str] = []
    failures: list[str] = []

    for i, (start, end) in enumerate(chunks):
        label = f"Part {i + 1}/{n} ({_fmt(start)}-{_fmt(end)})"
        progress(f"{label}: preparing…")

        chunk_dir = os.path.join(workdir, f"chunk_{i}")
        os.makedirs(chunk_dir, exist_ok=True)
        chunk_path = os.path.join(chunk_dir, "part.mp4")

        try:
            video_editor.make_analysis_chunk(video_path, start, end - start, chunk_path)
            progress(f"{label}: analyzing…")
            payload = _analyze_part_with_retry(chunk_path, interest, chunk_dir, requested_provider, progress, label)
        except Exception as exc:
            print(f"[analyze] {label} failed: {exc}")
            failures.append(f"{label} failed: {exc}")
            continue
        finally:
            try:
                os.remove(chunk_path)  # free the disk space, only the timestamps matter
            except OSError:
                pass

        part_len = end - start
        for seg in payload["segments"]:
            s_start = max(0.0, float(seg["start"]))
            s_end = min(float(seg["end"]), part_len)  # stay inside this part
            if s_end - s_start < 0.5:
                continue
            shifted = dict(seg)
            shifted["start"] = s_start + start        # back onto the full timeline
            shifted["end"] = s_end + start
            all_segments.append(shifted)

        providers_used.append(payload["provider"])
        warnings.extend(payload.get("warnings", []))
        attempts.extend(payload.get("attempts", []))

    if len(failures) == n:
        raise ProviderError("Every part failed:\n" + "\n".join(f"- {f}" for f in failures))
    if failures:
        warnings.append(
            "Some parts could not be analyzed, so matches in them may be missing: "
            + "; ".join(failures)
        )

    all_segments.sort(key=lambda s: s["start"])
    return {
        "provider": "+".join(dict.fromkeys(providers_used)) or "none",
        "segments": all_segments,
        "transcript": None,
        "warnings": warnings,
        "attempts": attempts,
    }


def generate_cut(
    video_path: str,
    interest: str,
    workdir: str,
    requested_provider: str | None = None,
    progress=None,
) -> dict:
    """Full pipeline: analyze (in parts) -> validate -> merge -> cut -> stitch."""
    progress = progress or (lambda _msg: None)
    duration = scene_service.get_duration(video_path)
    analysis = analyze(video_path, interest, workdir, requested_provider, duration, progress)

    segments = analysis["segments"]
    segments = timestamp_service.filter_by_confidence(segments)
    segments = timestamp_service.validate(segments, duration)

    # Snap edges to real shot changes when PySceneDetect is available.
    progress("Finding scene boundaries…")
    progress("Detecting scene boundaries (this may take a little while)…")
    scenes = scene_service.detect_scenes(video_path)
    if scenes:
        segments = scene_service.snap_to_scenes(segments, scenes)

    # Overlapping parts can report the same moment twice; this merges them.
    segments = timestamp_service.merge_and_pad(segments, duration=duration)

    if not segments:
        raise ProviderError("Nothing in this video matched that interest")

    progress(f"Cutting and stitching {len(segments)} clip(s)…")
    output_path = video_editor.build_cut(video_path, segments, workdir, progress=progress)

    return {
        "output_path": output_path,
        "provider": analysis["provider"],
        "segments": segments,
        "warnings": analysis.get("warnings", []),
        "attempts": analysis.get("attempts", []),
        "original_duration": duration,
        "cut_duration": timestamp_service.total_kept_seconds(segments),
    }
