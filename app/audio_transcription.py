from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, UploadFile


AUDIO_TRANSCRIPTION_MAX_FILE_BYTES = 25 * 1024 * 1024
DEFAULT_AUDIO_PROVIDER_ORDER = (
    "groq",
    "openai",
    "openrouter",
    "gemini",
    "cerebras",
    "sambanova",
    "fireworks",
    "edenai",
)


@dataclass(frozen=True)
class AudioTranscriptionRequestData:
    model: str
    file_bytes: bytes
    filename: str
    content_type: str
    provider: str | None = None
    language: str | None = None
    prompt: str | None = None

    @property
    def size_bytes(self) -> int:
        return len(self.file_bytes)


async def build_audio_transcription_request(
    file: UploadFile | None,
    model: str | None,
    provider: str | None = None,
    language: str | None = None,
    prompt: str | None = None,
) -> AudioTranscriptionRequestData:
    cleaned_model = str(model or "").strip()
    if not file:
        raise HTTPException(status_code=400, detail="file is required")
    if not cleaned_model:
        raise HTTPException(status_code=400, detail="model is required")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="file is empty")
    if len(file_bytes) > AUDIO_TRANSCRIPTION_MAX_FILE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"file is too large; max size is {AUDIO_TRANSCRIPTION_MAX_FILE_BYTES} bytes",
        )

    filename = str(file.filename or "audio.bin").strip() or "audio.bin"
    content_type = str(file.content_type or "application/octet-stream").strip() or "application/octet-stream"
    cleaned_provider = str(provider or "").strip() or None
    cleaned_language = str(language or "").strip() or None
    cleaned_prompt = str(prompt or "").strip() or None

    return AudioTranscriptionRequestData(
        model=cleaned_model,
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
        provider=cleaned_provider,
        language=cleaned_language,
        prompt=cleaned_prompt,
    )


def select_audio_provider(requested_provider: str | None, available_providers: list[str]) -> str:
    if not available_providers:
        raise ValueError("No providers are configured")

    if requested_provider:
        if requested_provider not in available_providers:
            raise ValueError(f"Provider '{requested_provider}' is not configured")
        return requested_provider

    for provider_name in DEFAULT_AUDIO_PROVIDER_ORDER:
        if provider_name in available_providers:
            return provider_name
    return available_providers[0]


def normalize_audio_transcription_response(payload: Any) -> dict[str, Any]:
    text = _find_transcription_text(payload)
    if not text:
        raise ValueError("Upstream transcription response does not contain recognized text")
    normalized = {"text": text}
    if isinstance(payload, dict):
        normalized["_upstream"] = payload
    else:
        normalized["_upstream"] = {"raw": payload}
    return normalized


def _find_transcription_text(payload: Any) -> str | None:
    if isinstance(payload, str):
        cleaned = payload.strip()
        return cleaned or None

    if isinstance(payload, dict):
        for key in ("text", "transcript", "output_text"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            extracted = _find_transcription_text(value)
            if extracted:
                return extracted
        return None

    if isinstance(payload, list):
        for item in payload:
            extracted = _find_transcription_text(item)
            if extracted:
                return extracted
        return None

    return None
