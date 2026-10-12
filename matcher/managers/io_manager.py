"""
I/O Manager - the upload and filter forms, and the checks on what users submit.
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

def validate_candidate_files(candidate_files):
    """Check the employer's resume uploads. Returns a list of error messages."""
    if not candidate_files:
        return ["Upload at least one candidate resume (PDF)."]

    errors = []
    if len(candidate_files) > settings.MAX_CANDIDATES:
        # All resumes go to the AI in one request, so keep the batch small
        errors.append(f"Upload at most {settings.MAX_CANDIDATES} resumes at a time.")
    for uploaded_file in candidate_files:
        try:
            validate_pdf_file(uploaded_file)
        except ValidationError as exc:
            errors.append(exc.message)
    return errors


class JobPostingForm(forms.Form):
    """Employer uploads the job description PDF."""

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

    resume_file = forms.FileField(
        label="Your Resume (PDF)",
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf"}),
    )

    def clean_resume_file(self):
        uploaded_file = self.cleaned_data["resume_file"]
        validate_pdf_file(uploaded_file)
        return uploaded_file


# ---------- Job results filters ----------

# Filter options on the job results page. The AI is told to use these same
# values, so they match what's saved on each job (e.g. location "Central").
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

    work_arrangement = forms.MultipleChoiceField(
        label="Work Arrangement",
        choices=WORK_ARRANGEMENT_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    locations = forms.MultipleChoiceField(
        label="Location(s)",
        choices=LOCATION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    working_hours = forms.MultipleChoiceField(
        label="Working Hours",
        choices=WORKING_HOURS_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    industry = forms.ChoiceField(
        label="Industry",
        choices=INDUSTRY_CHOICES,
        widget=forms.Select,
        required=False,
    )
