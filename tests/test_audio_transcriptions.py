from fastapi.testclient import TestClient

from app.audio_transcription import normalize_audio_transcription_response
from app.main import app


client = TestClient(app)


def test_audio_transcriptions_requires_file() -> None:
    response = client.post(
        "/v1/audio/transcriptions",
        data={"model": "whisper-large-v3-turbo", "provider": "groq"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "file is required"}


def test_audio_transcriptions_requires_model() -> None:
    response = client.post(
        "/v1/audio/transcriptions",
        files={"file": ("voice.ogg", b"fake-audio", "audio/ogg")},
        data={"provider": "groq"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "model is required"}


def test_audio_transcription_normalization_keeps_raw_upstream_without_proxy() -> None:
    payload = {
        "text": "привет мир",
        "x_groq": {"id": "abc"},
        "_proxy": {"selected_provider": "groq"},
    }

    normalized = normalize_audio_transcription_response(payload)

    assert normalized["text"] == "привет мир"
    assert normalized["_upstream"] == payload
