"""Validation and merging of timestamp ranges, whichever provider produced them."""

import config


def validate(segments: list[dict], duration: float) -> list[dict]:
    """Drop impossible ranges and clamp the rest inside the video."""
    valid = []
    for seg in segments:
        start = max(0.0, float(seg["start"]))
        end = float(seg["end"])

        if duration > 0:
            start = min(start, duration)
            end = min(end, duration)

        if end - start < 0.5:  # too short to be a usable cut
            continue

        new_seg = dict(seg)
        new_seg["start"] = start
        new_seg["end"] = end
        valid.append(new_seg)

    valid.sort(key=lambda s: s["start"])
    return valid


def filter_by_confidence(segments: list[dict], minimum: float | None = None) -> list[dict]:
    minimum = config.MIN_CONFIDENCE if minimum is None else minimum
    if minimum <= 0:
        return segments
    return [s for s in segments if s.get("confidence", 1.0) >= minimum]


def merge_and_pad(
    segments: list[dict],
    gap_threshold: float | None = None,
    pad: float | None = None,
    duration: float = 0.0,
) -> list[dict]:
    """Merge overlapping or near-adjacent ranges, then pad each one slightly."""
    gap_threshold = config.MERGE_GAP_THRESHOLD if gap_threshold is None else gap_threshold
    pad = config.SEGMENT_PAD_SECONDS if pad is None else pad

    if not segments:
        return []

    ordered = sorted(segments, key=lambda s: s["start"])
    merged = [dict(ordered[0])]

    for seg in ordered[1:]:
        last = merged[-1]
        if seg["start"] - last["end"] <= gap_threshold:
            last["end"] = max(last["end"], seg["end"])
            if seg.get("reason") and seg["reason"] not in last.get("reason", ""):
                last["reason"] = f"{last.get('reason', '')} / {seg['reason']}".strip(" /")
            last["confidence"] = max(last.get("confidence", 0), seg.get("confidence", 0))
        else:
            merged.append(dict(seg))

    for seg in merged:
        seg["start"] = max(0.0, seg["start"] - pad)
        seg["end"] = seg["end"] + pad
        if duration > 0:
            seg["end"] = min(seg["end"], duration)

    return merged


def total_kept_seconds(segments: list[dict]) -> float:
    return sum(seg["end"] - seg["start"] for seg in segments)
