"""Local video inspection: duration, sampled frames, scene boundaries.

None of this needs an API — it is ffmpeg/ffprobe and PySceneDetect.
"""

import base64
import glob
import os
import subprocess
import tempfile


def get_duration(video_path: str) -> float:
    """Video duration in seconds, via ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def extract_frames(video_path: str, interval: int = 20, max_frames: int = 20) -> list[dict]:
    """Sample one frame every `interval` seconds, returned as base64 JPEGs.

    Returns [{"timestamp": 20.0, "base64": "..."}, ...]
    """
    duration = get_duration(video_path)
    if duration <= 0:
        return []

    # Widen the interval if the video is long enough that max_frames would bite.
    if duration / interval > max_frames:
        interval = max(1, int(duration / max_frames))

    frames: list[dict] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        pattern = os.path.join(tmpdir, "frame_%04d.jpg")
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_path,
                "-vf", f"fps=1/{interval},scale=768:-1",
                "-frames:v", str(max_frames),
                "-q:v", "5",
                pattern,
            ],
            check=True,
            capture_output=True,
        )

        for i, path in enumerate(sorted(glob.glob(os.path.join(tmpdir, "frame_*.jpg")))):
            with open(path, "rb") as f:
                frames.append(
                    {
                        "timestamp": i * interval,
                        "base64": base64.b64encode(f.read()).decode("utf-8"),
                    }
                )

    return frames


def detect_scenes(video_path: str, threshold: float = 27.0) -> list[dict]:
    """Scene boundaries via PySceneDetect. Returns [] if it isn't installed.

    Useful for snapping cut points to real shot changes instead of mid-shot.
    """
    try:
        from scenedetect import ContentDetector, detect
    except ImportError:
        return []

    try:
        scene_list = detect(video_path, ContentDetector(threshold=threshold))
    except Exception:
        return []

    return [
        {"start": start.get_seconds(), "end": end.get_seconds()}
        for start, end in scene_list
    ]


def snap_to_scenes(segments: list[dict], scenes: list[dict], tolerance: float = 2.0) -> list[dict]:
    """Nudge segment edges onto nearby scene boundaries for cleaner cuts."""
    if not scenes:
        return segments

    boundaries = sorted({s["start"] for s in scenes} | {s["end"] for s in scenes})

    def nearest(value: float) -> float:
        candidate = min(boundaries, key=lambda b: abs(b - value))
        return candidate if abs(candidate - value) <= tolerance else value

    snapped = []
    for seg in segments:
        new_seg = dict(seg)
        new_seg["start"] = nearest(seg["start"])
        new_seg["end"] = nearest(seg["end"])
        if new_seg["end"] > new_seg["start"]:
            snapped.append(new_seg)
    return snapped
