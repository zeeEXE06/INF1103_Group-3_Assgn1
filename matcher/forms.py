"""
Forms for Sprint 1.

These forms only validate *shape* (is a file attached, is it a PDF,
is it under the size limit, did the user pick preferences) — they do
not extract text or talk to the AI Manager. That belongs to later
sprints (PDF/OCR services, AI Manager). Keeping validation here means
views stay thin and the I/O boundary (rejecting bad input, one place)
stays in one place, per the I/O Manager responsibility in the spec.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django import forms


def validate_pdf_file(uploaded_file):
    """Shared PDF validation used by every upload field in the app.

    Raises ValidationError with a user-facing message on failure.
    Actual text extraction (Sprint 2/3) happens elsewhere — this only
    checks that the file looks like something we can safely accept.
    """
    name = uploaded_file.name.lower()
    if not name.endswith(".pdf"):
        raise ValidationError(f"'{uploaded_file.name}' is not a PDF file.")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise ValidationError(
            f"'{uploaded_file.name}' is larger than the "
            f"{settings.MAX_UPLOAD_SIZE_MB}MB limit."
        )

    if uploaded_file.size == 0:
        raise ValidationError(f"'{uploaded_file.name}' is empty.")


class JobPostingForm(forms.Form):
    """Step 1 of the employer workflow: upload the job description PDF."""

    job_file = forms.FileField(
        label="Job Description (PDF)",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf"}),
    )

    def clean_job_file(self):
        uploaded_file = self.cleaned_data["job_file"]
        validate_pdf_file(uploaded_file)
        return uploaded_file


WORK_ARRANGEMENT_CHOICES = [
    ("wfh", "Work From Home"),
    ("hybrid", "Hybrid"),
    ("on_site", "On-site"),
    ("flexible", "Flexible"),
]

LOCATION_CHOICES = [
    ("north", "North"),
    ("south", "South"),
    ("east", "East"),
    ("west", "West"),
    ("central", "Central"),
]

WORKING_HOURS_CHOICES = [
    ("standard", "Standard"),
    ("flexible", "Flexible"),
    ("shift", "Shift-based"),
    ("no_preference", "No preference"),
]


class ResumeUploadForm(forms.Form):
    """Job seeker workflow: resume PDF + preferences, one form/one page."""

    resume_file = forms.FileField(
        label="Your Resume (PDF)",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf"}),
    )
    work_arrangement = forms.ChoiceField(
        label="Preferred Work Arrangement",
        choices=WORK_ARRANGEMENT_CHOICES,
        widget=forms.RadioSelect,
    )
    locations = forms.MultipleChoiceField(
        label="Preferred Location(s)",
        choices=LOCATION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    working_hours = forms.ChoiceField(
        label="Preferred Working Hours",
        choices=WORKING_HOURS_CHOICES,
        widget=forms.RadioSelect,
    )

    def clean_resume_file(self):
        uploaded_file = self.cleaned_data["resume_file"]
        validate_pdf_file(uploaded_file)
        return uploaded_file