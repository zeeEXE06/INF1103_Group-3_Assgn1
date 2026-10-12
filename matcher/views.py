"""
Views - each page checks the input, calls the matching service and shows a template.

DATA_MODE=debug shows the sample results from dummy_data.py; DATA_MODE=live
shows the visitor's own saved results.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render

from .dummy_data import sample_ranked_candidates, sample_ranked_jobs
from .managers.data_manager import load_records
from .managers.io_manager import (
    JobFilterForm,
    JobPostingForm,
    ResumeUploadForm,
    validate_candidate_files,
)
from .managers.logic_manager import filter_jobs, rank_candidates, rank_jobs
from .services.matching_service import match_candidates_to_job, match_jobs_to_resume, read_resume

logger = logging.getLogger(__name__)

AI_UNAVAILABLE = "The AI service is unavailable right now. Please try again later."


def is_live_mode():
    return settings.DATA_MODE == "live"


def find_record(collection, record_id):
    """Return the saved record with this id, or None."""
    if not record_id:
        return None
    for record in load_records(collection):
        if record.get("id") == record_id:
            return record
    return None


def landing(request):
    """Landing page: choose Job Seeker or Employer."""
    return render(request, "matcher/landing.html")


def employer_upload(request):
    """Employer uploads one job posting and one or more resumes."""
    job_form = JobPostingForm()
    candidate_errors = []

    if request.method == "POST":
        job_form = JobPostingForm(request.POST, request.FILES)
        candidate_files = request.FILES.getlist("candidate_files")
        candidate_errors = validate_candidate_files(candidate_files)

        if job_form.is_valid() and not candidate_errors:
            job_file = job_form.cleaned_data["job_file"]
            try:
                candidate_match = match_candidates_to_job(job_file, candidate_files)
            except ValueError:
                logger.exception("AI comparison reply could not be read")
                messages.error(request, "Could not compare the resumes. Please try again.")
            except Exception:
                # Bad/missing API key, network down, rate limit, files too large, etc.
                logger.exception("AI comparison failed")
                messages.error(request, AI_UNAVAILABLE)
            else:
                # Remember this employer's result so the results page shows theirs only
                request.session["candidate_match_id"] = candidate_match["id"]
                messages.success(
                    request,
                    f"Compared {len(candidate_files)} candidate resume(s) against the job posting.",
                )
                return redirect("matcher:employer_results")

    return render(
        request,
        "matcher/employer.html",
        {"job_form": job_form, "candidate_errors": candidate_errors},
    )


def employer_results(request):
    """Employer results: candidates ranked against the job posting (no AI call)."""
    job = None
    if is_live_mode():
        candidate_match = find_record("candidate_matches", request.session.get("candidate_match_id"))
        candidates = []
        if candidate_match:
            job = candidate_match.get("job")
            candidates = rank_candidates(candidate_match.get("candidates", []))
    else:
        candidates = sample_ranked_candidates()
    return render(
        request,
        "matcher/employer_results.html",
        {"candidates": candidates, "job": job},
    )


def job_seeker_upload(request):
    """Job seeker uploads a resume. Preferences are set as filters on the results page."""
    if request.method == "POST":
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            resume_file = form.cleaned_data["resume_file"]
            try:
                resume = read_resume(resume_file)
            except ValueError:
                messages.error(request, "Could not read the resume. Please try again.")
                return render(request, "matcher/job_seeker.html", {"form": form})
            except Exception:
                # Bad/missing API key, network down, rate limit, etc.
                logger.exception("AI call failed for %s", resume_file.name)
                messages.error(request, AI_UNAVAILABLE)
                return render(request, "matcher/job_seeker.html", {"form": form})

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

            # Remember this visitor's result so the results page shows theirs only
            request.session["job_match_id"] = job_match["id"]
            messages.success(
                request,
                f"Resume received. Found {len(job_match['jobs'])} matching job title(s) to search on Jobstreet.",
            )
            return redirect("matcher:job_results")
    else:
        form = ResumeUploadForm()

    return render(request, "matcher/job_seeker.html", {"form": form})


def job_results(request):
    """Job seeker results: suggested jobs, best first, with filters (no AI call)."""
    if is_live_mode():
        job_match = find_record("job_matches", request.session.get("job_match_id"))
        all_jobs = rank_jobs(job_match.get("jobs", [])) if job_match else []
    else:
        all_jobs = sample_ranked_jobs()

    # Filters come from the URL, e.g. ?locations=North&industry=Technology+%2F+IT
    filter_form = JobFilterForm(request.GET)
    if filter_form.is_valid():
        data = filter_form.cleaned_data
        jobs = filter_jobs(
            all_jobs,
            data["work_arrangement"],
            data["locations"],
            data["working_hours"],
            data["industry"],
        )
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
