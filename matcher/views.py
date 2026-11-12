"""
Views - each page checks the input, calls the MatchingService and shows a template.

Results pages only show what the AI produced for the visitor's own upload,
so nothing can be seen without the AI.

    LandingView                               choose Job Seeker or Employer
    UploadView                                base for the two upload pages
    EmployerUploadView, EmployerResultsView   employer pages
    JobSeekerUploadView, JobResultsView       job seeker pages
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from .managers.io_manager import JobFilterForm, UploadValidator
from .services.matching_service import MatchingError, MatchingService


class LandingView(TemplateView):
    """Landing page: choose Job Seeker or Employer."""

    template_name = "matcher/landing.html"


class MatchingView(View):
    """Base for pages that use the MatchingService.

    The service is created on first use, once per request.
    """

    AI_FAILED = "The AI could not process your upload right now. Please try again later."

    @property
    def service(self):
        if not hasattr(self, "_service"):
            self._service = MatchingService.default()
        return self._service


class UploadView(MatchingView):
    """Base for the upload pages: GET shows the form, POST checks the files.

    Subclasses set template_name and write post().
    """

    template_name = None

    def get(self, request):
        return self.show_form(request)

    def show_form(self, request, **errors):
        """The upload form, with any error messages for each field."""
        return render(request, self.template_name, errors)


class EmployerUploadView(UploadView):
    """Employer uploads one job posting and one or more resumes."""

    template_name = "matcher/employer.html"

    def post(self, request):
        job_file, candidate_files, job_errors, candidate_errors = (
            UploadValidator().check_employer_upload(request.FILES)
        )
        if job_errors or candidate_errors:
            return self.show_form(request, job_errors=job_errors, candidate_errors=candidate_errors)

        try:
            shortlist = self.service.match_candidates_to_job(job_file, candidate_files)
        except MatchingError:
            messages.error(request, self.AI_FAILED)
            return self.show_form(request)

        # Remember this employer's result so the results page shows theirs only
        request.session["candidate_match_id"] = shortlist.id
        messages.success(request, f"Compared {len(candidate_files)} candidate resume(s) against the job posting.")
        return redirect("matcher:employer_results")


class EmployerResultsView(MatchingView):
    """Employer results: candidates ranked against the job posting (no AI call)."""

    def get(self, request):
        job, candidates = None, []
        shortlist = self.service.find_shortlist(request.session.get("candidate_match_id"))
        if shortlist:
            job = shortlist.job.to_dict()
            candidates = [
                {**result.to_dict(), "rank": rank}
                for rank, result in enumerate(self.service.ranked_candidates(shortlist), start=1)
            ]
        return render(request, "matcher/employer_results.html", {"candidates": candidates, "job": job})


class JobSeekerUploadView(UploadView):
    """Job seeker uploads a resume. Preferences are set as filters on the results page."""

    template_name = "matcher/job_seeker.html"

    def post(self, request):
        resume_file, resume_errors = UploadValidator().check_resume_upload(request.FILES)
        if resume_errors:
            return self.show_form(request, resume_errors=resume_errors)

        try:
            resume = self.service.read_resume(resume_file)
        except MatchingError:
            messages.error(request, self.AI_FAILED)
            return self.show_form(request)

        try:
            job_match = self.service.match_jobs_to_resume(resume.id)
        except MatchingError:
            messages.warning(request, "Resume received, but the job search failed. Please try again later.")
            return redirect("matcher:job_results")

        # Remember this visitor's result so the results page shows theirs only
        request.session["job_match_id"] = job_match["id"]
        messages.success(
            request,
            f"Resume received. Found {len(job_match['jobs'])} matching job title(s) to search on Jobstreet.",
        )
        return redirect("matcher:job_results")


class JobResultsView(MatchingView):
    """Job seeker results: suggested jobs, best first, with filters (no AI call)."""

    def get(self, request):
        all_jobs = self.service.suggested_jobs(request.session.get("job_match_id"))

        # Filters come from the URL, e.g. ?locations=North&industry=Technology+%2F+IT
        form = JobFilterForm.from_query(request.GET)
        job_filter = self.service.job_filter(form.filters)
        # Number every job first, so a job keeps its rank when others are filtered out
        jobs = [
            {**job.to_dict(), "rank": rank}
            for rank, job in enumerate(all_jobs, start=1)
            if job_filter.matches(job)
        ]

        return render(
            request,
            "matcher/job_results.html",
            {
                "jobs": jobs,
                "total_job_count": len(all_jobs),
                "filter_bar": form.filter_bar(),
                "filters_applied": bool(request.GET),
            },
        )
