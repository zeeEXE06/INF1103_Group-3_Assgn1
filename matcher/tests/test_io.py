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

from ..domain.scoring_profile import ScoringProfile
from ..managers.io_manager import LOCATION_CHOICES, JobFilterForm, ScoringProfileForm, UploadValidator
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


def test_ai_is_given_the_same_values_as_the_filters():
    options = JobFilterForm.options_for_ai()
    assert sorted(options) == ["industries", "locations", "work_arrangements", "working_hours"]
    assert options["locations"] == "North, South, East, West, Central"
    assert "All industries" not in options["industries"]


def test_values_from_the_ai_are_kept_only_if_allowed():
    assert JobFilterForm.allowed_value("West", LOCATION_CHOICES) == "West"
    assert JobFilterForm.allowed_value("Mars", LOCATION_CHOICES) == ""
    assert JobFilterForm.allowed_value(None, LOCATION_CHOICES) == ""



# ---------- ScoringProfileForm ----------

PROFILES = ScoringProfile.built_in()


def custom_profile(**fields):
    """A submitted custom profile, like request.POST."""
    data = {"profile": "custom", "profile_name": "Mine", "strong_match_skills": "70",
            **{f"weight_{part}": str(weight) for part, weight in ScoringProfile.DEFAULT_WEIGHTS.items()}}
    data.update(fields)
    query = QueryDict(mutable=True)
    query.update(data)
    return query


def test_new_profile_form_picks_the_first_profile():
    form = ScoringProfileForm(PROFILES)
    assert form.profile.name == "Balanced" and not form.errors and not form.is_custom


def test_profile_form_picks_a_profile_by_id():
    form = ScoringProfileForm(PROFILES, {"profile": "experience-first"})
    assert form.profile.name == "Experience first" and not form.errors


def test_profile_form_rejects_an_unknown_profile():
    form = ScoringProfileForm(PROFILES, {"profile": "S999"})
    assert form.profile is None and form.errors == ["Choose one of the scoring profiles."]


def test_profile_form_reads_a_custom_profile():
    form = ScoringProfileForm(PROFILES, custom_profile(weight_skills="20", weight_experience="45",
                                                       strong_match_skills="60"))
    assert form.is_custom and not form.errors
    assert form.profile.id is None and form.profile.name == "Mine"
    assert form.profile.weights["experience"] == 45 and form.profile.strong_match_skills == 60


def test_profile_form_turns_bad_custom_values_into_messages():
    def errors(**fields):
        return ScoringProfileForm(PROFILES, custom_profile(**fields)).errors

    assert errors(weight_skills="lots") == ["The Skills weight must be a whole number from 0 to 100."]
    assert errors(weight_skills="50") == ["The weights must add up to 100, not 110."]
    assert errors(profile_name="  ") == ["Give the scoring profile a name."]
    assert errors(strong_match_skills="150") == [
        "The Strong Match skills share must be a whole number from 0 to 100."]


def test_profile_picker_keeps_what_was_typed():
    picker = ScoringProfileForm(PROFILES, custom_profile(weight_skills="50")).picker()
    assert picker["custom"]["checked"] and picker["custom"]["name"] == "Mine"
    assert picker["custom"]["weights"][0] == {"field": "weight_skills", "label": "Skills", "value": "50"}
    assert not any(option["checked"] for option in picker["options"])
    assert [o["id"] for o in picker["options"]] == ["balanced", "skills-first", "experience-first"]
