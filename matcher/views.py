"""
Views - each page checks the input and shows a template.

Sprint 1: uploads are checked but not saved. Results pages use sample data
from dummy_data.py.
Sprint 2: save the uploaded data with the Data Manager.
Sprint 3: score and rank results with the Logic Manager.
Sprint 4: analyse resumes and jobs with the AI Manager.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from .dummy_data import sample_ranked_candidates, sample_ranked_jobs
from .managers.io_manager import JobPostingForm, ResumeUploadForm, validate_pdf_file


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
    # TODO (Sprint 2/3): load from the Data Manager + Logic Manager instead of sample data
    candidates = sample_ranked_candidates()
    return render(
        request,
        "matcher/employer_results.html",
        {"candidates": candidates},
    )


def job_seeker_upload(request):
    """Job seeker uploads a resume and sets their preferences."""
    if request.method == "POST":
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # DATA: job seeker's resume and preferences
            resume_file = form.cleaned_data["resume_file"]            # resume PDF
            work_arrangement = form.cleaned_data["work_arrangement"]  # e.g. "wfh"
            preferred_locations = form.cleaned_data["locations"]      # e.g. ["north", "central"]
            working_hours = form.cleaned_data["working_hours"]        # e.g. "flexible"
            industry = form.cleaned_data["industry"]                  # e.g. "tech"

            # TODO (Sprint 2): extract text from resume_file and save it with
            # the preferences using the Data Manager
            # TODO (Sprint 3/4): send them to the AI + Logic Managers for ranking
            messages.success(request, "Resume and preferences received.")
            return redirect("matcher:job_results")
    else:
        form = ResumeUploadForm()

    return render(request, "matcher/job_seeker.html", {"form": form})


def job_results(request):
    """Job seeker results: jobs ranked against the resume."""
    # DATA: ranked jobs shown on the page
    # TODO (Sprint 2/3): load from the Data Manager + Logic Manager instead of sample data
    jobs = sample_ranked_jobs()
    return render(
        request,
        "matcher/job_results.html",
        {"jobs": jobs},
    )
