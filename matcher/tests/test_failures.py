"""
What the user sees when something goes wrong. Each test is one row of the
error-handling matrix: the failure, the message shown, and that the app
keeps working (no crash, no half-saved results).
"""

import json
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from ..contracts.ai import AIProviderError
from ..views import EmployerResultsView, MatchingView
from .test_app import (
    RESUME_REPLY,
    comparison_reply,
    fake_gemini,
    load_records,
    make_pdf_file,
    text,
    upload_employer_files,
    upload_resume,
)

AI_FAILED = MatchingView.AI_FAILED
TIMEOUT = AIProviderError("Gemini did not reply within 60 seconds")
NOT_JSON = "Sorry, I can't help with that."
WRONG_SHAPE = json.dumps({"candidates": "none", "jobs": "none", "skills": "none"})


def client_with_session(**values):
    """A Client whose session already holds these values (e.g. an old result id)."""
    client = Client()
    session = client.session
    session.update(values)
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
    return client


def post_employer(job_file, candidate_file):
    return Client().post(reverse("matcher:employer_upload"),
                         {"job_file": job_file, "candidate_files": [candidate_file]})


# ---------- Errors nobody planned for ----------

@override_settings(DEBUG=False)
def test_unknown_page_shows_a_friendly_404():
    response = Client().get("/no-such-page/")
    assert response.status_code == 404
    assert "Page not found" in text(response) and "Go to the home page" in text(response)


@override_settings(DEBUG=False)
def test_unexpected_error_shows_a_friendly_500_page():
    client = Client(raise_request_exception=False)
    with patch.object(EmployerResultsView, "get", side_effect=RuntimeError("bug")):
        response = client.get(reverse("matcher:employer_results"))
    assert response.status_code == 500
    assert "Something went wrong" in text(response) and "RuntimeError" not in text(response)


# ---------- The AI fails (employer) ----------

def check_employer_ai_failure(*replies, expected_calls):
    with fake_gemini(*replies) as gemini:
        response = upload_employer_files(Client(), ["c1.pdf"])
    assert response.status_code == 200  # back on the form, not a crash
    assert AI_FAILED in text(response)
    assert gemini.call_count == expected_calls
    assert load_records("candidate_matches") == []


def test_ai_timeout_shows_a_message_and_saves_nothing():
    check_employer_ai_failure(TIMEOUT, expected_calls=1)


def test_ai_reply_that_is_not_json_is_asked_again_then_shows_a_message():
    check_employer_ai_failure(NOT_JSON, NOT_JSON, expected_calls=2)


def test_ai_reply_with_the_wrong_structure_is_asked_again_then_shows_a_message():
    check_employer_ai_failure(WRONG_SHAPE, WRONG_SHAPE, expected_calls=2)


def test_ai_reply_fixed_on_the_second_try_is_used():
    with fake_gemini(NOT_JSON, comparison_reply(1)) as gemini:
        response = upload_employer_files(Client(), ["c1.pdf"], follow=True)
    assert gemini.call_count == 2 and "Candidate 1" in text(response)


def test_resume_the_ai_skipped_is_shown_last_as_unreadable():
    reply = json.dumps({"job": {"title": "Dev"}, "candidates": []})
    with fake_gemini(reply):
        page = text(upload_employer_files(Client(), ["c1.pdf"], follow=True))
    assert "Could not read this resume." in page


# ---------- The AI fails (job seeker) ----------

def test_resume_the_ai_cannot_read_shows_a_message_and_saves_nothing():
    with fake_gemini(TIMEOUT):
        response = upload_resume(Client())
    assert response.status_code == 200 and AI_FAILED in text(response)
    assert load_records("resumes") == []


def test_failed_job_search_keeps_the_resume_and_says_so():
    with fake_gemini(RESUME_REPLY, WRONG_SHAPE, WRONG_SHAPE):
        page = text(upload_resume(Client(), follow=True))
    assert "the job search failed" in page and "No matches yet" in page
    assert len(load_records("resumes")) == 1 and load_records("job_matches") == []


# ---------- Bad uploads (never reach the AI) ----------

def check_upload_rejected(job_file, message):
    with fake_gemini() as gemini:
        response = post_employer(job_file, make_pdf_file("c1.pdf"))
    assert response.status_code == 200 and message in text(response)
    assert gemini.call_count == 0


def test_empty_pdf_is_rejected():
    check_upload_rejected(SimpleUploadedFile("job.pdf", b""), "is empty")


@override_settings(MAX_UPLOAD_SIZE_MB=1)
def test_oversized_pdf_is_rejected():
    check_upload_rejected(SimpleUploadedFile("job.pdf", b"%PDF" + b"0" * 1024 * 1024), "larger than the 1MB limit")


def test_corrupt_pdf_is_rejected():
    check_upload_rejected(SimpleUploadedFile("job.pdf", b"%PDF-1.4 broken"), "not a valid or readable PDF")


def test_file_that_is_not_a_pdf_is_rejected():
    check_upload_rejected(SimpleUploadedFile("job.docx", b"hello"), "is not a PDF file")


# ---------- Bad saved data ----------

def test_corrupt_data_file_is_kept_as_a_backup_and_the_app_carries_on():
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (settings.DATA_DIR / "candidate_matches.json").write_text("{not json")
    with fake_gemini(comparison_reply(1)):
        page = text(upload_employer_files(Client(), ["c1.pdf"], follow=True))
    assert "Candidate 1" in page
    assert (settings.DATA_DIR / "candidate_matches.broken.json").read_text() == "{not json"
    assert len(load_records("candidate_matches")) == 1


def test_broken_saved_result_shows_the_empty_page():
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    (settings.DATA_DIR / "candidate_matches.json").write_text(json.dumps(
        [{"id": "C001", "job": {}, "candidates": [{"filename": "a.pdf", "match_score": 500}]}]))
    (settings.DATA_DIR / "job_matches.json").write_text(json.dumps([{"id": "J001", "jobs": "oops"}]))

    employer = client_with_session(candidate_match_id="C001").get(reverse("matcher:employer_results"))
    seeker = client_with_session(job_match_id="J001").get(reverse("matcher:job_results"))
    assert employer.status_code == 200 and "No candidates yet" in text(employer)
    assert seeker.status_code == 200 and "No matches yet" in text(seeker)


def test_result_that_no_longer_exists_shows_the_empty_page():
    employer = client_with_session(candidate_match_id="C404").get(reverse("matcher:employer_results"))
    seeker = client_with_session(job_match_id="J404").get(reverse("matcher:job_results"))
    assert "No candidates yet" in text(employer) and "No matches yet" in text(seeker)
