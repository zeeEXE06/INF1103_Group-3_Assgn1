"""
Matching service - the three AI flows, connecting the AI, Logic and Data Managers.

The same input always gives the same output: every uploaded PDF is
fingerprinted, and if the same file (or set of files) was processed before,
the saved result is returned instead of asking the AI again.

    read_resume()             job seeker's resume PDF -> saved resume details
    match_jobs_to_resume()    saved resume -> suggested jobs with Jobstreet links
    match_candidates_to_job() job posting + resume PDFs -> scored candidates
"""

import hashlib
import logging
import re

from django.conf import settings
from django.utils import timezone

from ..managers.ai_manager import compare_candidates, extract_resume, suggest_jobs
from ..managers.data_manager import filter_records, load_records, save_record
from ..managers.io_manager import (
    INDUSTRY_CHOICES,
    LOCATION_CHOICES,
    WORK_ARRANGEMENT_CHOICES,
    WORKING_HOURS_CHOICES,
    choice_values,
)
from ..managers.logic_manager import calculate_score, is_strong_match, select_top_jobs, to_score

logger = logging.getLogger(__name__)

JOBSTREET_BASE_URL = "https://sg.jobstreet.com"


# ---------- Shared helpers ----------

def filter_options():
    """The filter values the AI must choose from."""
    return {
        "locations": ", ".join(choice_values(LOCATION_CHOICES)),
        "work_arrangements": ", ".join(choice_values(WORK_ARRANGEMENT_CHOICES)),
        "working_hours": ", ".join(choice_values(WORKING_HOURS_CHOICES)),
        "industries": ", ".join(choice_values(INDUSTRY_CHOICES)),
    }


def pick(value, choices):
    """Keep the AI's value only if it is one of the filter options, else ""."""
    return value if value in choice_values(choices) else ""


def as_list(value):
    """Keep a list of non-empty strings, whatever the AI sent."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def now():
    return timezone.now().isoformat(timespec="seconds")


def file_hash(uploaded_file):
    """Fingerprint of a file's contents (SHA-256), the same for identical files."""
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


def previous_result(collection, **fields):
    """The newest saved record with these field values, or None."""
    matches = filter_records(collection, **fields)
    if matches:
        logger.info("Same input as %s %s - reusing the saved result", collection, matches[-1]["id"])
        return matches[-1]
    return None


# ---------- Job seeker: read the resume ----------

def read_resume(resume_file):
    """Read a resume PDF with the AI and save its details.

    Returns the saved record, e.g. {"id": "R001", "filename": ..., "skills": [...]}.
    Raises ValueError if the AI could not read it.
    """
    resume_hash = file_hash(resume_file)
    previous = previous_result("resumes", file_hash=resume_hash)
    if previous:
        return previous

    resume_data = extract_resume(resume_file)
    if resume_data is None:
        raise ValueError("The AI could not read the resume")

    return save_record("resumes", {
        "file_hash": resume_hash,
        "filename": resume_file.name,
        "uploaded_at": now(),
        "education": resume_data.get("education", []),
        "experience": resume_data.get("experience", []),
        "skills": resume_data.get("skills", []),
    })


# ---------- Job seeker: suggest jobs ----------

def jobstreet_search_url(title):
    """e.g. "Junior Python Developer" -> https://sg.jobstreet.com/junior-python-developer-jobs"""
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"{JOBSTREET_BASE_URL}/{slug}-jobs"


def match_jobs_to_resume(resume_id=None):
    """Ask the AI for job titles that suit a saved resume, and save them
    with a Jobstreet search link for each.

    Uses the newest saved resume unless resume_id is given. Returns the saved
    record, e.g. {"id": "J001", "resume_id": "R001", "jobs": [...]}.
    Raises ValueError if there is no resume or the AI could not suggest jobs.
    """
    resumes = load_records("resumes")
    if resume_id is not None:
        resumes = [r for r in resumes if r.get("id") == resume_id]
    if not resumes:
        raise ValueError(f"No saved resume found (resume_id={resume_id})")
    resume = resumes[-1]

    max_jobs = settings.MAX_JOBS
    previous = previous_result("job_matches", resume_id=resume["id"], max_jobs=max_jobs)
    if previous:
        return previous

    reply = suggest_jobs(resume, max_jobs, filter_options())
    if reply is None:
        raise ValueError("The AI could not suggest jobs")

    jobs = []
    for job in reply["jobs"]:
        title = job["title"].strip()
        if not title:
            continue
        jobs.append({
            "title": title,
            "url": jobstreet_search_url(title),
            "match_score": to_score(job.get("match_score")),
            "location": pick(job.get("location"), LOCATION_CHOICES),
            "work_arrangement": pick(job.get("work_arrangement"), WORK_ARRANGEMENT_CHOICES),
            "working_hours": pick(job.get("working_hours"), WORKING_HOURS_CHOICES),
            "industry": pick(job.get("industry"), INDUSTRY_CHOICES),
            "matched_skills": job.get("matched_skills", []),
            "match_reason": job.get("match_reason", ""),
        })

    return save_record("job_matches", {
        "resume_id": resume["id"],
        "max_jobs": max_jobs,
        "searched_at": now(),
        "jobs": select_top_jobs(jobs, max_jobs),
    })


# ---------- Employer: compare resumes to one job posting ----------

MATCH_FIELDS = (
    "experience_match", "education_match", "location_match",
    "work_arrangement_match", "working_hours_match",
)


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
    Raises ValueError if the AI could not compare them.
    """
    # The job posting's fingerprint, then each resume's, in upload order
    file_hashes = [file_hash(job_file)] + [file_hash(f) for f in candidate_files]
    previous = previous_result("candidate_matches", file_hashes=file_hashes)
    if previous:
        return previous

    reply = compare_candidates(job_file, candidate_files, filter_options())
    if reply is None:
        raise ValueError("The AI could not compare the resumes")

    # Match each AI candidate back to its file by resume number
    by_number = {}
    for ai_candidate in reply["candidates"]:
        by_number.setdefault(ai_candidate["resume_number"], ai_candidate)

    candidates = []
    for number, resume_file in enumerate(candidate_files, start=1):
        ai_candidate = by_number.get(number)
        if ai_candidate is None:
            logger.warning("AI returned no result for resume %s (%s)", number, resume_file.name)
            candidates.append(unreadable_candidate(resume_file.name))
        else:
            candidates.append(clean_candidate(ai_candidate, resume_file.name))

    ai_job = reply["job"]
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
        "file_hashes": file_hashes,
        "created_at": now(),
        "job": job,
        "candidates": candidates,
    })
