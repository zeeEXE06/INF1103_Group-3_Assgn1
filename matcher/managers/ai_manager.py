"""
AI Manager - sends prompts and PDFs to Google Gemini and returns its JSON reply.

Settings (in .env):
    AI_MODE            "mock" (default, fixed replies, no key needed) or "live"
    AI_API_KEY         free Gemini key from https://aistudio.google.com/apikey
    AI_MODEL           Gemini model to use
    AI_FALLBACK_MODELS models to try, in order, if AI_MODEL is busy

No scoring or business logic here - that is the Logic Manager's job.
"""

import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

# Server errors worth retrying on the same model (server error, overloaded, timeout)
RETRY_STATUS_CODES = [500, 503, 504]
# Errors that move on to the next model. 429 = this model's quota is used up,
# and each model has its own quota.
FALLBACK_STATUS_CODES = [429, *RETRY_STATUS_CODES]
# Times to ask before giving up on a reply that is not valid JSON
JSON_ATTEMPTS = 2


# ---------- Gemini calls ----------

def get_client():
    """Create the Gemini client, retrying busy servers after ~2s and ~4s."""
    from google import genai
    from google.genai import types

    if not settings.AI_API_KEY:
        raise RuntimeError("AI_MODE is 'live' but AI_API_KEY is not set in .env")
    return genai.Client(
        api_key=settings.AI_API_KEY,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=3,
                initial_delay=2,
                max_delay=10,
                http_status_codes=RETRY_STATUS_CODES,
            ),
        ),
    )


def generate(contents, config):
    """Call Gemini, moving on to AI_FALLBACK_MODELS if a model is busy.

    Errors that waiting won't fix, like a bad API key, are raised straight away.
    """
    from google.genai import errors

    client = get_client()
    models = [settings.AI_MODEL, *settings.AI_FALLBACK_MODELS]

    for i, model in enumerate(models):
        try:
            response = client.models.generate_content(model=model, contents=contents, config=config)
            return response.text
        except errors.APIError as exc:
            is_last = i == len(models) - 1
            if exc.code not in FALLBACK_STATUS_CODES or is_last:
                raise
            logger.warning("%s unavailable (%s), trying %s", model, exc.code, models[i + 1])


def generate_json(contents, config):
    """Like generate(), but asks again if the reply is not valid JSON."""
    for attempt in range(1, JSON_ATTEMPTS + 1):
        reply = generate(contents, config)
        if parse_json_reply(reply) is not None:
            return reply
        if attempt < JSON_ATTEMPTS:
            logger.warning("AI reply was not valid JSON, asking again (attempt %s)", attempt + 1)
    return reply


def json_config():
    from google.genai import types

    return types.GenerateContentConfig(response_mime_type="application/json")


def pdf_part(uploaded_file):
    from google.genai import types

    return types.Part.from_bytes(data=uploaded_file.read(), mime_type="application/pdf")


def ask_ai(prompt, uploaded_file):
    """Send a prompt with one PDF and return the AI's JSON reply."""
    logger.info("AI Manager received %s (%s bytes)", uploaded_file.name, uploaded_file.size)
    if settings.AI_MODE != "live":
        return MOCK_RESUME_REPLY
    return generate_json([pdf_part(uploaded_file), prompt], json_config())


def ask_ai_text(prompt):
    """Send a text-only prompt and return the AI's JSON reply."""
    if settings.AI_MODE != "live":
        return MOCK_JOBS_REPLY
    return generate_json(prompt, json_config())


def ask_ai_with_pdfs(prompt, labelled_files):
    """Send a prompt with several PDFs in one request and return the JSON reply.

    labelled_files: [("JOB POSTING", job_file), ("RESUME 1", resume_file), ...].
    Each label is sent just before its PDF so the AI knows which file is which.
    """
    logger.info("AI Manager received %s PDFs", len(labelled_files))
    if settings.AI_MODE != "live":
        # The first file is the job posting, the rest are resumes
        return mock_comparison_reply(len(labelled_files) - 1)

    contents = [prompt]
    for label, uploaded_file in labelled_files:
        contents += [f"{label} ({uploaded_file.name}):", pdf_part(uploaded_file)]
    return generate_json(contents, json_config())


# ---------- Reading the reply ----------

def parse_json_reply(reply):
    """Turn the AI's text reply into a dict. Returns None if it is not valid JSON."""
    text = (reply or "").strip()

    # Models often wrap JSON in ```json ... ```
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        text = text.rsplit("```", 1)[0]

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Some replies add a sentence around the JSON - try just the {...} part
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


# ---------- Mock replies (AI_MODE=mock) ----------

MOCK_RESUME_REPLY = json.dumps({
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

MOCK_JOBS_REPLY = json.dumps({
    "jobs": [{
        "title": "Junior Python Developer",
        "match_score": 82,
        "location": "Central",
        "work_arrangement": "Hybrid",
        "working_hours": "Standard",
        "industry": "Technology / IT",
        "matched_skills": ["Python", "Django"],
        "match_reason": "Uses the candidate's Python and Django skills.",
    }],
})


def mock_comparison_reply(resume_count):
    """Mock employer comparison: one candidate per resume."""
    return json.dumps({
        "job": {
            "title": "Junior Python Developer",
            "company": "Sample Tech Pte Ltd",
            "required_skills": ["Python", "Django", "SQL"],
            "location": "Central",
            "work_arrangement": "Hybrid",
            "working_hours": "Standard",
            "industry": "Technology / IT",
        },
        "candidates": [mock_candidate(number) for number in range(1, resume_count + 1)],
    })


def mock_candidate(number):
    """Resume 1 is a strong match, resume 2 a partial match, the rest weak."""
    strong, partial = number == 1, number == 2
    if strong:
        matched, missing = ["Python", "Django", "SQL"], []
    elif partial:
        matched, missing = ["Python", "Django"], ["SQL"]
    else:
        matched, missing = ["Python"], ["Django", "SQL"]
    return {
        "resume_number": number,
        "name": f"Sample Candidate {number}",
        "matched_skills": matched,
        "missing_skills": missing,
        "experience": ["Software Developer, 3 years" if strong else "Intern, 6 months"],
        "education": ["B.Sc. Computer Science"],
        "location": "Central" if strong or partial else "West",
        "work_arrangement": "Hybrid",
        "working_hours": "Standard",
        "experience_match": strong,
        "education_match": True,
        "location_match": strong or partial,
        "work_arrangement_match": True,
        "working_hours_match": strong,
        "summary": f"Sample summary for candidate {number}.",
    }
