"""
Views for Sprint 1 (UI).

Every view here does two things: validate/accept input, and render a
template. There is no persistence (Data Manager, Sprint 2), no AI
analysis (AI Manager, Sprint 4), and no scoring logic (Logic Manager,
Sprint 3) yet — results pages are populated from matcher/dummy_data.py
so the full click-through experience is real even though the numbers
behind it are not.

Uploaded files ARE validated (type, size, non-empty) because that
validation is part of the UI/UX contract (clear, immediate errors),
but the files are discarded rather than processed further — wiring
them into the Data/AI/Logic Managers happens in later sprints.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from .dummy_data import sample_ranked_candidates, sample_ranked_jobs
from .forms import JobPostingForm, ResumeUploadForm, validate_pdf_file

from .managers.ai_manager import ask_ai

#def test_ai(request):
#    result = ask_ai("Verify integration with AI and return a simple response.")
    
#    return render(request, "matcher/base.html", {
#        "result": result
#    })

def landing(request):
    """Landing page: choose Job Seeker or Employer."""
    return render(request, "matcher/landing.html")


def employer_upload(request):
    """Employer workflow: upload one job posting + one or more resumes."""
    job_form = JobPostingForm()
    candidate_errors = []
    candidate_file_count = 0

    if request.method == "POST":
        job_form = JobPostingForm(request.POST, request.FILES)
        candidate_files = request.FILES.getlist("candidate_files")
        candidate_file_count = len(candidate_files)

        if not candidate_files:
            candidate_errors.append("Upload at least one candidate resume (PDF).")
        else:
            for uploaded_file in candidate_files:
                try:
                    validate_pdf_file(uploaded_file)
                except ValidationError as exc:
                    candidate_errors.append(exc.message)

        if job_form.is_valid() and not candidate_errors:
            # Sprint 2+ will hand these files to the PDF/OCR service, then
            # the Data Manager, AI Manager and Logic Manager in turn.
            # For now we simply acknowledge the upload and show sample
            # ranked results so the workflow is fully navigable.
            messages.success(
                request,
                f"Job posting and {candidate_file_count} candidate resume(s) received.",
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
    """Employer results: ranked candidates against the job posting."""
    candidates = sample_ranked_candidates()
    return render(
        request,
        "matcher/employer_results.html",
        {"candidates": candidates},
    )


def job_seeker_upload(request):
    """Job seeker workflow: upload resume + set preferences."""
    if request.method == "POST":
        form = ResumeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Sprint 2+ will structure the resume and store preferences via
            # the Data Manager, then run it through AI + Logic Managers.
            messages.success(request, "Resume and preferences received.")
            return redirect("matcher:job_results")
    else:
        form = ResumeUploadForm()

    return render(request, "matcher/job_seeker.html", {"form": form})


def job_results(request):
    """Job seeker results: ranked job postings against the resume."""
    jobs = sample_ranked_jobs()
    return render(
        request,
        "matcher/job_results.html",
        {"jobs": jobs},
    )
