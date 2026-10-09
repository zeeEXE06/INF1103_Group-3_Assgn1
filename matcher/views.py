"""
Views - each page checks the input and shows a template.

Sprint 1: uploads are checked but not saved. Results pages use sample data
from dummy_data.py in debug mode, or show nothing in live mode
(see DATA_MODE in config/settings.py).
Sprint 2: save the uploaded data with the Data Manager.
Sprint 3: score and rank results with the Logic Manager.
Sprint 4: analyse resumes and jobs with the AI Manager.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone

from .dummy_data import sample_ranked_candidates, sample_ranked_jobs
from .managers.ai_manager import ask_ai, parse_json_reply
from .managers.data_manager import load_records, save_record
from .managers.io_manager import (
    JobFilterForm,
    JobPostingForm,
    ResumeUploadForm,
    validate_pdf_file,
)
from .managers.logic_manager import filter_jobs, rank_jobs
from .services.matching_service import match_jobs_to_resume

logger = logging.getLogger(__name__)


# Prompt sent to the AI Manager with the job seeker's resume PDF
RESUME_EXTRACTION_PROMPT = """
Analyze the uploaded resume.

Extract the candidate's education & experience information.

Look for education information such as:
- Degrees
- Diplomas
- Certificates
- Fields of study
- Schools or universities
- Dates of study

Look for experience information such as:
- Job titles
- Companies
- Dates of employment

Look for skills also and fill them into JSON accordingly.

Return ONLY valid JSON in this format:

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

If none of the information is found, return the following JSON with
empty arrays if applicable:
{
    "education": [],
    "experience": [],
    "skills": []
}

Do not invent information that is not present in the resume.
"""


# ---------- Data mode (debug = fixed sample data, live = real data) ----------

def is_live_mode():
    return settings.DATA_MODE == "live"


def get_ranked_candidates():
    """Return the ranked candidates for the employer results page."""
    if is_live_mode():
        # TODO (Sprint 2/3): load candidates with the Data Manager and rank
        # them with the Logic Manager. Empty until then.
        return []
    return sample_ranked_candidates()


def get_ranked_jobs():
    """Return the ranked jobs for the job seeker results page."""
    if is_live_mode():
        # TODO (Sprint 2/3): load jobs with the Data Manager and rank
        # them with the Logic Manager. Empty until then.
        return []
    return sample_ranked_jobs()


def landing(request):
    """Landing page: choose Job Seeker or Employer."""
    return render(request, "matcher/landing.html")


def employer_upload(request):
    """Employer uploads one job posting and one or more resumes."""
    job_form = JobPostingForm()
    candidate_errors = []

    if request.method == "POST":
        job_form = JobPostingForm(request.POST, request.FILES)

        # DATA: list of candidate resume PDFs uploaded by the employer
        candidate_files = request.FILES.getlist("candidate_files")

        if not candidate_files:
            candidate_errors.append("Upload at least one candidate resume (PDF).")
        else:
            for uploaded_file in candidate_files:
                try:
                    validate_pdf_file(uploaded_file)
                except ValidationError as exc:
                    candidate_errors.append(exc.message)

        if job_form.is_valid() and not candidate_errors:
            # DATA: job description PDF uploaded by the employer
            job_file = job_form.cleaned_data["job_file"]

            # TODO (Sprint 2): extract text from job_file and candidate_files,
            # then save them with the Data Manager
            # TODO (Sprint 3/4): send them to the AI + Logic Managers for ranking
            messages.success(
                request,
                f"Job posting and {len(candidate_files)} candidate resume(s) received.",
            )
            return redirect("matcher:employer_results")

    return render(
        request,
        "matcher/employer.html",
        {
            "job_form": job_form,
            "candidate_errors": candidate_errors,
        },
    )


def employer_results(request):
    """Employer results: candidates ranked against the job posting."""
    # DATA: ranked candidates shown on the page
    candidates = get_ranked_candidates()
    return render(
        request,
        "matcher/employer_results.html",
        {"candidates": candidates},
    )


def job_seeker_upload(request):
    """Job seeker uploads a resume. Preferences are set as filters on the results page."""
    if request.method == "POST":
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # DATA: job seeker's resume PDF
            resume_file = form.cleaned_data["resume_file"]

            # DATA: AI Manager's reply as JSON text (mock reply unless AI_MODE=live)
            try:
                ai_result = ask_ai(RESUME_EXTRACTION_PROMPT, resume_file)
            except Exception:
                # Bad/missing API key, network down, rate limit, etc.
                logger.exception("AI call failed for %s", resume_file.name)
                messages.error(
                    request,
                    "The AI service is unavailable right now. Please try again later.",
                )
                return render(request, "matcher/job_seeker.html", {"form": form})

            # DATA: education/experience/skills parsed from the reply (None if broken)
            resume_data = parse_json_reply(ai_result)
            if resume_data is None:
                messages.error(request, "Could not read the resume. Please try again.")
                return render(request, "matcher/job_seeker.html", {"form": form})

            # DATA: saved resume record, e.g. {"id": "R001", "filename": ..., "skills": [...]}
            resume = save_record("resumes", {
                "filename": resume_file.name,
                "uploaded_at": timezone.now().isoformat(timespec="seconds"),
                "education": resume_data.get("education", []),
                "experience": resume_data.get("experience", []),
                "skills": resume_data.get("skills", []),
            })

            # DATA: job titles suggested by the AI with Jobstreet search links,
            # saved in data/job_matches.json
            try:
                job_match = match_jobs_to_resume(resume["id"])
            except Exception:
                # The resume is already saved, so still continue to the results page
                logger.exception("Job search failed for resume %s", resume["id"])
                messages.warning(
                    request,
                    "Resume received, but the job search failed. Please try again later.",
                )
                return redirect("matcher:job_results")

            # Remember this visitor's match so the results page shows their jobs only
            request.session["job_match_id"] = job_match["id"]
            messages.success(
                request,
                f"Resume received. Found {len(job_match['jobs'])} matching job title(s) to search on Jobstreet.",
            )
            return redirect("matcher:job_results")
    else:
        form = ResumeUploadForm()

    return render(request, "matcher/job_seeker.html", {"form": form})


def get_job_suggestions(request):
    """Return the saved AI job suggestions for this visitor's last upload, best first.

    Reads data/job_matches.json via the Data Manager - no AI call. Each job is a
    dict with rank, title, url, match_score, location, work_arrangement,
    working_hours, industry, matched_skills and match_reason.
    Empty if the visitor has not uploaded a resume (or the match was not found).
    """
    job_match_id = request.session.get("job_match_id")
    if not job_match_id:
        return []

    for record in load_records("job_matches"):
        if record.get("id") == job_match_id:
            return rank_jobs(record.get("jobs", []))
    return []


def job_results(request):
    """Job seeker results: jobs ranked against the resume, with filters."""
    # DATA: all ranked jobs, before filtering. Live mode = the AI's suggested
    # job titles saved in job_matches.json; debug mode = sample jobs.
    # Filtering only reads saved data, so changing filters never calls the AI.
    if is_live_mode():
        all_jobs = get_job_suggestions(request)
    else:
        all_jobs = get_ranked_jobs()

    # Filters come from the URL, e.g. ?locations=North&industry=Technology+%2F+IT
    filter_form = JobFilterForm(request.GET)
    if filter_form.is_valid():
        # DATA: job seeker's chosen filters (empty = show all)
        work_arrangements = filter_form.cleaned_data["work_arrangement"]  # e.g. ["WFH"]
        locations = filter_form.cleaned_data["locations"]                 # e.g. ["North", "Central"]
        working_hours = filter_form.cleaned_data["working_hours"]         # e.g. ["Flexible"]
        industry = filter_form.cleaned_data["industry"]                   # e.g. "Technology / IT"

        # DATA: jobs left after filtering
        jobs = filter_jobs(all_jobs, work_arrangements, locations, working_hours, industry)
    else:
        # Bad filter values in the URL - ignore them and show everything
        jobs = all_jobs

    return render(
        request,
        "matcher/job_results.html",
        {
            "jobs": jobs,
            "total_job_count": len(all_jobs),
            "filter_form": filter_form,
            "filters_applied": bool(request.GET),
            "show_jobstreet_links": is_live_mode(),
        },
    )
