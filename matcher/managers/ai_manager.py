"""
AI Manager - builds the prompts, sends them to Google Gemini, and checks
that each reply has the expected JSON structure before returning it.

It never raises: if the AI fails or keeps replying in the wrong format, the
error is logged and None is returned.

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
# Times to ask before giving up on a reply in the wrong format
REPLY_ATTEMPTS = 2


# ---------- Prompts ----------

RESUME_PROMPT = """
Analyze the uploaded resume and extract the candidate's education,
experience and skills.

- Education: degrees, diplomas, certificates, fields of study, schools, dates.
- Experience: job titles, companies, dates of employment.
- Skills: every skill mentioned.

Return ONLY valid JSON in this format (use empty lists if nothing is found):

{
    "education": [
        {
            "qualification": "",
            "institution": "",
            "field_of_study": "",
            "start_date": "",
            "end_date": ""
        }
    ],
    "experience": [
        {
            "job_title": "",
            "company": "",
            "start_date": "",
            "end_date": ""
        }
    ],
    "skills": [
        {
            "skill": ""
        }
    ]
}

Do not invent information that is not present in the resume.
"""

JOB_TITLES_PROMPT = """
You are a career advisor in Singapore. Suggest job titles that suit the
candidate below, so they can search for them on Jobstreet.

Candidate resume (JSON):
{resume_json}

Rules:
- Suggest at most {max_jobs} job titles, best match first.
- match_score is a whole number from 0 to 100: how well the resume fits
  the job title's usual requirements (skills, experience, education).
- Use common job titles people actually search for on job sites,
  2-4 words each (e.g. "Junior Python Developer", "Data Analyst").
- No company names, no locations, no duplicate titles.
- matched_skills must only use skills from the resume.
- For location, work_arrangement, working_hours and industry, give what is
  most typical in Singapore for this job title. Use ONLY these values:
  location: {locations}
  work_arrangement: {work_arrangements}
  working_hours: {working_hours}
  industry: {industries}

Return ONLY valid JSON in this format:

{{
    "jobs": [
        {{
            "title": "",
            "match_score": 0,
            "location": "",
            "work_arrangement": "",
            "working_hours": "",
            "industry": "",
            "matched_skills": [""],
            "match_reason": ""
        }}
    ]
}}
"""

CANDIDATE_COMPARISON_PROMPT = """
You are helping an employer in Singapore screen candidates.

You will receive one JOB POSTING PDF, then {resume_count} resume PDFs
labelled RESUME 1 to RESUME {resume_count}. Compare EACH resume against the
job posting. Do not score or rank them - only report what matches.

Rules:
- Return exactly one candidate per resume, using its resume_number.
- matched_skills: skills the job asks for that the candidate has.
- missing_skills: skills the job asks for that the candidate does not have.
  Together they should cover all the job's required skills.
- experience_match: true if the candidate's experience meets what the job asks for.
- education_match: true if the candidate's education meets what the job asks for.
- location_match / work_arrangement_match / working_hours_match: true if
  the candidate's location / preference fits the job (true if the resume
  does not say, false only if it clearly does not fit).
- summary: one sentence on how well the candidate fits.
- If a PDF is not a readable resume, still return it with name "" and empty lists.
- Do not invent information that is not in the PDFs.
- For location, work_arrangement, working_hours and industry use ONLY these
  values (or "" if unknown):
  location: {locations}
  work_arrangement: {work_arrangements}
  working_hours: {working_hours}
  industry: {industries}

Return ONLY valid JSON in this format:

{{
    "job": {{
        "title": "",
        "company": "",
        "required_skills": [""],
        "location": "",
        "work_arrangement": "",
        "working_hours": "",
        "industry": ""
    }},
    "candidates": [
        {{
            "resume_number": 1,
            "name": "",
            "matched_skills": [""],
            "missing_skills": [""],
            "experience": ["Job title, X years"],
            "education": [""],
            "location": "",
            "work_arrangement": "",
            "working_hours": "",
            "experience_match": false,
            "education_match": false,
            "location_match": false,
            "work_arrangement_match": false,
            "working_hours_match": false,
            "summary": ""
        }}
    ]
}}
"""


# ---------- The three AI tasks ----------

def extract_resume(resume_file):
    """Read a resume PDF. Returns {"education", "experience", "skills"} or None."""
    logger.info("AI Manager reading %s (%s bytes)", resume_file.name, resume_file.size)
    return request_json(
        lambda: [pdf_part(resume_file), RESUME_PROMPT],
        resume_schema_problem,
        MOCK_RESUME_REPLY,
    )


def suggest_jobs(resume, max_jobs, options):
    """Suggest job titles for a saved resume. Returns {"jobs": [...]} or None.

    options: the allowed filter values, e.g. {"locations": "North, South, ..."}.
    """
    prompt = JOB_TITLES_PROMPT.format(
        resume_json=json.dumps(
            {key: resume.get(key, []) for key in ("education", "experience", "skills")},
            indent=2,
        ),
        max_jobs=max_jobs,
        **options,
    )
    return request_json(lambda: prompt, jobs_schema_problem, MOCK_JOBS_REPLY)


def compare_candidates(job_file, candidate_files, options):
    """Compare every resume with the job posting in one request.

    Returns {"job": {...}, "candidates": [...]} or None.
    """
    logger.info("AI Manager comparing %s resumes with %s", len(candidate_files), job_file.name)
    prompt = CANDIDATE_COMPARISON_PROMPT.format(resume_count=len(candidate_files), **options)

    def contents():
        parts = [prompt, f"JOB POSTING ({job_file.name}):", pdf_part(job_file)]
        for number, resume_file in enumerate(candidate_files, start=1):
            parts += [f"RESUME {number} ({resume_file.name}):", pdf_part(resume_file)]
        return parts

    return request_json(contents, comparison_schema_problem, mock_comparison_reply(len(candidate_files)))


# ---------- Asking Gemini ----------

def request_json(build_contents, schema_problem, mock_reply):
    """Ask the AI and return its reply as a dict, or None if it fails.

    A reply that is not JSON, or doesn't match the expected structure, is
    rejected and asked for again (up to REPLY_ATTEMPTS times).
    """
    for attempt in range(1, REPLY_ATTEMPTS + 1):
        if settings.AI_MODE != "live":
            reply = mock_reply
        else:
            try:
                reply = generate(build_contents(), json_config())
            except Exception:
                # Bad/missing API key, network down, every model busy, etc.
                logger.exception("AI request failed")
                return None

        data = parse_json_reply(reply)
        problem = "not valid JSON" if data is None else schema_problem(data)
        if problem is None:
            return data
        logger.warning("AI reply rejected (%s), attempt %s of %s", problem, attempt, REPLY_ATTEMPTS)
    return None


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


def json_config():
    """Ask for JSON, and temperature 0 so the same input gives the same answer."""
    from google.genai import types

    return types.GenerateContentConfig(response_mime_type="application/json", temperature=0)


def pdf_part(uploaded_file):
    from google.genai import types

    uploaded_file.seek(0)
    return types.Part.from_bytes(data=uploaded_file.read(), mime_type="application/pdf")


# ---------- Checking the reply ----------

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


def list_of_dicts_problem(data, key):
    """Return a problem if data[key] is not a list of objects, else None."""
    if not isinstance(data.get(key), list):
        return f'"{key}" is not a list'
    if not all(isinstance(item, dict) for item in data[key]):
        return f'"{key}" must only contain objects'
    return None


def resume_schema_problem(data):
    """Expected: {"education": [{...}], "experience": [{...}], "skills": [{...}]}"""
    for key in ("education", "experience", "skills"):
        problem = list_of_dicts_problem(data, key)
        if problem:
            return problem
    return None


def jobs_schema_problem(data):
    """Expected: {"jobs": [{"title": "...", ...}]}"""
    problem = list_of_dicts_problem(data, "jobs")
    if problem:
        return problem
    if not all(isinstance(job.get("title"), str) for job in data["jobs"]):
        return 'every job needs a "title" string'
    return None


def comparison_schema_problem(data):
    """Expected: {"job": {...}, "candidates": [{"resume_number": 1, ...}]}"""
    if not isinstance(data.get("job"), dict):
        return '"job" is not an object'
    problem = list_of_dicts_problem(data, "candidates")
    if problem:
        return problem
    for candidate in data["candidates"]:
        number = candidate.get("resume_number")
        if not isinstance(number, int) or isinstance(number, bool):
            return 'every candidate needs a whole-number "resume_number"'
    return None


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
