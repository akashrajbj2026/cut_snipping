"""Gemini provider — the only one here that reads the whole video natively.

Uploads the file through the Gemini Files API, waits for it to finish
processing, then asks for timestamped ranges matching the viewer's interest.
"""

import time

import config
from providers.base import AnalysisResult, BaseProvider, ProviderError, build_segment_prompt


class GeminiProvider(BaseProvider):
    name = "gemini"
    accepts_video = True
    needs_transcript = False

    def is_configured(self) -> bool:
        return bool(config.GEMINI_API_KEY)

    def analyze(self, video_path: str, interest: str, transcript: list[dict] | None = None) -> AnalysisResult:
        if not self.is_configured():
            raise ProviderError("GEMINI_API_KEY is not set")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ProviderError("google-genai is not installed (pip install google-genai)") from exc

        # A short HTTP timeout is the most common reason this works on a
        # 2-minute test clip and then silently dies on a real-length video:
        # the request is still fine, it just needs longer to finish.
        client = genai.Client(
            api_key=config.GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=config.GEMINI_REQUEST_TIMEOUT_MS),
        )
        warnings: list[str] = []

        try:
            uploaded = client.files.upload(file=video_path)
        except Exception as exc:
            message = str(exc)
            if "401" in message or "api key" in message.lower() or "unauthenticated" in message.lower():
                raise ProviderError("Gemini rejected GEMINI_API_KEY. Check that it is a real, active key from https://aistudio.google.com/apikey and restart the backend.") from exc
            raise ProviderError(f"Gemini upload failed: {message}") from exc

        # The Files API processes video asynchronously; poll until it is ACTIVE.
        deadline = time.time() + config.GEMINI_PROCESSING_TIMEOUT_SECONDS
        while getattr(uploaded.state, "name", uploaded.state) == "PROCESSING":
            if time.time() > deadline:
                raise ProviderError("Gemini took too long to process the video")
            time.sleep(5)
            uploaded = client.files.get(name=uploaded.name)

        state = str(getattr(uploaded.state, "name", uploaded.state)).upper()
        if state == "FAILED":
            raise ProviderError("Gemini failed to process the uploaded video. Try a smaller MP4 (H.264/AAC) or use the Groq transcript fallback.")
        if state not in {"ACTIVE", "STATE_UNSPECIFIED", ""}:
            raise ProviderError(f"Gemini file processing ended in unexpected state: {state}")

        prompt = build_segment_prompt(interest)
        if transcript:
            from providers.base import format_transcript

            prompt += "\n\nA transcript is available for reference:\n" + format_transcript(transcript)

        try:
            raw_text = self._generate_with_retry(client, types, uploaded, prompt, warnings)
        finally:
            # Don't leave uploaded videos sitting in the account's file store.
            try:
                client.files.delete(name=uploaded.name)
            except Exception:
                warnings.append("Could not delete the uploaded file from Gemini")

        from providers.base import parse_segments

        segments = parse_segments(raw_text, self.name)
        return AnalysisResult(
            provider=self.name,
            segments=segments,
            transcript=transcript,
            warnings=warnings,
        )

    @staticmethod
    def _is_transient(exc: Exception) -> bool:
        text = str(exc).lower()
        return any(k in text for k in ("503", "unavailable", "overloaded", "429", "resource_exhausted", "high demand", "timed out", "timeout"))

    @staticmethod
    def _is_model_unavailable(exc: Exception) -> bool:
        """Model retired / renamed / not offered to this account -> try the next model."""
        text = str(exc).lower()
        return "404" in text or "not_found" in text or "no longer available" in text or "is not found" in text

    def _generate_with_retry(self, client, types, uploaded, prompt, warnings) -> str:
        """Retry overloaded/rate-limited calls, then fall back to other models.

        The video is uploaded only once; only the text request is repeated.
        """
        models = [config.GEMINI_MODEL] + [m for m in config.GEMINI_FALLBACK_MODELS if m != config.GEMINI_MODEL]
        last_exc: Exception | None = None

        for model in models:
            for attempt in range(config.GEMINI_RETRIES_PER_MODEL):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=[uploaded, prompt],
                        config=types.GenerateContentConfig(
                            http_options=types.HttpOptions(timeout=config.GEMINI_REQUEST_TIMEOUT_MS),
                        ),
                    )
                    if model != config.GEMINI_MODEL:
                        warnings.append(f"Used fallback model {model} ({config.GEMINI_MODEL} was busy)")
                    return response.text
                except Exception as exc:
                    last_exc = exc
                    if self._is_model_unavailable(exc):
                        print(f"[gemini] {model} is not available to this key - trying next model")
                        warnings.append(f"Model {model} is unavailable (retired?) - skipped")
                        break
                    if not self._is_transient(exc):
                        raise  # a real error (bad key, bad model name...) - don't hammer it
                    wait = 15 * (2 ** attempt)
                    print(f"[gemini] {model} busy ({str(exc)[:80]}...) - attempt {attempt + 1}, waiting {wait}s")
                    if attempt < config.GEMINI_RETRIES_PER_MODEL - 1:
                        time.sleep(wait)
            print(f"[gemini] {model} still unavailable, trying next model")

        raise ProviderError(f"Gemini is overloaded on every model tried ({', '.join(models)}): {last_exc}")
