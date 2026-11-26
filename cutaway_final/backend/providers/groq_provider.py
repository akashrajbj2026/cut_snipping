"""Groq provider — speech-based only.

Groq has no full-video understanding endpoint, so this provider searches the
transcript for relevant ranges. It is fast and cheap, and it is the right
fallback when the video's value is in what is said rather than what is shown.
"""

import time

import requests

import config
from providers.base import (
    AnalysisResult,
    BaseProvider,
    ProviderError,
    build_segment_prompt,
    format_transcript,
    parse_segments,
)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(BaseProvider):
    name = "groq"
    accepts_video = False
    needs_transcript = True

    def is_configured(self) -> bool:
        return bool(config.GROQ_API_KEY)

    # Groq's free tier caps tokens-per-minute, and a long transcript sent in one
    # request can be rejected outright (HTTP 413 / 429). So the transcript is sent
    # in windows of roughly this many characters, and the results are combined.
    WINDOW_CHARS = 9000

    @staticmethod
    def _windows(transcript: list[dict], max_chars: int) -> list[list[dict]]:
        windows: list[list[dict]] = []
        current: list[dict] = []
        size = 0
        for seg in transcript:
            line_len = len(seg.get("text", "")) + 24
            if current and size + line_len > max_chars:
                windows.append(current)
                current, size = [], 0
            current.append(seg)
            size += line_len
        if current:
            windows.append(current)
        return windows

    def _chat(self, prompt: str) -> str:
        """One Groq chat call with clear errors and a few polite 429 retries."""
        for attempt in range(4):
            resp = requests.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                json={
                    "model": config.GROQ_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                },
                timeout=120,
            )
            if resp.status_code == 429 and attempt < 3:
                try:
                    wait = float(resp.headers.get("retry-after", "") or 0)
                except ValueError:
                    wait = 0
                time.sleep(min(max(wait, 5 * (attempt + 1)), 30))
                continue
            break

        if resp.status_code == 401:
            raise ProviderError(
                "Groq rejected GROQ_API_KEY (HTTP 401). Check that it is a real, active key from https://console.groq.com/keys; restart/redeploy after changing it."
            )
        if resp.status_code == 403:
            raise ProviderError("Groq denied this request (HTTP 403). Check your account/model access.")
        if resp.status_code == 429:
            raise ProviderError("Groq rate limit/quota reached (HTTP 429). Wait for the limit to reset or use a different available provider.")
        if not resp.ok:
            try:
                detail = resp.json().get("error", {}).get("message", "")
            except (ValueError, AttributeError):
                detail = resp.text[:300]
            raise ProviderError(f"Groq API returned HTTP {resp.status_code}: {detail or 'request failed'}")

        try:
            return resp.json()["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Groq returned an unexpected response: {exc}") from exc

    def analyze(self, video_path: str, interest: str, transcript: list[dict] | None = None) -> AnalysisResult:
        if not self.is_configured():
            raise ProviderError("GROQ_API_KEY is not set")
        if not transcript:
            raise ProviderError("Groq needs a transcript and none was produced")

        segments: list[dict] = []
        for window in self._windows(transcript, self.WINDOW_CHARS):
            prompt = build_segment_prompt(interest)
            prompt += (
                "\n\nYou cannot see the video. Work only from this timestamped"
                " transcript, and keep your ranges inside the timestamps shown.\n\n"
            )
            prompt += format_transcript(window)
            segments.extend(parse_segments(self._chat(prompt), self.name))

        segments.sort(key=lambda s: s["start"])
        return AnalysisResult(
            provider=self.name,
            segments=segments,
            transcript=transcript,
            warnings=["Groq analyzed speech only — purely visual moments may be missed"],
        )
