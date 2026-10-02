"""
I/O Manager - handles all user input and output.

Sprint 1: checks the uploaded files and form inputs before they reach the views.
Sprint 2: pass the checked data on to the Data Manager to be saved.
Sprint 3/4: format the results from the Logic Manager for display.
"""

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError


# ---------- File checks ----------

def validate_pdf_file(uploaded_file):
    """Check that an uploaded file is a PDF, not empty and under the size limit."""
    file_name = uploaded_file.name.lower()
    if not file_name.endswith(".pdf"):
        raise ValidationError(f"'{uploaded_file.name}' is not a PDF file.")

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if uploaded_file.size > max_bytes:
        raise ValidationError(
            f"'{uploaded_file.name}' is larger than the "
            f"{settings.MAX_UPLOAD_SIZE_MB}MB limit."
        )

    if uploaded_file.size == 0:
        raise ValidationError(f"'{uploaded_file.name}' is empty.")


# ---------- Employer input ----------

class JobPostingForm(forms.Form):
    """Employer uploads the job description PDF."""

    # DATA: job description PDF (to be saved in Sprint 2)
    job_file = forms.FileField(
        label="Job Description (PDF)",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf"}),
    )

    def clean_job_file(self):
        uploaded_file = self.cleaned_data["job_file"]
        validate_pdf_file(uploaded_file)
        return uploaded_file


# ---------- Job seeker input ----------

# Options shown on the job seeker page
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

INDUSTRY_CHOICES = [
    ("", "Select an industry"),
    ("tech", "Technology / IT"),
    ("finance", "Finance / Banking"),
    ("healthcare", "Healthcare"),
    ("education", "Education"),
    ("retail", "Retail / E-commerce"),
    ("manufacturing", "Manufacturing"),
    ("hospitality", "Hospitality / F&B"),
    ("logistics", "Logistics / Supply Chain"),
    ("media", "Media / Creative"),
    ("other", "Other"),
]


class ResumeUploadForm(forms.Form):
    """Job seeker uploads their resume and picks their preferences."""

    # DATA: resume PDF (to be saved in Sprint 2)
    resume_file = forms.FileField(
        label="Your Resume (PDF)",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf"}),
    )
    # DATA: preferred work arrangement, e.g. "wfh"
    work_arrangement = forms.ChoiceField(
        label="Preferred Work Arrangement",
        choices=WORK_ARRANGEMENT_CHOICES,
        widget=forms.RadioSelect,
    )
    # DATA: list of preferred locations, e.g. ["north", "central"]
    locations = forms.MultipleChoiceField(
        label="Preferred Location(s)",
        choices=LOCATION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    # DATA: preferred working hours, e.g. "flexible"
    working_hours = forms.ChoiceField(
        label="Preferred Working Hours",
        choices=WORKING_HOURS_CHOICES,
        widget=forms.RadioSelect,
    )
    # DATA: preferred industry, e.g. "tech"
    industry = forms.ChoiceField(
        label="Preferred Industry",
        choices=INDUSTRY_CHOICES,
        widget=forms.Select,
        required=True,
    )

    def clean_industry(self):
        industry = self.cleaned_data["industry"]
        if not industry:
            raise ValidationError("Select an industry.")
        return industry

    def clean_resume_file(self):
        uploaded_file = self.cleaned_data["resume_file"]
        validate_pdf_file(uploaded_file)
        return uploaded_file


# ---------- Output ----------

# TODO (Sprint 3/4): add functions to format results and error messages for display
