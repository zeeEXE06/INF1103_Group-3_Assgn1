"""
AI Manager - talks to the AI API (Google Gemini, via the google-genai package).

Sprint 1-3: ask_ai() is wired up for testing. In mock mode it returns a
            fixed reply so the app works without an API key.
Sprint 4: build the prompt, call the AI, check the JSON reply, retry if
          it is broken, and log errors without crashing.

Settings (in .env, read by config/settings.py):
    AI_MODE    = "mock" (default, no key needed) or "live"
    AI_API_KEY = your free Gemini key from https://aistudio.google.com/apikey
                 (GEMINI_API_KEY also works)
    AI_MODEL   = Gemini model to use (default "gemini-3.8-flash")
    AI_FALLBACK_MODELS = comma-separated models to try if AI_MODEL is busy

No scoring or business logic here - that goes in logic_manager.py.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# DATA: fixed mock reply, shaped like a real resume extraction
MOCK_REPLY = json.dumps({
    "education": [{
        "qualification": "B.Sc.",
        "institution": "Sample University",
        "field_of_study": "Computer Science",
        "start_date": "2020",
        "end_date": "2024",
    }],
    "experience": [{
        "job_title": "Software Developer Intern",
        "company": "Sample Company",
        "start_date": "2023",
        "end_date": "2023",
    }],
    "skills": [{"skill": "Python"}, {"skill": "Django"}],
})

# DATA: fixed mock reply for the job title suggestions
MOCK_JOBS_REPLY = json.dumps({
    "jobs": [{
        "title": "Junior Python Developer",
        "industry": "Technology / IT",
        "matched_skills": ["Python", "Django"],
        "match_reason": "Uses the candidate's Python and Django skills.",
    }],
})


# Server-side errors worth retrying on the same model: server error, overloaded, timeout
RETRY_STATUS_CODES = [500, 503, 504]
# Errors that mean "try the next model". 429 = this model's quota is used up -
# retrying it only uses more quota, but each model has its own quota.
FALLBACK_STATUS_CODES = [429, *RETRY_STATUS_CODES]


def get_client():
    """Create the Gemini client. Only needed in live mode."""
    from google import genai
    from google.genai import types

    if not settings.AI_API_KEY:
        raise RuntimeError("AI_MODE is 'live' but AI_API_KEY is not set in .env")
    return genai.Client(
        api_key=settings.AI_API_KEY,
        http_options=types.HttpOptions(
            # Wait ~2s, then ~4s, before giving up on a model
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=2,
                max_delay=10,
                http_status_codes=RETRY_STATUS_CODES,
            ),
        ),
    )


def generate(contents, config):
    """Call Gemini, falling back to AI_FALLBACK_MODELS if a model is busy.

    Each model is retried a few times first (see get_client). Errors that are
    not temporary, like a bad API key, are raised straight away.
    """
    from google.genai import errors

    client = get_client()
    models = [settings.AI_MODEL, *settings.AI_FALLBACK_MODELS]

    for i, model in enumerate(models):
        try:
            response = client.models.generate_content(
                model=model, contents=contents, config=config,
            )
            return response.text
        except errors.APIError as exc:
            is_last = i == len(models) - 1
            if exc.code not in FALLBACK_STATUS_CODES or is_last:
                raise
            logger.warning("%s unavailable (%s), trying %s", model, exc.code, models[i + 1])


def ask_ai(prompt, uploaded_file):
    """Send a prompt and the uploaded PDF to the AI and return its reply."""
    logger.info(
        "AI Manager received %s (%s, %s bytes)",
        uploaded_file.name,
        uploaded_file.content_type,
        uploaded_file.size,
    )

    if settings.AI_MODE != "live":
        return MOCK_REPLY

    from google.genai import types

    # TODO (Sprint 4): retry if the JSON reply is broken.
    pdf_bytes = uploaded_file.read()

    return generate(
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ],
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )


def ask_ai_text(prompt):
    """Send a text-only prompt and return the AI's JSON reply."""
    if settings.AI_MODE != "live":
        return MOCK_JOBS_REPLY

    from google.genai import types

    return generate(
        contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json"),
    )


def parse_json_reply(reply):
    """Turn the AI's text reply into a dict. Returns None if it is not valid JSON."""
    text = (reply or "").strip()

    # Models often wrap JSON in ```json ... ``` - strip the fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Search replies sometimes add a sentence around the JSON - try just the {...} part
        start, end = text.find("{"), text.rfind("}")
        data = None
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        if data is None:
            logger.warning("AI reply is not valid JSON: %.200s", reply)
            return None

    if not isinstance(data, dict):
        logger.warning("AI reply is JSON but not an object: %.200s", reply)
        return None
    return data
