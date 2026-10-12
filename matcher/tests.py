"""
Tests for the Resume & Job Matcher. Run them with:

    python run_tests.py

Every test is a plain function. No test calls the real AI, and run_tests.py
gives each test its own empty data folder.
"""

import io
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse
from google.genai import errors

from .managers.ai_manager import (
    comparison_schema_problem,
    extract_resume,
    generate,
    get_client,
    jobs_schema_problem,
    parse_json_reply,
    request_json,
    resume_schema_problem,
)
from .managers.data_manager import load_records, save_record
from .managers.logic_manager import (
    calculate_score,
    filter_jobs,
    is_strong_match,
    rank_candidates,
    rank_jobs,
    select_top_jobs,
    to_score,
)
from .services.matching_service import match_candidates_to_job, match_jobs_to_resume


# ---------- Helpers ----------

def make_pdf_file(name="resume.pdf", content=b"%PDF-1.4 fake pdf content"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


def text(response):
    return response.content.decode()


def upload_resume(client, follow=False):
    return client.post(
        reverse("matcher:job_seeker_upload"),
        {"resume_file": make_pdf_file("resume.pdf")},
        follow=follow,
    )


def upload_employer_files(client, candidate_names, follow=False):
    return client.post(
        reverse("matcher:employer_upload"),
        {
            "job_file": make_pdf_file("job.pdf"),
            "candidate_files": [make_pdf_file(name) for name in candidate_names],
        },
        follow=follow,
    )


def save_resume():
    return save_record("resumes", {"filename": "r.pdf", "skills": [{"skill": "Python"}]})


def candidate(matched=3, missing=0, **matches):
    return {"matched_skills": ["s"] * matched, "missing_skills": ["m"] * missing, **matches}


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


@override_settings(AI_MODE="mock")
def test_employer_upload_redirects_to_results():
    response = upload_employer_files(Client(), ["c1.pdf", "c2.pdf"])
    assert response.status_code == 302
    assert response.url == reverse("matcher:employer_results")


@override_settings(AI_MODE="mock", DATA_MODE="live")
def test_employer_results_are_ranked_with_strong_match():
    # Uploaded weakest first - the page must still rank the strong match first
    page = text(upload_employer_files(Client(), ["c3.pdf", "c2.pdf", "c1.pdf"], follow=True))
    assert "Junior Python Developer" in page  # job posting summary
    assert page.count("Strong Match") == 1
    # Mock: resume 1 (c3.pdf) is the strong match, so it is ranked first
    assert page.index("c3.pdf") < page.index("c2.pdf") < page.index("c1.pdf")


@override_settings(DATA_MODE="live")
def test_employer_ai_failure_shows_error_and_stays_on_page():
    with patch("matcher.views.match_candidates_to_job", side_effect=ValueError("AI failed")):
        response = upload_employer_files(Client(), ["c1.pdf"])
    assert response.status_code == 200
    assert "The AI could not process your upload" in text(response)


@override_settings(DATA_MODE="debug")
def test_employer_results_debug_mode_shows_sample_data():
    page = text(Client().get(reverse("matcher:employer_results")))
    assert "#1" in page and "John Tan" in page


@override_settings(DATA_MODE="live")
def test_results_pages_are_empty_before_any_upload():
    client = Client()
    assert "No candidates yet" in text(client.get(reverse("matcher:employer_results")))
    assert "No matches yet" in text(client.get(reverse("matcher:job_results")))


def test_compare_candidates_marks_skipped_resume_unreadable():
    reply = {"job": {"title": "Dev"}, "candidates": [
        {"resume_number": 1, "name": "Ann", "matched_skills": ["Python"], "missing_skills": [],
         "experience_match": True, "location_match": True},
    ]}
    with patch("matcher.services.matching_service.compare_candidates", return_value=reply):
        record = match_candidates_to_job(make_pdf_file("job.pdf"), [make_pdf_file("ann.pdf"), make_pdf_file("bad.pdf")])
    ann, bad = record["candidates"]
    assert (ann["name"], ann["filename"], ann["match_score"], ann["strong_match"]) == ("Ann", "ann.pdf", 75, True)
    assert bad["unreadable"] and bad["filename"] == "bad.pdf"
    assert load_records("candidate_matches") == [record]


def test_compare_candidates_raises_when_ai_fails():
    with patch("matcher.services.matching_service.compare_candidates", return_value=None):
        assert raises(ValueError, match_candidates_to_job, make_pdf_file("job.pdf"), [make_pdf_file("a.pdf")])


# ---------- Job seeker ----------

def test_job_seeker_requires_a_resume():
    response = Client().post(reverse("matcher:job_seeker_upload"), {})
    assert response.status_code == 200
    assert "Upload your resume" in text(response)


@override_settings(AI_MODE="mock")
def test_job_seeker_upload_redirects_and_saves_resume():
    response = upload_resume(Client())
    assert response.status_code == 302
    assert response.url == reverse("matcher:job_results")
    records = load_records("resumes")
    assert len(records) == 1
    assert records[0]["id"] == "R001" and records[0]["filename"] == "resume.pdf"
    assert {"skill": "Python"} in records[0]["skills"]


def test_job_seeker_ai_failure_shows_error_and_saves_nothing():
    with patch("matcher.services.matching_service.extract_resume", return_value=None):
        response = upload_resume(Client())
    assert response.status_code == 200
    assert "The AI could not process your upload" in text(response)
    assert load_records("resumes") == []


@override_settings(AI_MODE="mock")
def test_failed_job_search_still_saves_resume():
    with patch("matcher.views.match_jobs_to_resume", side_effect=ValueError("AI failed")):
        response = upload_resume(Client(), follow=True)
    assert "the job search failed" in text(response)
    assert len(load_records("resumes")) == 1


@override_settings(AI_MODE="mock", MAX_JOBS=2)
def test_suggested_jobs_are_saved_for_the_resume():
    resume = save_resume()
    record = match_jobs_to_resume()
    assert record["resume_id"] == resume["id"]
    assert len(record["jobs"]) == 1
    assert load_records("job_matches") == [record]


@override_settings(MAX_JOBS=2)
def test_suggested_jobs_are_sorted_and_cleaned():
    save_resume()
    reply = {"jobs": [
        {"title": "Low", "match_score": "40", "location": "Mars", "work_arrangement": "WFH"},
        {"title": "High", "match_score": 150, "industry": "Technology / IT"},
    ]}
    with patch("matcher.services.matching_service.suggest_jobs", return_value=reply):
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
    with patch("matcher.services.matching_service.suggest_jobs", return_value=reply):
        record = match_jobs_to_resume()
    assert [job["url"] for job in record["jobs"]] == [
        "https://sg.jobstreet.com/junior-python-developer-jobs",
        "https://sg.jobstreet.com/c-embedded-engineer-jobs",
    ]


def test_job_search_without_a_saved_resume_raises():
    assert raises(ValueError, match_jobs_to_resume)


@override_settings(AI_MODE="mock", DATA_MODE="live")
def test_job_results_show_suggested_jobs_with_links():
    page = text(upload_resume(Client(), follow=True))
    assert "Junior Python Developer" in page
    assert 'href="https://sg.jobstreet.com/junior-python-developer-jobs"' in page
    assert "View jobs on Jobstreet" in page and "82%" in page and "Apply filters" in page


@override_settings(AI_MODE="mock", DATA_MODE="live")
def test_filters_apply_to_suggested_jobs():
    client = Client()
    upload_resume(client)
    url = reverse("matcher:job_results")
    assert "Junior Python Developer" in text(client.get(url, {"work_arrangement": ["Hybrid"], "locations": ["Central"]}))
    page = text(client.get(url, {"locations": ["North"]}))
    assert "Junior Python Developer" not in page
    assert "No jobs match these filters" in page


@override_settings(AI_MODE="mock", DATA_MODE="live")
def test_changing_filters_does_not_call_the_ai():
    client = Client()
    upload_resume(client)
    with patch("matcher.services.matching_service.suggest_jobs") as ai_text, \
            patch("matcher.services.matching_service.extract_resume") as ai_pdf:
        client.get(reverse("matcher:job_results"), {"locations": ["Central"]})
        client.get(reverse("matcher:job_results"), {"industry": "Technology / IT"})
    ai_text.assert_not_called()
    ai_pdf.assert_not_called()


@override_settings(AI_MODE="mock", DATA_MODE="live")
def test_other_visitors_do_not_see_your_jobs():
    upload_resume(Client())
    page = text(Client().get(reverse("matcher:job_results")))
    assert "Junior Python Developer" not in page
    assert "No matches yet" in page


# ---------- Job filters (sample data) ----------
# Sample jobs: Software Developer (Central, WFH, Flexible, Technology / IT),
# Backend Engineer (East, Hybrid, Standard, Technology / IT),
# Data Analyst (West, On-site, Shift-based, Finance / Banking)

def sample_job_results(filters):
    return text(Client().get(reverse("matcher:job_results"), filters))


@override_settings(DATA_MODE="debug")
def test_no_filters_shows_all_jobs():
    assert "Showing 3 of 3 jobs" in sample_job_results({})


@override_settings(DATA_MODE="debug")
def test_filter_by_location():
    page = sample_job_results({"locations": ["Central", "East"]})
    assert "Software Developer" in page and "Backend Engineer" in page
    assert "Data Analyst" not in page


@override_settings(DATA_MODE="debug")
def test_filters_combine():
    page = sample_job_results({"work_arrangement": ["Hybrid"], "industry": "Technology / IT"})
    assert "Showing 1 of 3 jobs" in page and "Backend Engineer" in page


@override_settings(DATA_MODE="debug")
def test_no_jobs_match_shows_message():
    assert "No jobs match these filters" in sample_job_results({"locations": ["North"]})


@override_settings(DATA_MODE="debug")
def test_unknown_filter_value_shows_all_jobs():
    assert "Showing 3 of 3 jobs" in sample_job_results({"locations": ["Mars"]})


# ---------- AI Manager ----------

@override_settings(AI_MODE="mock")
def test_mock_mode_works_without_api_key():
    assert set(extract_resume(make_pdf_file())) == {"education", "experience", "skills"}


@override_settings(AI_MODE="live", AI_API_KEY="test", AI_MODEL="main", AI_FALLBACK_MODELS=["backup"])
def test_busy_model_falls_back_to_next_model():
    busy = errors.ServerError(503, {"error": {"code": 503, "message": "high demand"}})
    client = MagicMock()
    client.models.generate_content.side_effect = [busy, MagicMock(text="ok")]
    with patch("matcher.managers.ai_manager.get_client", return_value=client):
        assert generate("hi", None) == "ok"
    assert [c.kwargs["model"] for c in client.models.generate_content.call_args_list] == ["main", "backup"]


@override_settings(AI_MODE="live", AI_API_KEY="test", AI_MODEL="main", AI_FALLBACK_MODELS=["backup"])
def test_bad_key_error_does_not_fall_back():
    client = MagicMock()
    client.models.generate_content.side_effect = errors.ClientError(
        400, {"error": {"code": 400, "message": "API key not valid"}}
    )
    with patch("matcher.managers.ai_manager.get_client", return_value=client):
        assert raises(errors.ClientError, generate, "hi", None)
    assert client.models.generate_content.call_count == 1


@override_settings(AI_MODE="live", AI_API_KEY="test")
def test_broken_or_wrong_shape_reply_is_asked_again():
    good = '{"jobs": [{"title": "Dev"}]}'
    for bad in ('{"broken', '{"jobs": "none"}'):
        with patch("matcher.managers.ai_manager.generate", side_effect=[bad, good]) as gen:
            assert request_json(lambda: "hi", jobs_schema_problem, "") == {"jobs": [{"title": "Dev"}]}
        assert gen.call_count == 2


@override_settings(AI_MODE="live", AI_API_KEY="test")
def test_gives_up_after_repeated_wrong_shape():
    with patch("matcher.managers.ai_manager.generate", return_value='{"jobs": "none"}') as gen:
        assert request_json(lambda: "hi", jobs_schema_problem, "") is None
    assert gen.call_count == 2


@override_settings(AI_MODE="live", AI_API_KEY="")
def test_api_failure_returns_none_instead_of_crashing():
    assert extract_resume(make_pdf_file()) is None


@override_settings(AI_MODE="live", AI_API_KEY="")
def test_missing_api_key_gives_clear_error():
    assert raises(RuntimeError, get_client)


def test_schema_checks():
    assert resume_schema_problem({"education": [], "experience": [{}], "skills": []}) is None
    assert resume_schema_problem({"education": [], "skills": []}) is not None
    assert resume_schema_problem({"education": ["BSc"], "experience": [], "skills": []}) is not None
    assert jobs_schema_problem({"jobs": [{"title": 5}]}) is not None
    assert comparison_schema_problem({"job": {}, "candidates": [{"resume_number": 1}]}) is None
    assert comparison_schema_problem({"job": {}, "candidates": [{"resume_number": "1"}]}) is not None
    assert comparison_schema_problem({"candidates": []}) is not None


def test_parse_json_reply():
    assert parse_json_reply('```json\n{"skills": [{"skill": "SQL"}]}\n```') == {"skills": [{"skill": "SQL"}]}
    assert parse_json_reply('Here are the jobs I found:\n{"jobs": []}\nGood luck!') == {"jobs": []}
    assert parse_json_reply("PDF received") is None
    assert parse_json_reply("[1, 2]") is None


# ---------- Data Manager ----------

def test_missing_file_loads_as_empty():
    assert load_records("resumes") == []


def test_save_then_load():
    save_record("resumes", {"filename": "a.pdf"})
    save_record("resumes", {"filename": "b.pdf"})
    records = load_records("resumes")
    assert [r["id"] for r in records] == ["R001", "R002"]
    assert records[1]["filename"] == "b.pdf"


def test_broken_file_is_kept_as_backup():
    (settings.DATA_DIR / "resumes.json").write_text("{not json")
    assert load_records("resumes") == []
    save_record("resumes", {"filename": "a.pdf"})
    assert len(load_records("resumes")) == 1
    assert (settings.DATA_DIR / "resumes.broken.json").read_text() == "{not json"


# ---------- Logic Manager ----------

def test_select_top_jobs_removes_duplicates_sorts_and_caps():
    jobs = [
        {"title": "A", "url": "/a", "match_score": 50},
        {"title": "a", "url": "/a", "match_score": 99},
        {"title": "B", "url": "/b", "match_score": 80},
        {"title": "C", "url": "/c", "match_score": 70},
    ]
    assert [j["title"] for j in select_top_jobs(jobs, 2)] == ["B", "C"]
    assert [j["title"] for j in select_top_jobs(jobs, 10)] == ["B", "C", "A"]


def test_to_score_keeps_scores_between_0_and_100():
    assert [to_score(v) for v in (82, "40.6", 150, -5, None, "high")] == [82, 41, 100, 0, 0, 0]


def test_rank_jobs_sorts_by_score_and_fills_missing_fields():
    ranked = rank_jobs([{"title": "B", "match_score": 50}, {"title": "A", "match_score": 90}])
    assert [(j["rank"], j["title"]) for j in ranked] == [(1, "A"), (2, "B")]
    assert ranked[0]["location"] == ""


def test_filter_jobs_works_on_saved_jobs():
    jobs = [
        {"title": "A", "location": "West", "work_arrangement": "On-site",
         "working_hours": "Standard", "industry": "Manufacturing"},
        {"title": "B", "location": "Central", "work_arrangement": "Hybrid",
         "working_hours": "Standard", "industry": "Technology / IT"},
    ]
    assert [j["title"] for j in filter_jobs(jobs, [], ["West"], [], "")] == ["A"]
    assert [j["title"] for j in filter_jobs(jobs, ["Hybrid"], [], ["Standard"], "Technology / IT")] == ["B"]
    assert len(filter_jobs(jobs, [], [], [], "")) == 2


def test_full_match_scores_100():
    full = candidate(experience_match=True, education_match=True, location_match=True,
                     work_arrangement_match=True, working_hours_match=True)
    assert calculate_score(full) == 100


def test_score_weights():
    # Half the skills (20) + experience (25) + location (10)
    assert calculate_score(candidate(matched=1, missing=1, experience_match=True, location_match=True)) == 55
    assert calculate_score(candidate(matched=0, missing=0)) == 0


def test_strong_match_needs_skills_experience_and_location():
    assert is_strong_match(candidate(7, 3, experience_match=True, location_match=True))
    assert not is_strong_match(candidate(6, 4, experience_match=True, location_match=True))
    assert not is_strong_match(candidate(3, 0, experience_match=False, location_match=True))
    assert not is_strong_match(candidate(3, 0, experience_match=True, location_match=False))


def test_rank_candidates_puts_unreadable_last():
    ranked = rank_candidates([
        {"name": "Unreadable", "match_score": 0, "unreadable": True},
        {"name": "Low", "match_score": 10},
        {"name": "High", "match_score": 80},
    ])
    assert [(c["rank"], c["name"]) for c in ranked] == [(1, "High"), (2, "Low"), (3, "Unreadable")]
