"""
Tests for the IO Manager's classes: checking uploads and reading the job
filters. They work on uploaded files and URL values, without loading pages.
"""
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.http import QueryDict
from django.utils.datastructures import MultiValueDict
from pypdf import PdfWriter

from ..managers.io_manager import JobFilterForm, UploadValidator
from .test_app import make_pdf_file


def uploads(**files):
    """Like request.FILES: one file per name, or a list for multi-file inputs."""
    return MultiValueDict({name: f if isinstance(f, list) else [f] for name, f in files.items()})

def create_valid_pdf():
    """Create a valid PDF in memory for testing."""
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(buffer)
    return buffer.getvalue()

# ---------- UploadValidator: one file ----------

def test_a_normal_pdf_passes():
    assert UploadValidator().check_pdf(make_pdf_file("cv.pdf")) is None
    assert UploadValidator().check_pdf(make_pdf_file("CV.PDF")) is None


def test_non_pdf_empty_and_too_large_files_are_rejected():
    validator = UploadValidator(max_size_mb=1)
    assert validator.check_pdf(make_pdf_file("cv.docx")) == "'cv.docx' is not a PDF file."
    assert validator.check_pdf(make_pdf_file("cv.pdf", b"")) == "'cv.pdf' is empty."
    big = SimpleUploadedFile("big.pdf", b"x" * (1024 * 1024 + 1))
    assert validator.check_pdf(big) == "'big.pdf' is larger than the 1MB limit."


@override_settings(MAX_UPLOAD_SIZE_MB=3, MAX_CANDIDATES=4)
def test_limits_come_from_the_settings_unless_given():
    assert (UploadValidator().max_size_mb, UploadValidator().max_candidates) == (3, 4)
    assert UploadValidator(max_size_mb=1, max_candidates=2).max_candidates == 2


# ---------- UploadValidator: job seeker and employer uploads ----------

def test_resume_upload():
    validator = UploadValidator()
    assert validator.check_resume_upload(uploads()) == (None, ["Upload your resume (PDF)."])
    resume = make_pdf_file()
    assert validator.check_resume_upload(uploads(resume_file=resume)) == (resume, [])
    _, errors = validator.check_resume_upload(uploads(resume_file=make_pdf_file("cv.txt")))
    assert errors == ["'cv.txt' is not a PDF file."]


def test_employer_upload_needs_a_job_and_at_least_one_resume():
    _, _, job_errors, candidate_errors = UploadValidator().check_employer_upload(uploads())
    assert job_errors == ["Upload the job description (PDF)."]
    assert candidate_errors == ["Upload at least one candidate resume (PDF)."]


def test_employer_upload_checks_every_resume_and_the_limit():
    validator = UploadValidator(max_candidates=2)
    files = uploads(job_file=make_pdf_file("job.pdf"),
                    candidate_files=[make_pdf_file("a.pdf"), make_pdf_file("b.txt"), make_pdf_file("c.pdf")])
    job_file, candidate_files, job_errors, candidate_errors = validator.check_employer_upload(files)
    assert job_file.name == "job.pdf" and job_errors == []
    assert [f.name for f in candidate_files] == ["a.pdf", "b.txt", "c.pdf"]
    assert candidate_errors == ["Upload at most 2 resumes at a time.", "'b.txt' is not a PDF file."]


def test_valid_employer_upload_has_no_errors():
    files = uploads(job_file=make_pdf_file("job.pdf"), candidate_files=[make_pdf_file("a.pdf")])
    *_, job_errors, candidate_errors = UploadValidator().check_employer_upload(files)
    assert job_errors == [] and candidate_errors == []

def test_pdf_filename_with_non_pdf_content_is_rejected():
    uploaded_file = SimpleUploadedFile(
        "fake.pdf",
        b"This is just a text file, not a PDF."
    )

    error = UploadValidator().check_pdf(uploaded_file)

    assert error == "'fake.pdf' is not a valid or readable PDF file."


def test_corrupted_pdf_is_rejected():
    uploaded_file = SimpleUploadedFile(
        "corrupted.pdf",
        b"%PDF-1.4 corrupted content"
    )

    error = UploadValidator().check_pdf(uploaded_file)

    assert error == "'corrupted.pdf' is not a valid or readable PDF file."


def test_valid_pdf_content_is_accepted():
    uploaded_file = SimpleUploadedFile(
        "valid.pdf",
        create_valid_pdf(),
        content_type="application/pdf"
    )

    assert UploadValidator().check_pdf(uploaded_file) is None

def test_password_protected_pdf_is_rejected():
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("testpassword")

    writer.write(buffer)

    uploaded_file = SimpleUploadedFile(
        "protected.pdf",
        buffer.getvalue(),
        content_type="application/pdf"
    )

    error = UploadValidator().check_pdf(uploaded_file)

    assert error == "'protected.pdf' is password-protected and cannot be processed."

# ---------- JobFilterForm ----------

def test_filters_are_read_from_the_url():
    form = JobFilterForm.from_query(QueryDict("locations=West&locations=East&work_arrangement=WFH&industry=Healthcare"))
    assert form.filters == {"work_arrangement": ["WFH"], "locations": ["West", "East"],
                            "working_hours": [], "industry": "Healthcare"}
    assert not form.is_empty


def test_no_filters_means_show_all():
    form = JobFilterForm.from_query(QueryDict(""))
    assert form.filters == {"work_arrangement": [], "locations": [], "working_hours": [], "industry": ""}
    assert form.is_empty


def test_unknown_filter_values_are_ignored():
    form = JobFilterForm.from_query(QueryDict("locations=Mars&locations=West&industry=Space"))
    assert form.filters["locations"] == ["West"] and form.filters["industry"] == ""


def test_filters_cannot_be_changed_from_outside():
    form = JobFilterForm(locations=["West"])
    form.filters["locations"].append("East")
    assert form.filters["locations"] == ["West"]


def test_filter_bar_marks_the_picked_options():
    bar = JobFilterForm(locations=["West"], industry="Healthcare").filter_bar()
    locations = next(group for group in bar["groups"] if group["name"] == "locations")
    assert [o["value"] for o in locations["options"] if o["checked"]] == ["West"]
    assert [i["value"] for i in bar["industries"] if i["selected"]] == ["Healthcare"]


def test_choice_values_skip_the_show_all_option():
    assert JobFilterForm.choice_values([("", "All"), ("WFH", "Work From Home")]) == ["WFH"]
