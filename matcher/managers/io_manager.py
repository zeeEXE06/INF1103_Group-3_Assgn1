"""
I/O Manager - reads and checks what users submit, and prepares the filter
options shown on the job results page.

    UploadValidator  checks uploaded PDFs before they reach the AI
    JobFilterForm    the filters on the job results page
"""

from django.conf import settings
from pypdf import PdfReader


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
        try: #read and validate acutal pdf content
            uploaded_file.seek(0)
            reader = PdfReader(uploaded_file, strict=True)
            if reader.is_encrypted: #reject password-protected pdfs
                return f"'{uploaded_file.name}' is password-protected and cannot be processed."
            if len(reader.pages) == 0: #check pdf got at least 1 page
                return f"'{uploaded_file.name}' does not contain any pages."
            for page in reader.pages:
                _ = page.mediabox
                contents = page.get_contents()
                if contents is not None:
                    contents.get_data()
        except Exception:
            return f"'{uploaded_file.name}' is not a valid or readable PDF file."
        finally:
            uploaded_file.seek(0) #reset file pointer for AI processing
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


# ---------- Job results filters ----------

class JobFilterForm:
    """The filters picked on the job results page.

    Only known values are kept, and an empty filter means "show all", e.g.
    {"work_arrangement": ["WFH"], "locations": [], "working_hours": [], "industry": ""}
    """

    # The checkbox filters: (name in the URL, label, choices)
    CHECKBOX_FILTERS = [
        ("work_arrangement", "Work Arrangement", WORK_ARRANGEMENT_CHOICES),
        ("locations", "Location(s)", LOCATION_CHOICES),
        ("working_hours", "Working Hours", WORKING_HOURS_CHOICES),
    ]

    def __init__(self, work_arrangement=(), locations=(), working_hours=(), industry=""):
        picked = {"work_arrangement": work_arrangement, "locations": locations, "working_hours": working_hours}
        self._filters = {
            name: [value for value in picked[name] if value in self.choice_values(choices)]
            for name, _label, choices in self.CHECKBOX_FILTERS
        }
        self._filters["industry"] = industry if industry in self.choice_values(INDUSTRY_CHOICES) else ""

    @classmethod
    def from_query(cls, query):
        """Read the filters from the URL, e.g. ?locations=West&locations=East."""
        return cls(
            **{name: query.getlist(name) for name, _label, _choices in cls.CHECKBOX_FILTERS},
            industry=query.get("industry", ""),
        )

    @staticmethod
    def choice_values(choices):
        """[("WFH", "Work From Home"), ...] -> ["WFH", ...] (skips the "" = all option)."""
        return [value for value, _label in choices if value]

    @classmethod
    def options_for_ai(cls):
        """The values the AI must choose from, e.g. {"locations": "North, South, ..."}.

        The AI is given the same values the filters use, so every saved job
        can be filtered.
        """
        return {
            "locations": ", ".join(cls.choice_values(LOCATION_CHOICES)),
            "work_arrangements": ", ".join(cls.choice_values(WORK_ARRANGEMENT_CHOICES)),
            "working_hours": ", ".join(cls.choice_values(WORKING_HOURS_CHOICES)),
            "industries": ", ".join(cls.choice_values(INDUSTRY_CHOICES)),
        }

    @classmethod
    def allowed_value(cls, value, choices):
        """Keep a value from the AI only if it is one of the filter options, else ""."""
        return value if value in cls.choice_values(choices) else ""

    @property
    def filters(self):
        """The picked values, e.g. {"locations": ["West"], ..., "industry": ""}."""
        return {name: list(value) if isinstance(value, list) else value for name, value in self._filters.items()}

    @property
    def is_empty(self):
        """True if nothing is picked, so every job is shown."""
        return not any(self._filters.values())

    def filter_bar(self):
        """The filter options for the template, with the picked ones marked."""
        groups = [
            {
                "name": name,
                "label": label,
                "options": [
                    {"value": value, "label": text, "checked": value in self._filters[name]}
                    for value, text in choices
                ],
            }
            for name, label, choices in self.CHECKBOX_FILTERS
        ]
        industries = [
            {"value": value, "label": text, "selected": value == self._filters["industry"]}
            for value, text in INDUSTRY_CHOICES
        ]
        return {"groups": groups, "industries": industries}
