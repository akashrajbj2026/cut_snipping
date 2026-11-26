"""Common provider interface.

Every provider returns the same normalized shape, so the cutting and merging
logic downstream never has to know which API produced the timestamps:

    {
      "provider": "gemini",
      "segments": [
        {"start": 32.4, "end": 91.8, "reason": "...", "confidence": 0.91}
      ],
      "transcript": [...] or None,
      "warnings": []
    }
"""

import json
import re
from dataclasses import dataclass, field


class ProviderError(RuntimeError):
    """Raised when a provider cannot produce a usable result."""


@dataclass
class AnalysisResult:
    provider: str
    segments: list[dict] = field(default_factory=list)
    transcript: list[dict] | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "segments": self.segments,
            "transcript": self.transcript,
            "warnings": self.warnings,
        }


class BaseProvider:
    """Interface all providers implement."""

    name: str = "base"

    # Does this provider accept the raw video file itself?
    accepts_video: bool = False
    # Does this provider need a transcript prepared for it beforehand?
    needs_transcript: bool = False

    def is_configured(self) -> bool:
        raise NotImplementedError

    def analyze(self, video_path: str, interest: str, transcript: list[dict] | None = None) -> AnalysisResult:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

SEGMENT_PROMPT = """A viewer wants to watch only the parts of this video relevant to: "{interest}"

Identify every time range that is genuinely relevant to that interest. Ignore
intros, sponsor reads, tangents and filler unless they are part of what the
viewer asked for. The speech may be in any language (for example Tamil or
Hindi): judge relevance by meaning in that language, including names,
abbreviations and nicknames, not just English keywords. Include the whole
stretch where the topic is being discussed, from where it starts to where the
speaker moves on.

Respond with ONLY a JSON array and nothing else — no prose, no code fences.
Each element must have:
  "start": seconds from the beginning of the video (number)
  "end": seconds from the beginning of the video (number)
  "reason": one short sentence explaining why this range is relevant
  "confidence": a number from 0 to 1

Example:
[{{"start": 32.4, "end": 91.8, "reason": "The speaker explains neural networks", "confidence": 0.91}}]

If nothing in the video is relevant, respond with an empty array: []"""


def build_segment_prompt(interest: str) -> str:
    return SEGMENT_PROMPT.format(interest=interest)


def format_transcript(transcript: list[dict]) -> str:
    return "\n".join(
        f"[{seg['start']:.1f}s-{seg['end']:.1f}s] {seg['text']}" for seg in transcript
    )


def parse_segments(raw_text: str, provider_name: str) -> list[dict]:
    """Pull a JSON array of segments out of a model response, tolerantly."""
    text = (raw_text or "").strip()

    # Strip code fences if the model added them despite instructions.
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    # Fall back to grabbing the outermost array if there is surrounding prose.
    if not text.startswith("["):
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            text = match.group(0)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ProviderError(f"{provider_name} returned unparseable JSON: {exc}") from exc

    if not isinstance(data, list):
        raise ProviderError(f"{provider_name} did not return a JSON array")

    return normalize_segments(data, provider_name)


def normalize_segments(data: list, provider_name: str) -> list[dict]:
    """Coerce whatever the model gave us into clean, sorted, valid segments."""
    segments = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            start = float(item.get("start", item.get("start_time", 0)))
            end = float(item.get("end", item.get("end_time", 0)))
        except (TypeError, ValueError):
            continue

        if end <= start:
            continue

        confidence = item.get("confidence", 1.0)
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 1.0

        segments.append(
            {
                "start": max(0.0, start),
                "end": end,
                "reason": str(item.get("reason", "") or ""),
                "confidence": min(max(confidence, 0.0), 1.0),
                "source": provider_name,
            }
        )

    segments.sort(key=lambda s: s["start"])
    return segments
