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

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_client():
    """Create the OpenRouter client. Only needed in live mode."""
    from openai import OpenAI

    if not settings.AI_API_KEY:
        raise RuntimeError("AI_MODE is 'live' but AI_API_KEY is not set in .env")
    return OpenAI(base_url=OPENROUTER_BASE_URL, api_key=settings.AI_API_KEY)


def ask_ai(prompt, uploaded_file):
    """Send a prompt (and later, the uploaded file's text) to the AI."""
    logger.info(
        "AI Manager received %s (%s, %s bytes)",
        uploaded_file.name,
        uploaded_file.content_type,
        uploaded_file.size,
    )

    if settings.AI_MODE != "live":
        # DATA: fixed mock reply
        return "PDF received"

    # TODO (Sprint 4): turn on the real call below, send the resume text
    # (from pdf_service.py) with the prompt, and validate the JSON reply.
    # client = get_client()
    # response = client.chat.completions.create(
    #     model="openrouter/free",
    #     messages=[{"role": "user", "content": prompt}],
    # )
    # return response.choices[0].message.content
    logger.info("AI live mode: API key set = %s", bool(settings.AI_API_KEY))
    return "PDF received"
