from __future__ import annotations

import base64
from dataclasses import dataclass

import requests


class GeminiError(RuntimeError):
    """Raised when Gemini API request fails."""


@dataclass(frozen=True)
class GeminiClient:
    api_key: str
    model: str
    timeout_seconds: int = 60

    def transcribe_wav(self, wav_bytes: bytes, prompt: str) -> str:
        if not wav_bytes:
            raise GeminiError("Audio payload is empty.")

        endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "audio/wav",
                                "data": base64.b64encode(wav_bytes).decode("ascii"),
                            }
                        },
                    ],
                }
            ]
        }

        try:
            response = requests.post(
                endpoint,
                params={"key": self.api_key},
                json=payload,
                timeout=self.timeout_seconds,
            )
        except requests.RequestException as exc:
            raise GeminiError(f"Gemini request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = ""
            try:
                detail = response.json().get("error", {}).get("message", "")
            except Exception:  # noqa: BLE001
                detail = response.text
            raise GeminiError(f"Gemini API error {response.status_code}: {detail}".strip())

        data = response.json()
        text = _extract_text(data)
        if not text:
            raise GeminiError("Gemini response did not contain transcript text.")
        return text.strip()


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        return ""
    for candidate in candidates:
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        if not isinstance(parts, list):
            continue
        chunks: list[str] = []
        for part in parts:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text)
        if chunks:
            return "\n".join(chunks)
    return ""

