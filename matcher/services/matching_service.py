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

from ..managers.ai_manager import ask_ai_text, ask_ai_with_pdfs, parse_json_reply
from ..managers.data_manager import load_records, save_record
from ..managers.logic_manager import calculate_score, is_strong_match
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


# ---------- Employer: compare resumes to one job posting ----------

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

MATCH_FIELDS = (
    "experience_match", "education_match", "location_match",
    "work_arrangement_match", "working_hours_match",
)


def as_list(value):
    """Keep a list of non-empty strings, whatever the AI sent."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def clean_candidate(ai_candidate, filename):
    """Turn one AI candidate into a saved candidate with its score."""
    candidate = {
        "filename": filename,
        "name": str(ai_candidate.get("name", "")).strip() or filename,
        "matched_skills": as_list(ai_candidate.get("matched_skills")),
        "missing_skills": as_list(ai_candidate.get("missing_skills")),
        "experience": as_list(ai_candidate.get("experience")),
        "education": as_list(ai_candidate.get("education")),
        "location": pick(ai_candidate.get("location"), LOCATION_CHOICES),
        "work_arrangement": pick(ai_candidate.get("work_arrangement"), WORK_ARRANGEMENT_CHOICES),
        "working_hours": pick(ai_candidate.get("working_hours"), WORKING_HOURS_CHOICES),
        "summary": str(ai_candidate.get("summary", "")).strip(),
        "unreadable": False,
        **{field: ai_candidate.get(field) is True for field in MATCH_FIELDS},
    }
    # Logic Manager decides the final score and the Strong Match label
    candidate["match_score"] = calculate_score(candidate)
    candidate["strong_match"] = is_strong_match(candidate)
    return candidate


def unreadable_candidate(filename):
    """Placeholder for a resume the AI did not return - shown last with 0%."""
    return {
        "filename": filename,
        "name": filename,
        "matched_skills": [], "missing_skills": [], "experience": [], "education": [],
        "location": "", "work_arrangement": "", "working_hours": "",
        "summary": "Could not read this resume.",
        "unreadable": True,
        **{field: False for field in MATCH_FIELDS},
        "match_score": 0,
        "strong_match": False,
    }


def match_candidates_to_job(job_file, candidate_files):
    """Compare several resumes to one job posting in ONE AI call, score them
    with the Logic Manager and save the result.

    Returns the saved record, e.g.
    {"id": "C001", "job": {...}, "candidates": [{..., "match_score": 85}, ...]}.
    Raises ValueError if the AI reply is unreadable, and lets AI/API errors
    through for the caller to handle.
    """
    prompt = CANDIDATE_COMPARISON_PROMPT.format(
        resume_count=len(candidate_files),
        locations=", ".join(choice_values(LOCATION_CHOICES)),
        work_arrangements=", ".join(choice_values(WORK_ARRANGEMENT_CHOICES)),
        working_hours=", ".join(choice_values(WORKING_HOURS_CHOICES)),
        industries=", ".join(choice_values(INDUSTRY_CHOICES)),
    )
    labelled_files = [("JOB POSTING", job_file)] + [
        (f"RESUME {number}", resume_file)
        for number, resume_file in enumerate(candidate_files, start=1)
    ]

    reply = parse_json_reply(ask_ai_with_pdfs(prompt, labelled_files))
    if reply is None or not isinstance(reply.get("candidates"), list):
        raise ValueError("AI comparison reply is not in the expected JSON format")

    # DATA: AI candidates by resume number, so each one is matched to its file
    by_number = {}
    for ai_candidate in reply["candidates"]:
        if isinstance(ai_candidate, dict):
            try:
                by_number.setdefault(int(ai_candidate.get("resume_number")), ai_candidate)
            except (TypeError, ValueError):
                continue

    candidates = []
    for number, resume_file in enumerate(candidate_files, start=1):
        ai_candidate = by_number.get(number)
        if ai_candidate is None:
            logger.warning("AI returned no result for resume %s (%s)", number, resume_file.name)
            candidates.append(unreadable_candidate(resume_file.name))
        else:
            candidates.append(clean_candidate(ai_candidate, resume_file.name))

    ai_job = reply.get("job") if isinstance(reply.get("job"), dict) else {}
    job = {
        "filename": job_file.name,
        "title": str(ai_job.get("title", "")).strip(),
        "company": str(ai_job.get("company", "")).strip(),
        "required_skills": as_list(ai_job.get("required_skills")),
        "location": pick(ai_job.get("location"), LOCATION_CHOICES),
        "work_arrangement": pick(ai_job.get("work_arrangement"), WORK_ARRANGEMENT_CHOICES),
        "working_hours": pick(ai_job.get("working_hours"), WORKING_HOURS_CHOICES),
        "industry": pick(ai_job.get("industry"), INDUSTRY_CHOICES),
    }

    return save_record("candidate_matches", {
        "created_at": timezone.now().isoformat(timespec="seconds"),
        "job": job,
        "candidates": candidates,
    })
