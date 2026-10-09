"""
Matching service - runs the AI Manager and Logic Manager together.

Sprint 1-2: not built yet.
Sprint 3/4: the views call one function here to get ranked results.
"""

import json
import logging
import re

from django.conf import settings
from django.utils import timezone

from ..managers.ai_manager import ask_ai_text, parse_json_reply
from ..managers.data_manager import load_records, save_record
from ..managers.io_manager import (
    INDUSTRY_CHOICES,
    LOCATION_CHOICES,
    WORK_ARRANGEMENT_CHOICES,
    WORKING_HOURS_CHOICES,
)

logger = logging.getLogger(__name__)

JOBSTREET_BASE_URL = "https://sg.jobstreet.com"

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


def jobstreet_search_url(title):
    """Jobstreet Singapore search page for a job title.

    e.g. "Junior Python Developer" -> https://sg.jobstreet.com/junior-python-developer-jobs
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{JOBSTREET_BASE_URL}/{slug}-jobs"


def choice_values(choices):
    """[("WFH", "Work From Home"), ...] -> ["WFH", ...] (skips the "" = all option)."""
    return [value for value, _label in choices if value]


def pick(value, choices):
    """Keep the AI's value only if it is one of the filter options, else ""."""
    return value if value in choice_values(choices) else ""


def to_score(value):
    """Turn the AI's match_score into a whole number from 0 to 100."""
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return 0


def match_jobs_to_resume(resume_id=None):
    """Ask the AI for job titles that suit a saved resume, and save them
    with a Jobstreet search link for each.

    Uses the newest saved resume unless resume_id is given. Returns the saved
    record, e.g. {"id": "J001", "resume_id": "R001", "jobs": [...]}.
    Raises ValueError if there is no resume or the AI reply is unreadable,
    and lets AI/API errors through for the caller to handle.
    """
    # DATA: all resumes saved by the job seeker upload
    resumes = load_records("resumes")
    if resume_id is not None:
        resumes = [r for r in resumes if r.get("id") == resume_id]
    if not resumes:
        raise ValueError(f"No saved resume found (resume_id={resume_id})")
    resume = resumes[-1]

    max_jobs = settings.MAX_JOBS
    prompt = JOB_TITLES_PROMPT.format(
        resume_json=json.dumps(
            {key: resume.get(key, []) for key in ("education", "experience", "skills")},
            indent=2,
        ),
        max_jobs=max_jobs,
        locations=", ".join(choice_values(LOCATION_CHOICES)),
        work_arrangements=", ".join(choice_values(WORK_ARRANGEMENT_CHOICES)),
        working_hours=", ".join(choice_values(WORKING_HOURS_CHOICES)),
        industries=", ".join(choice_values(INDUSTRY_CHOICES)),
    )

    reply = parse_json_reply(ask_ai_text(prompt))
    if reply is None or not isinstance(reply.get("jobs"), list):
        raise ValueError("AI job title reply is not in the expected JSON format")

    # DATA: suggested job titles with a Jobstreet search link, no duplicates,
    # best match first, capped at MAX_JOBS
    jobs = []
    seen_urls = set()
    for job in reply["jobs"]:
        title = str(job.get("title", "")).strip() if isinstance(job, dict) else ""
        if not title:
            continue
        url = jobstreet_search_url(title)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        jobs.append({
            "title": title,
            "url": url,
            "match_score": to_score(job.get("match_score")),
            "location": pick(job.get("location"), LOCATION_CHOICES),
            "work_arrangement": pick(job.get("work_arrangement"), WORK_ARRANGEMENT_CHOICES),
            "working_hours": pick(job.get("working_hours"), WORKING_HOURS_CHOICES),
            "industry": pick(job.get("industry"), INDUSTRY_CHOICES),
            "matched_skills": job.get("matched_skills", []),
            "match_reason": job.get("match_reason", ""),
        })
    jobs = sorted(jobs, key=lambda job: job["match_score"], reverse=True)[:max_jobs]

    return save_record("job_matches", {
        "resume_id": resume["id"],
        "searched_at": timezone.now().isoformat(timespec="seconds"),
        "jobs": jobs,
    })


# TODO (Sprint 3/4): match_candidates_to_job()
