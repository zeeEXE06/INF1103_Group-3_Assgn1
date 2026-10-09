"""
AI Manager - talks to the AI API (OpenRouter, via the openai package).

Sprint 1-3: ask_ai() is wired up for testing. In mock mode it returns a
            fixed reply so the app works without an API key.
Sprint 4: build the prompt, call the AI, check the JSON reply, retry if
          it is broken, and log errors without crashing.

Settings (in .env, read by config/settings.py):
    AI_MODE    = "mock" (default, no key needed) or "live"
    AI_API_KEY = your OpenRouter key (OPENROUTER_API_KEY also works)

No scoring or business logic here - that goes in logic_manager.py.
"""

import base64
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

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


def get_client():
    """Create the OpenRouter client. Only needed in live mode."""
    from openai import OpenAI

    if not settings.AI_API_KEY:
        raise RuntimeError("AI_MODE is 'live' but AI_API_KEY is not set in .env")
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=settings.AI_API_KEY)


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

    # TODO (Sprint 4): retry if the JSON reply is broken.
    pdf_bytes = uploaded_file.read()
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

    client = get_client()
    response = client.chat.completions.create(
        model="openrouter/free",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "file",
                        "file": {
                            "filename": uploaded_file.name,
                            "file_data": "data:application/pdf;base64," + pdf_base64,
                        },
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content


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
        logger.warning("AI reply is not valid JSON: %.200s", reply)
        return None

    if not isinstance(data, dict):
        logger.warning("AI reply is JSON but not an object: %.200s", reply)
        return None
    return data
