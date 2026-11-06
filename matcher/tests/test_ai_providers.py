"""
Tests for the AI providers. No test calls the real Gemini: the client is
replaced with a MagicMock that returns fixed replies or errors.
"""

from unittest.mock import MagicMock, patch

from django.test import override_settings
from google.genai import errors, types

from ..contracts.ai import AIProviderError
from ..managers.ai_providers import GeminiProvider
from .test_app import make_pdf_file, raises


def fake_client(*replies):
    """A Gemini client whose calls return these replies (text) or raise them (errors)."""
    client = MagicMock()
    client.models.generate_content.side_effect = [
        reply if isinstance(reply, Exception) else MagicMock(text=reply) for reply in replies
    ]
    return client


def using(client):
    """Make every GeminiProvider use this client instead of the real one."""
    return patch.object(GeminiProvider, "_get_client", return_value=client)


def gemini(*backups):
    return GeminiProvider(api_key="test", model="main", fallback_models=list(backups))


def busy_error():
    return errors.ServerError(503, {"error": {"code": 503, "message": "high demand"}})


def models_tried(client):
    return [c.kwargs["model"] for c in client.models.generate_content.call_args_list]


# ---------- GeminiProvider ----------

@override_settings(AI_API_KEY="from-env", AI_MODEL="main", AI_FALLBACK_MODELS=["backup"])
def test_gemini_uses_the_settings_unless_told_otherwise():
    assert GeminiProvider().models == ["main", "backup"]
    assert GeminiProvider(model="other", fallback_models=[]).models == ["other"]


def test_gemini_returns_the_reply_text():
    with using(fake_client('{"skills": []}')):
        assert gemini().generate(["hi"]) == '{"skills": []}'


def test_busy_model_falls_back_to_next_model():
    client = fake_client(busy_error(), "ok")
    with using(client):
        assert gemini("backup").generate(["hi"]) == "ok"
    assert models_tried(client) == ["main", "backup"]


def test_every_model_busy_raises_provider_error():
    client = fake_client(busy_error(), busy_error())
    with using(client):
        assert raises(AIProviderError, gemini("backup").generate, ["hi"])
    assert models_tried(client) == ["main", "backup"]


def test_bad_key_error_does_not_fall_back():
    client = fake_client(errors.ClientError(400, {"error": {"code": 400, "message": "API key not valid"}}))
    with using(client):
        assert raises(AIProviderError, gemini("backup").generate, ["hi"])
    assert models_tried(client) == ["main"]


def test_network_error_becomes_provider_error():
    with using(fake_client(ConnectionError("network down"))):
        assert raises(AIProviderError, gemini().generate, ["hi"])


def test_missing_api_key_gives_clear_error():
    try:
        GeminiProvider(api_key="").generate(["hi"])
    except AIProviderError as exc:
        assert "AI_API_KEY" in str(exc)
    else:
        raise AssertionError("expected AIProviderError")


def test_pdf_files_are_sent_as_pdf_parts():
    client = fake_client("ok")
    with using(client):
        gemini().generate(["Read this resume.", make_pdf_file()])

    text, pdf = client.models.generate_content.call_args.kwargs["contents"]
    assert text == "Read this resume."
    assert isinstance(pdf, types.Part) and pdf.inline_data.mime_type == "application/pdf"


def test_gemini_asks_for_json_at_temperature_0():
    client = fake_client("ok")
    with using(client):
        gemini().generate(["hi"])

    config = client.models.generate_content.call_args.kwargs["config"]
    assert config.response_mime_type == "application/json" and config.temperature == 0
