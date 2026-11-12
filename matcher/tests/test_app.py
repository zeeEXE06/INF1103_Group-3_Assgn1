"""
Tests for the whole app: the pages and the AI flows from upload to results.
Each class has its own tests in the other test_*.py files. Run them with:

    python run_tests.py

Every test is a plain function. No test calls the real AI: fake_gemini()
replaces Gemini with a FakeProvider, whose fixed replies still go through
the AI Manager's checks. run_tests.py gives each test its own empty data folder.
"""

import io
import json
import re
from contextlib import contextmanager
from unittest.mock import patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from pypdf import PdfWriter

from ..managers.data_manager import JsonRepository
from ..services.matching_service import MatchingError, MatchingService
from .fakes import FakeProvider


# ---------- Fake Gemini replies ----------

RESUME_REPLY = json.dumps({
    "education": [{"qualification": "B.Sc.", "institution": "Sample University",
                   "field_of_study": "Computer Science", "start_date": "2020", "end_date": "2024"}],
    "experience": [{"job_title": "Software Developer Intern", "company": "Sample Company",
                    "start_date": "2023", "end_date": "2023"}],
    "skills": [{"skill": "Python"}, {"skill": "Django"}],
})

JOBS_REPLY = json.dumps({"jobs": [
    {"title": "Software Developer", "match_score": 91, "location": "Central", "work_arrangement": "WFH",
     "working_hours": "Flexible", "industry": "Technology / IT", "matched_skills": ["Python", "Django"],
     "match_reason": "Uses the candidate's Python and Django skills."},
    {"title": "Backend Engineer", "match_score": 68, "location": "East", "work_arrangement": "Hybrid",
     "working_hours": "Standard", "industry": "Technology / IT", "matched_skills": ["Python"],
     "match_reason": "Good backend overlap."},
    {"title": "Data Analyst", "match_score": 35, "location": "West", "work_arrangement": "On-site",
     "working_hours": "Shift-based", "industry": "Finance / Banking", "matched_skills": [],
     "match_reason": "Limited overlap."},
]})


def comparison_reply(resume_count):
    """Resume 1 is a strong match, resume 2 a partial match, the rest weak."""
    candidates = []
    for number in range(1, resume_count + 1):
        strong, partial = number == 1, number == 2
        matched = ["Python", "Django", "SQL"] if strong else ["Python", "Django"] if partial else ["Python"]
        candidates.append({
            "resume_number": number,
            "name": f"Candidate {number}",
            "matched_skills": matched,
            "missing_skills": [skill for skill in ["Python", "Django", "SQL"] if skill not in matched],
            "experience_match": strong,
            "education_match": True,
            "location_match": strong or partial,
            "work_arrangement_match": True,
            "working_hours_match": strong,
            "summary": f"Summary for candidate {number}.",
        })
    return json.dumps({
        "job": {"title": "Junior Python Developer", "company": "Sample Tech", "required_skills": ["Python", "Django", "SQL"]},
        "candidates": candidates,
    })


@contextmanager
def fake_gemini(*replies):
    """Replace Gemini with a FakeProvider that gives these replies, in order.

    Use as `with fake_gemini(...) as gemini:`; gemini.call_count is the
    number of AI calls. With no replies left, any AI call fails.
    """
    provider = FakeProvider(*replies)
    with patch("matcher.services.matching_service.GeminiProvider", return_value=provider):
        yield provider


# ---------- Helpers ----------

def make_pdf_file(name="resume.pdf", content=None):
    if content is not None:
        return SimpleUploadedFile(
            name,
            content,
            content_type="application/pdf"
        )

    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(buffer)

    return SimpleUploadedFile(
        name,
        buffer.getvalue(),
        content_type="application/pdf"
    )

def text(response):
    return response.content.decode()


def upload_resume(client, follow=False):
    return client.post(
        reverse("matcher:job_seeker_upload"),
        {"resume_file": make_pdf_file("resume.pdf")},
        follow=follow,
    )


def upload_employer_files(client, candidate_names, follow=False, **profile_fields):
    """Post the employer form; profile_fields are the scoring profile inputs, e.g. profile="skills-first"."""
    return client.post(
        reverse("matcher:employer_upload"),
        {
            "job_file": make_pdf_file("job.pdf"),
            "candidate_files": [make_pdf_file(name) for name in candidate_names],
            **profile_fields,
        },
        follow=follow,
    )


def custom_profile_fields(name="Location matters", **weights):
    """The upload form's custom profile inputs (default: Balanced weights)."""
    weights = {"skills": 40, "experience": 25, "education": 10, "location": 10,
               "work_arrangement": 10, "working_hours": 5, **weights}
    return {"profile": "custom", "profile_name": name, "strong_match_skills": "70",
            **{f"weight_{part}": str(weight) for part, weight in weights.items()}}


def load_records(collection):
    """What is saved in data/<collection>.json."""
    return JsonRepository().load(collection)


def save_resume():
    return JsonRepository().save("resumes", {"filename": "r.pdf", "skills": [{"skill": "Python"}]})


def match_jobs_to_resume():
    """Run the job search for the newest saved resume, as the app does."""
    return MatchingService.default().match_jobs_to_resume()


def raises(error_type, func, *args):
    """True if func(*args) raises error_type."""
    try:
        func(*args)
    except error_type:
        return True
    return False


# ---------- Pages ----------

def test_landing_page_loads():
    response = Client().get(reverse("matcher:landing"))
    assert response.status_code == 200
    assert "Job Seeker" in text(response) and "Employer" in text(response)


def test_upload_pages_load():
    for page in ("matcher:employer_upload", "matcher:job_seeker_upload"):
        assert Client().get(reverse(page)).status_code == 200


# ---------- Employer ----------

def test_employer_rejects_non_pdf_job_file():
    response = Client().post(
        reverse("matcher:employer_upload"),
        {"job_file": io.BytesIO(b"not a pdf"), "candidate_files": [make_pdf_file("c1.pdf")]},
    )
    assert response.status_code == 200
    assert "not a PDF" in text(response)


def test_employer_requires_at_least_one_resume():
    response = Client().post(reverse("matcher:employer_upload"), {"job_file": make_pdf_file("job.pdf")})
    assert response.status_code == 200
    assert "at least one candidate resume" in text(response)


@override_settings(MAX_CANDIDATES=2)
def test_employer_rejects_too_many_resumes():
    response = upload_employer_files(Client(), ["c1.pdf", "c2.pdf", "c3.pdf"])
    assert response.status_code == 200
    assert "at most 2 resumes" in text(response)


def test_employer_upload_redirects_to_results():
    with fake_gemini(comparison_reply(2)):
        response = upload_employer_files(Client(), ["c1.pdf", "c2.pdf"])
    assert response.status_code == 302
    assert response.url == reverse("matcher:employer_results")


def test_employer_results_are_ranked_with_strong_match():
    # Uploaded weakest first - the page must still rank the strong match first
    with fake_gemini(comparison_reply(3)):
        page = text(upload_employer_files(Client(), ["c3.pdf", "c2.pdf", "c1.pdf"], follow=True))
    assert "Junior Python Developer" in page  # job posting summary
    assert page.count("badge--strong") == 1  # one Strong Match badge
    # Resume 1 (c3.pdf) is the strong match, so it is ranked first
    assert page.index("c3.pdf") < page.index("c2.pdf") < page.index("c1.pdf")


def test_employer_ai_failure_shows_error_and_stays_on_page():
    with patch.object(MatchingService, "match_candidates_to_job", side_effect=MatchingError("AI failed")):
        response = upload_employer_files(Client(), ["c1.pdf"])
    assert response.status_code == 200
    assert "The AI could not process your upload" in text(response)


# ---------- Employer: scoring profiles ----------

def test_employer_page_offers_the_scoring_profiles():
    page = text(Client().get(reverse("matcher:employer_upload")))
    for name in ("Balanced", "Skills first", "Experience first", "Custom"):
        assert name in page
    assert 'value="balanced" checked' in page


def test_results_show_the_chosen_profile():
    with fake_gemini(comparison_reply(2)):
        page = text(upload_employer_files(Client(), ["c1.pdf", "c2.pdf"], follow=True, profile="experience-first"))
    assert "Scored with the <strong>Experience first</strong> profile" in page
    assert load_records("candidate_matches")[0]["profile"]["id"] == "experience-first"


def test_without_a_choice_the_balanced_profile_is_used():
    with fake_gemini(comparison_reply(1)):
        page = text(upload_employer_files(Client(), ["c1.pdf"], follow=True))
    assert "Scored with the <strong>Balanced</strong> profile" in page


def test_custom_profile_is_used_saved_and_offered_next_time():
    fields = custom_profile_fields(skills=20, location=30)
    with fake_gemini(comparison_reply(2)):
        page = text(upload_employer_files(Client(), ["c1.pdf", "c2.pdf"], follow=True, **fields))
    assert "Scored with the <strong>Location matters</strong> profile" in page
    assert [p["name"] for p in load_records("scoring_profiles")] == ["Location matters"]
    assert "Location matters" in text(Client().get(reverse("matcher:employer_upload")))


def test_invalid_custom_profile_shows_error_without_asking_the_ai():
    with fake_gemini() as gemini:
        response = upload_employer_files(Client(), ["c1.pdf"], **custom_profile_fields(skills=90))
    assert response.status_code == 200 and gemini.call_count == 0
    page = text(response)
    assert "The weights must add up to 100, not 150." in page
    assert 'value="custom" checked' in page and 'value="90"' in page  # what was typed is kept
    assert load_records("scoring_profiles") == [] and load_records("candidate_matches") == []


def test_unknown_profile_is_rejected():
    with fake_gemini() as gemini:
        response = upload_employer_files(Client(), ["c1.pdf"], profile="S999")
    assert gemini.call_count == 0
    assert "Choose one of the scoring profiles." in text(response)


def test_changing_profile_rescores_the_same_files_without_the_ai():
    with fake_gemini(comparison_reply(2)):
        upload_employer_files(Client(), ["c1.pdf", "c2.pdf"])
    with fake_gemini() as gemini:
        page = text(upload_employer_files(Client(), ["c1.pdf", "c2.pdf"], follow=True, profile="skills-first"))
    assert gemini.call_count == 0
    assert "Scored with the <strong>Skills first</strong> profile" in page
    assert [r["profile"]["id"] for r in load_records("candidate_matches")] == ["balanced", "skills-first"]


def test_results_pages_are_empty_before_any_upload():
    client = Client()
    assert "No candidates yet" in text(client.get(reverse("matcher:employer_results")))
    assert "No matches yet" in text(client.get(reverse("matcher:job_results")))


# ---------- Job seeker ----------

def test_job_seeker_requires_a_resume():
    response = Client().post(reverse("matcher:job_seeker_upload"), {})
    assert response.status_code == 200
    assert "Upload your resume" in text(response)


def test_job_seeker_upload_redirects_and_saves_resume():
    with fake_gemini(RESUME_REPLY, JOBS_REPLY):
        response = upload_resume(Client())
    assert response.status_code == 302
    assert response.url == reverse("matcher:job_results")
    records = load_records("resumes")
    assert len(records) == 1
    assert records[0]["id"] == "R001" and records[0]["filename"] == "resume.pdf"
    assert {"skill": "Python"} in records[0]["skills"]


def test_job_seeker_ai_failure_shows_error_and_saves_nothing():
    with fake_gemini():  # no replies: the AI fails
        response = upload_resume(Client())
    assert response.status_code == 200
    assert "The AI could not process your upload" in text(response)
    assert load_records("resumes") == []


def test_failed_job_search_still_saves_resume():
    with fake_gemini(RESUME_REPLY), \
            patch.object(MatchingService, "match_jobs_to_resume", side_effect=MatchingError("AI failed")):
        response = upload_resume(Client(), follow=True)
    assert "the job search failed" in text(response)
    assert len(load_records("resumes")) == 1


@override_settings(MAX_JOBS=2)
def test_suggested_jobs_are_saved_for_the_resume():
    resume = save_resume()
    with fake_gemini(JOBS_REPLY):
        record = match_jobs_to_resume()
    assert record["resume_id"] == resume["id"]
    assert len(record["jobs"]) == 2
    assert load_records("job_matches") == [record]


@override_settings(MAX_JOBS=2)
def test_suggested_jobs_are_sorted_and_cleaned():
    save_resume()
    reply = {"jobs": [
        {"title": "Low", "match_score": "40", "location": "Mars", "work_arrangement": "WFH"},
        {"title": "High", "match_score": 150, "industry": "Technology / IT"},
    ]}
    with fake_gemini(json.dumps(reply)):
        high, low = match_jobs_to_resume()["jobs"]
    assert (high["title"], high["match_score"]) == ("High", 100)
    assert (low["match_score"], low["location"], low["work_arrangement"]) == (40, "", "WFH")


@override_settings(MAX_JOBS=2)
def test_suggested_jobs_get_jobstreet_links_without_duplicates():
    save_resume()
    reply = {"jobs": [
        {"title": "Junior Python Developer"},
        {"title": "junior python developer"},
        {"title": ""},
        {"title": "C++ / Embedded Engineer"},
        {"title": "Data Analyst"},
    ]}
    with fake_gemini(json.dumps(reply)):
        record = match_jobs_to_resume()
    assert [job["url"] for job in record["jobs"]] == [
        "https://sg.jobstreet.com/junior-python-developer-jobs",
        "https://sg.jobstreet.com/c-embedded-engineer-jobs",
    ]


def test_job_search_without_a_saved_resume_raises():
    assert raises(MatchingError, match_jobs_to_resume)


def uploaded_client():
    """A visitor who has uploaded a resume and got the three JOBS_REPLY jobs."""
    client = Client()
    with fake_gemini(RESUME_REPLY, JOBS_REPLY):
        upload_resume(client)
    return client


def job_results(client, filters=None):
    return text(client.get(reverse("matcher:job_results"), filters or {}))


def shown_results(page):
    """The match scores and names on a results page, in the order shown."""
    scores = re.findall(r'score-ring__value">(\d+)%', page)
    names = re.findall(r'<h2>\s*([^<]+?)\s*<', page)
    return scores, names


def test_job_results_show_suggested_jobs_with_links():
    with fake_gemini(RESUME_REPLY, JOBS_REPLY):
        page = text(upload_resume(Client(), follow=True))
    assert "Software Developer" in page
    assert 'href="https://sg.jobstreet.com/software-developer-jobs"' in page
    assert "View jobs on Jobstreet" in page and "91%" in page and "Apply filters" in page


def test_other_visitors_do_not_see_your_jobs():
    uploaded_client()
    page = job_results(Client())
    assert "Software Developer" not in page
    assert "No matches yet" in page


@override_settings(AI_API_KEY="")
def test_without_the_ai_the_user_cannot_get_results():
    client = Client()
    page = text(upload_resume(client, follow=True))
    assert "The AI could not process your upload" in page
    assert load_records("resumes") == []
    assert "No matches yet" in job_results(client)


# ---------- Job filters ----------
# JOBS_REPLY: Software Developer (Central, WFH, Flexible, Technology / IT),
# Backend Engineer (East, Hybrid, Standard, Technology / IT),
# Data Analyst (West, On-site, Shift-based, Finance / Banking)

def test_no_filters_shows_all_jobs():
    assert "Showing 3 of 3 jobs" in job_results(uploaded_client())


def test_filter_by_location():
    page = job_results(uploaded_client(), {"locations": ["Central", "East"]})
    assert "Software Developer" in page and "Backend Engineer" in page
    assert "Data Analyst" not in page


def test_filters_combine():
    page = job_results(uploaded_client(), {"work_arrangement": ["Hybrid"], "industry": "Technology / IT"})
    assert "Showing 1 of 3 jobs" in page and "Backend Engineer" in page


def test_no_jobs_match_shows_message():
    assert "No jobs match these filters" in job_results(uploaded_client(), {"locations": ["North"]})


def test_unknown_filter_value_shows_all_jobs():
    assert "Showing 3 of 3 jobs" in job_results(uploaded_client(), {"locations": ["Mars"]})


def test_changing_filters_does_not_call_the_ai():
    client = uploaded_client()
    with fake_gemini() as gemini:
        job_results(client, {"locations": ["Central"]})
        job_results(client, {"industry": "Technology / IT"})
    assert gemini.call_count == 0


# ---------- Same output across runs ----------

def test_same_resume_gives_same_results_without_asking_the_ai_again():
    first = job_results(uploaded_client())  # 2 AI calls: read the resume, suggest jobs
    with fake_gemini() as gemini:  # no replies left - any AI call would fail
        second = text(upload_resume(Client(), follow=True))
    assert gemini.call_count == 0
    assert len(shown_results(first)[0]) == 3
    assert shown_results(second) == shown_results(first)
    assert len(load_records("resumes")) == 1 and len(load_records("job_matches")) == 1

def test_different_resume_is_sent_to_the_ai():
    uploaded_client()

    # Create another valid PDF with different file contents
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.add_metadata({
        "/Title": "Different Resume",
        "/Author": "Different Candidate",
    })
    writer.write(buffer)

    other = SimpleUploadedFile(
        "other.pdf",
        buffer.getvalue(),
        content_type="application/pdf"
    )

    with fake_gemini(RESUME_REPLY, JOBS_REPLY) as gemini:
        response = Client().post(
            reverse("matcher:job_seeker_upload"),
            {"resume_file": other}
        )

    assert response.status_code == 302
    assert gemini.call_count == 2
    assert len(load_records("resumes")) == 2
    assert len(load_records("job_matches")) == 2


def test_same_employer_files_give_same_ranking_without_asking_the_ai_again():
    with fake_gemini(comparison_reply(2)):
        first = text(upload_employer_files(Client(), ["c1.pdf", "c2.pdf"], follow=True))
    with fake_gemini() as gemini:
        second = text(upload_employer_files(Client(), ["c1.pdf", "c2.pdf"], follow=True))
    assert gemini.call_count == 0
    assert len(shown_results(first)[0]) == 2
    assert shown_results(second) == shown_results(first)
    assert len(load_records("candidate_matches")) == 1
