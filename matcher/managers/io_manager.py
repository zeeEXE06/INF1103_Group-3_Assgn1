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

class ResumeUploadForm(forms.Form):
    """Job seeker uploads their resume."""

    # DATA: resume PDF (to be saved in Sprint 2)
    resume_file = forms.FileField(
        label="Your Resume (PDF)",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf"}),
    )

    def clean_resume_file(self):
        uploaded_file = self.cleaned_data["resume_file"]
        validate_pdf_file(uploaded_file)
        return uploaded_file


# ---------- Job results filters ----------

# Filter options on the job results page.
# The values match what's stored on each job (e.g. job.location == "Central").
WORK_ARRANGEMENT_CHOICES = [
    ("WFH", "Work From Home"),
    ("Hybrid", "Hybrid"),
    ("On-site", "On-site"),
    ("Flexible", "Flexible"),
]

LOCATION_CHOICES = [
    ("North", "North"),
    ("South", "South"),
    ("East", "East"),
    ("West", "West"),
    ("Central", "Central"),
]

WORKING_HOURS_CHOICES = [
    ("Standard", "Standard"),
    ("Flexible", "Flexible"),
    ("Shift-based", "Shift-based"),
]

INDUSTRY_CHOICES = [
    ("", "All industries"),
    ("Technology / IT", "Technology / IT"),
    ("Finance / Banking", "Finance / Banking"),
    ("Healthcare", "Healthcare"),
    ("Education", "Education"),
    ("Retail / E-commerce", "Retail / E-commerce"),
    ("Manufacturing", "Manufacturing"),
    ("Hospitality / F&B", "Hospitality / F&B"),
    ("Logistics / Supply Chain", "Logistics / Supply Chain"),
    ("Media / Creative", "Media / Creative"),
    ("Other", "Other"),
]


class JobFilterForm(forms.Form):
    """Filters on the job results page. All optional - nothing ticked = show all."""

    # DATA: work arrangements to show, e.g. ["WFH", "Hybrid"]
    work_arrangement = forms.MultipleChoiceField(
        label="Work Arrangement",
        choices=WORK_ARRANGEMENT_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    # DATA: locations to show, e.g. ["North", "Central"]
    locations = forms.MultipleChoiceField(
        label="Location(s)",
        choices=LOCATION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    # DATA: working hours to show, e.g. ["Flexible"]
    working_hours = forms.MultipleChoiceField(
        label="Working Hours",
        choices=WORKING_HOURS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    # DATA: industry to show, e.g. "Technology / IT" ("" = all)
    industry = forms.ChoiceField(
        label="Industry",
        choices=INDUSTRY_CHOICES,
        widget=forms.Select,
        required=False,
    )


# ---------- Output ----------

# TODO (Sprint 3/4): add functions to format results and error messages for display
