"""
Tests for the IO Manager's classes: checking uploads and reading the job
filters. They work on uploaded files and URL values, without loading pages.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils.datastructures import MultiValueDict

from ..managers.io_manager import UploadValidator
from .test_app import make_pdf_file


def uploads(**files):
    """Like request.FILES: one file per name, or a list for multi-file inputs."""
    return MultiValueDict({name: f if isinstance(f, list) else [f] for name, f in files.items()})


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
