"""
Views - each page checks the input, calls the matching service and shows a template.

Results pages only show what the AI produced for the visitor's own upload,
so nothing can be seen without the AI.
"""

from django.contrib import messages
from django.shortcuts import redirect, render

from .managers.data_manager import find_record
from .managers.io_manager import (
    filter_bar,
    read_employer_upload,
    read_job_filters,
    read_resume_upload,
)
from .managers.logic_manager import filter_jobs, rank_candidates, rank_jobs
from .services.matching_service import match_candidates_to_job, match_jobs_to_resume, read_resume

AI_FAILED = "The AI could not process your upload right now. Please try again later."


def landing(request):
    """Landing page: choose Job Seeker or Employer."""
    return render(request, "matcher/landing.html")


def employer_upload(request):
    """Employer uploads one job posting and one or more resumes."""
    job_errors, candidate_errors = [], []

    if request.method == "POST":
        job_file, candidate_files, job_errors, candidate_errors = read_employer_upload(request)

        if not job_errors and not candidate_errors:
            try:
                candidate_match = match_candidates_to_job(job_file, candidate_files)
            except ValueError:
                messages.error(request, AI_FAILED)
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
        {"job_errors": job_errors, "candidate_errors": candidate_errors},
    )


def employer_results(request):
    """Employer results: candidates ranked against the job posting (no AI call)."""
    job, candidates = None, []
    candidate_match = find_record("candidate_matches", request.session.get("candidate_match_id"))
    if candidate_match:
        job = candidate_match.get("job")
        candidates = rank_candidates(candidate_match.get("candidates", []))
    return render(
        request,
        "matcher/employer_results.html",
        {"candidates": candidates, "job": job},
    )


def job_seeker_upload(request):
    """Job seeker uploads a resume. Preferences are set as filters on the results page."""
    resume_errors = []
    if request.method == "POST":
        resume_file, resume_errors = read_resume_upload(request)
        if not resume_errors:
            try:
                resume = read_resume(resume_file)
            except ValueError:
                messages.error(request, AI_FAILED)
                return render(request, "matcher/job_seeker.html")

            try:
                job_match = match_jobs_to_resume(resume["id"])
            except ValueError:
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

    return render(request, "matcher/job_seeker.html", {"resume_errors": resume_errors})


def job_results(request):
    """Job seeker results: suggested jobs, best first, with filters (no AI call)."""
    job_match = find_record("job_matches", request.session.get("job_match_id"))
    all_jobs = rank_jobs(job_match.get("jobs", [])) if job_match else []

    # Filters come from the URL, e.g. ?locations=North&industry=Technology+%2F+IT
    filters = read_job_filters(request.GET)
    jobs = filter_jobs(
        all_jobs,
        filters["work_arrangement"],
        filters["locations"],
        filters["working_hours"],
        filters["industry"],
    )

    return render(
        request,
        "matcher/job_results.html",
        {
            "jobs": jobs,
            "total_job_count": len(all_jobs),
            "filter_bar": filter_bar(filters),
            "filters_applied": bool(request.GET),
        },
    )
