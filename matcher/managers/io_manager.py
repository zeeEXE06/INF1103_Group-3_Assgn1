"""
I/O Manager - reads and checks what users submit, and prepares the filter
options shown on the job results page.

    UploadValidator  checks uploaded PDFs before they reach the AI
"""

from django.conf import settings


# ---------- Filter options ----------

# The AI is told to use these same values, so they match what's saved on each
# job (e.g. location "Central").
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

# The checkbox filters: (name in the URL, label, choices)
CHECKBOX_FILTERS = [
    ("work_arrangement", "Work Arrangement", WORK_ARRANGEMENT_CHOICES),
    ("locations", "Location(s)", LOCATION_CHOICES),
    ("working_hours", "Working Hours", WORKING_HOURS_CHOICES),
]


# ---------- Upload checks ----------

class UploadValidator:
    """Checks the files a user uploads: PDFs only, not empty, under the size limit.

    Works on the uploaded files (request.FILES), not the whole request, so
    it doesn't depend on how the page was submitted.
    """

    def __init__(self, max_size_mb=None, max_candidates=None):
        """Defaults to MAX_UPLOAD_SIZE_MB and MAX_CANDIDATES in settings."""
        self._max_size_mb = settings.MAX_UPLOAD_SIZE_MB if max_size_mb is None else max_size_mb
        self._max_candidates = settings.MAX_CANDIDATES if max_candidates is None else max_candidates

    @property
    def max_size_mb(self):
        return self._max_size_mb

    @property
    def max_candidates(self):
        return self._max_candidates

    def check_pdf(self, uploaded_file):
        """Return an error message if the file is not a usable PDF, else None."""
        if not uploaded_file.name.lower().endswith(".pdf"):
            return f"'{uploaded_file.name}' is not a PDF file."
        if uploaded_file.size > self._max_size_mb * 1024 * 1024:
            return f"'{uploaded_file.name}' is larger than the {self._max_size_mb}MB limit."
        if uploaded_file.size == 0:
            return f"'{uploaded_file.name}' is empty."
        return None

    def check_resume_upload(self, files):
        """Job seeker's upload. Returns (resume_file, errors)."""
        resume_file = files.get("resume_file")
        if resume_file is None:
            return None, ["Upload your resume (PDF)."]
        error = self.check_pdf(resume_file)
        return resume_file, [error] if error else []

    def check_employer_upload(self, files):
        """Employer's upload. Returns (job_file, candidate_files, job_errors, candidate_errors)."""
        job_file = files.get("job_file")
        if job_file is None:
            job_errors = ["Upload the job description (PDF)."]
        else:
            error = self.check_pdf(job_file)
            job_errors = [error] if error else []

        candidate_files = files.getlist("candidate_files")
        if not candidate_files:
            candidate_errors = ["Upload at least one candidate resume (PDF)."]
        else:
            candidate_errors = []
            if len(candidate_files) > self._max_candidates:
                # All resumes go to the AI in one request, so keep the batch small
                candidate_errors.append(f"Upload at most {self._max_candidates} resumes at a time.")
            for uploaded_file in candidate_files:
                error = self.check_pdf(uploaded_file)
                if error:
                    candidate_errors.append(error)

        return job_file, candidate_files, job_errors, candidate_errors


def check_pdf(uploaded_file):
    """Return an error message if the file is not a usable PDF, else None."""
    if not uploaded_file.name.lower().endswith(".pdf"):
        return f"'{uploaded_file.name}' is not a PDF file."
    if uploaded_file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        return f"'{uploaded_file.name}' is larger than the {settings.MAX_UPLOAD_SIZE_MB}MB limit."
    if uploaded_file.size == 0:
        return f"'{uploaded_file.name}' is empty."
    return None


def read_resume_upload(request):
    """Job seeker's upload. Returns (resume_file, errors)."""
    resume_file = request.FILES.get("resume_file")
    if resume_file is None:
        return None, ["Upload your resume (PDF)."]
    error = check_pdf(resume_file)
    return resume_file, [error] if error else []


def read_employer_upload(request):
    """Employer's upload. Returns (job_file, candidate_files, job_errors, candidate_errors)."""
    job_file = request.FILES.get("job_file")
    if job_file is None:
        job_errors = ["Upload the job description (PDF)."]
    else:
        error = check_pdf(job_file)
        job_errors = [error] if error else []

    candidate_files = request.FILES.getlist("candidate_files")
    if not candidate_files:
        candidate_errors = ["Upload at least one candidate resume (PDF)."]
    else:
        candidate_errors = []
        if len(candidate_files) > settings.MAX_CANDIDATES:
            # All resumes go to the AI in one request, so keep the batch small
            candidate_errors.append(f"Upload at most {settings.MAX_CANDIDATES} resumes at a time.")
        for uploaded_file in candidate_files:
            error = check_pdf(uploaded_file)
            if error:
                candidate_errors.append(error)

    return job_file, candidate_files, job_errors, candidate_errors


# ---------- Job results filters ----------

def choice_values(choices):
    """[("WFH", "Work From Home"), ...] -> ["WFH", ...] (skips the "" = all option)."""
    return [value for value, _label in choices if value]


def read_job_filters(query):
    """The filters picked on the job results page, from the URL.

    Unknown values are ignored, and an empty filter means "show all", e.g.
    {"work_arrangement": ["WFH"], "locations": [], "working_hours": [], "industry": ""}
    """
    filters = {
        name: [value for value in query.getlist(name) if value in choice_values(choices)]
        for name, _label, choices in CHECKBOX_FILTERS
    }
    industry = query.get("industry", "")
    filters["industry"] = industry if industry in choice_values(INDUSTRY_CHOICES) else ""
    return filters


def filter_bar(filters):
    """The filter options for the template, with the picked ones marked."""
    groups = [
        {
            "name": name,
            "label": label,
            "options": [
                {"value": value, "label": text, "checked": value in filters[name]}
                for value, text in choices
            ],
        }
        for name, label, choices in CHECKBOX_FILTERS
    ]
    industries = [
        {"value": value, "label": text, "selected": value == filters["industry"]}
        for value, text in INDUSTRY_CHOICES
    ]
    return {"groups": groups, "industries": industries}
