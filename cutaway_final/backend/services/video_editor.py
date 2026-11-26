"""ffmpeg work: fetching, cutting, bridging and stitching."""

import os
import subprocess


def download_from_url(url: str, out_path: str) -> None:
    """Fetch a remote video with yt-dlp (YouTube and most other sites)."""
    import shutil
    if shutil.which("yt-dlp") is None:
        raise RuntimeError("yt-dlp is not installed. Run: pip install yt-dlp")
    proc = subprocess.run(
        [
            "yt-dlp", "--no-playlist", "-f", "bv*+ba/b",
            "--merge-output-format", "mp4", "-o", out_path, url,
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not os.path.isfile(out_path):
        tail = (proc.stderr or proc.stdout or "").strip()[-400:]
        raise RuntimeError(tail or "yt-dlp could not download that link")


def _run_ffmpeg(cmd: list[str], what: str) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is not installed or not on PATH. Install it and restart the backend.") from exc
    except subprocess.CalledProcessError as exc:
        tail = (exc.stderr or b"").decode("utf-8", "ignore")[-500:]
        raise RuntimeError(f"FFmpeg failed while {what}: {tail}") from exc


def cut_segment(input_path: str, start: float, end: float, out_path: str) -> None:
    duration = end - start
    _run_ffmpeg([
            "ffmpeg", "-y", "-ss", str(start), "-i", input_path,
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            # keep the aspect ratio (letterbox) instead of stretching to 16:9
            "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-r", "30",
            "-ar", "44100", "-ac", "2",
            out_path,
        ], "cutting a clip")


def make_analysis_chunk(input_path: str, start: float, duration: float, out_path: str) -> None:
    """Cut one part of the video for AI analysis only (never part of the output).

    Re-encoded small - max 480p, 2 fps, mono audio - because Gemini samples
    video at about 1 frame per second anyway. That makes each upload a few MB
    and the cut points frame-accurate, so timestamps line up exactly with the
    original once the chunk's start offset is added back.
    """
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", input_path,
                "-t", f"{duration:.3f}",
                "-vf", "scale=-2:'min(480,ih)'", "-r", "2",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                "-c:a", "aac", "-b:a", "64k", "-ac", "1", "-ar", "16000",
                out_path,
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        tail = (exc.stderr or b"").decode("utf-8", "ignore")[-600:]
        raise RuntimeError(f"ffmpeg could not cut an analysis chunk: {tail}") from exc


def make_bridge_clip(out_path: str, duration: float = 1.5, resolution: str = "1280x720") -> None:
    """A brief black flash between two kept segments, signaling a skip.

    No text overlay: FFmpeg's drawtext filter resolves fonts through
    fontconfig, and on many Windows FFmpeg builds that lookup crashes with
    an access violation (exit code 3221225477) instead of failing
    gracefully. A plain black flash needs no font at all, so it can never
    hit that bug, on any OS.
    """
    _run_ffmpeg([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=black:s={resolution}:d={duration}:r=30",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            "-ar", "44100", "-ac", "2",
            out_path,
        ], "making a transition")


def concat_clips(clip_paths: list[str], output_path: str, workdir: str) -> None:
    list_file = os.path.join(workdir, "concat_list.txt")
    with open(list_file, "w") as f:
        for p in clip_paths:
            f.write(f"file '{os.path.abspath(p)}'\n")

    _run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy",
         "-movflags", "+faststart", output_path], "stitching the clips together")


def build_cut(video_path: str, segments: list[dict], workdir: str, progress=None) -> str:
    """Cut kept ranges and stitch them, reporting progress while FFmpeg works.

    Re-encoding each clip is CPU-intensive, so callers need a live status message
    rather than appearing frozen at the frontend's 94% waiting indicator.
    """
    progress = progress or (lambda _msg: None)
    clip_paths: list[str] = []
    total = len(segments)

    for i, seg in enumerate(segments):
        progress(f"Rendering clip {i + 1}/{total}…")
        seg_path = os.path.join(workdir, f"seg_{i}.mp4")
        cut_segment(video_path, seg["start"], seg["end"], seg_path)
        clip_paths.append(seg_path)

        if i < total - 1:
            progress(f"Preparing transition {i + 1}/{total - 1}…")
            bridge_path = os.path.join(workdir, f"bridge_{i}.mp4")
            make_bridge_clip(bridge_path)
            clip_paths.append(bridge_path)

    output_path = os.path.join(workdir, "final_cut.mp4")
    progress("Stitching rendered clips into the final video…")
    concat_clips(clip_paths, output_path, workdir)

    if not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("FFmpeg finished without creating a valid output video.")
    progress("Final video ready.")
    return output_path
