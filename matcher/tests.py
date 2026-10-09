"""
Sprint 1 tests: pages load and upload checks work.

TODO (Sprint 3): scoring, "Strong Match" rule and ranking tests
TODO (Sprint 4): AI response checks (mock mode + missing key tests below)
"""

import io
import json
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse


def make_pdf_file(name="resume.pdf", content=b"%PDF-1.4 fake pdf content"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, content, content_type="application/pdf")


class TempDataDirMixin:
    """Save data to a temp folder so tests never touch the real data/ folder."""

    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_dir = Path(tmp.name)
        override = override_settings(DATA_DIR=self.data_dir)
        override.enable()
        self.addCleanup(override.disable)


class LandingPageTests(TestCase):
    def test_landing_page_loads(self):
        response = self.client.get(reverse("matcher:landing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Job Seeker")
        self.assertContains(response, "Employer")


class EmployerWorkflowTests(TestCase):
    def test_upload_page_loads(self):
        response = self.client.get(reverse("matcher:employer_upload"))
        self.assertEqual(response.status_code, 200)

    def test_rejects_non_pdf_job_file(self):
        response = self.client.post(
            reverse("matcher:employer_upload"),
            {
                "job_file": io.BytesIO(b"not a pdf"),
                "candidate_files": [make_pdf_file("c1.pdf")],
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)  # re-rendered with errors
        self.assertContains(response, "not a PDF")

    def test_requires_at_least_one_candidate_file(self):
        response = self.client.post(
            reverse("matcher:employer_upload"),
            {"job_file": make_pdf_file("job.pdf")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "at least one candidate resume")

    def test_valid_upload_redirects_to_results(self):
        response = self.client.post(
            reverse("matcher:employer_upload"),
            {
                "job_file": make_pdf_file("job.pdf"),
                "candidate_files": [make_pdf_file("c1.pdf"), make_pdf_file("c2.pdf")],
            },
        )
        self.assertRedirects(response, reverse("matcher:employer_results"))

    @override_settings(DATA_MODE="debug")
    def test_results_page_shows_ranked_candidates(self):
        response = self.client.get(reverse("matcher:employer_results"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "#1")


@override_settings(AI_MODE="mock")
class JobSeekerWorkflowTests(TempDataDirMixin, TestCase):
    def test_upload_page_loads(self):
        response = self.client.get(reverse("matcher:job_seeker_upload"))
        self.assertEqual(response.status_code, 200)

    def test_valid_submission_redirects_to_results(self):
        response = self.client.post(
            reverse("matcher:job_seeker_upload"),
            {"resume_file": make_pdf_file("resume.pdf")},
        )
        self.assertRedirects(response, reverse("matcher:job_results"))

    def test_valid_submission_saves_parsed_resume(self):
        from .managers.data_manager import load_records

        self.client.post(
            reverse("matcher:job_seeker_upload"),
            {"resume_file": make_pdf_file("resume.pdf")},
        )
        records = load_records("resumes")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], "R001")
        self.assertEqual(records[0]["filename"], "resume.pdf")
        self.assertIn({"skill": "Python"}, records[0]["skills"])

    def test_unreadable_ai_reply_shows_error_and_saves_nothing(self):
        from unittest.mock import patch

        from .managers.data_manager import load_records

        with patch("matcher.views.ask_ai", return_value="Sorry, I can't help."):
            response = self.client.post(
                reverse("matcher:job_seeker_upload"),
                {"resume_file": make_pdf_file("resume.pdf")},
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Could not read the resume")
        self.assertEqual(load_records("resumes"), [])

    def test_failed_ai_call_shows_error_and_saves_nothing(self):
        from unittest.mock import patch

        from .managers.data_manager import load_records

        with patch("matcher.views.ask_ai", side_effect=RuntimeError("401 Unauthorized")):
            with self.assertLogs("matcher.views", level="ERROR"):
                response = self.client.post(
                    reverse("matcher:job_seeker_upload"),
                    {"resume_file": make_pdf_file("resume.pdf")},
                )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The AI service is unavailable")
        self.assertEqual(load_records("resumes"), [])

    def test_missing_resume_reshows_form_with_errors(self):
        response = self.client.post(reverse("matcher:job_seeker_upload"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

    @override_settings(DATA_MODE="debug")
    def test_results_page_shows_ranked_jobs(self):
        response = self.client.get(reverse("matcher:job_results"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "#1")


class DataModeTests(TempDataDirMixin, TestCase):
    @override_settings(DATA_MODE="debug")
    def test_debug_mode_shows_sample_data(self):
        response = self.client.get(reverse("matcher:employer_results"))
        self.assertContains(response, "John Tan")

    @override_settings(DATA_MODE="live")
    def test_live_mode_shows_empty_state_until_sprint_2(self):
        response = self.client.get(reverse("matcher:employer_results"))
        self.assertNotContains(response, "John Tan")
        self.assertContains(response, "No candidates yet")

        response = self.client.get(reverse("matcher:job_results"))
        self.assertContains(response, "No matches yet")


@override_settings(DATA_MODE="debug")
class JobFilterTests(TestCase):
    # Sample jobs: Software Developer (Central, WFH, Flexible, Technology / IT),
    # Backend Engineer (East, Hybrid, Standard, Technology / IT),
    # Data Analyst (West, On-site, Shift-based, Finance / Banking)

    def get_results(self, filters):
        return self.client.get(reverse("matcher:job_results"), filters)

    def test_no_filters_shows_all_jobs(self):
        response = self.get_results({})
        self.assertContains(response, "Showing 3 of 3 jobs")

    def test_filter_by_location(self):
        response = self.get_results({"locations": ["Central", "East"]})
        self.assertContains(response, "Software Developer")
        self.assertContains(response, "Backend Engineer")
        self.assertNotContains(response, "Data Analyst")

    def test_filters_combine(self):
        response = self.get_results({"work_arrangement": ["Hybrid"], "industry": "Technology / IT"})
        self.assertContains(response, "Showing 1 of 3 jobs")
        self.assertContains(response, "Backend Engineer")

    def test_no_jobs_match_shows_message(self):
        response = self.get_results({"locations": ["North"]})
        self.assertContains(response, "No jobs match these filters")

    def test_bad_filter_value_shows_all_jobs(self):
        response = self.get_results({"locations": ["Mars"]})
        self.assertContains(response, "Showing 3 of 3 jobs")


class AIManagerTests(TestCase):
    @override_settings(AI_MODE="mock")
    def test_mock_mode_returns_reply_without_api_key(self):
        from .managers.ai_manager import ask_ai

        from .managers.ai_manager import parse_json_reply

        reply = parse_json_reply(ask_ai("test prompt", make_pdf_file()))
        self.assertEqual(set(reply), {"education", "experience", "skills"})

    @override_settings(AI_MODE="live", AI_API_KEY="test", AI_MODEL="main", AI_FALLBACK_MODELS=["backup"])
    def test_busy_model_falls_back_to_next_model(self):
        from unittest.mock import MagicMock, patch

        from google.genai import errors

        from .managers.ai_manager import generate

        busy = errors.ServerError(503, {"error": {"code": 503, "message": "high demand"}})
        client = MagicMock()
        client.models.generate_content.side_effect = [busy, MagicMock(text="ok")]

        with patch("matcher.managers.ai_manager.get_client", return_value=client):
            with self.assertLogs("matcher.managers.ai_manager", level="WARNING"):
                self.assertEqual(generate("hi", None), "ok")
        models = [c.kwargs["model"] for c in client.models.generate_content.call_args_list]
        self.assertEqual(models, ["main", "backup"])

    @override_settings(AI_MODE="live", AI_API_KEY="test", AI_MODEL="main", AI_FALLBACK_MODELS=["backup"])
    def test_bad_key_error_does_not_fall_back(self):
        from unittest.mock import MagicMock, patch

        from google.genai import errors

        from .managers.ai_manager import generate

        client = MagicMock()
        client.models.generate_content.side_effect = errors.ClientError(
            400, {"error": {"code": 400, "message": "API key not valid"}}
        )
        with patch("matcher.managers.ai_manager.get_client", return_value=client):
            with self.assertRaises(errors.ClientError):
                generate("hi", None)
        self.assertEqual(client.models.generate_content.call_count, 1)

    def test_parse_json_reply_strips_code_fences(self):
        from .managers.ai_manager import parse_json_reply

        reply = '```json\n{"skills": [{"skill": "SQL"}]}\n```'
        self.assertEqual(parse_json_reply(reply), {"skills": [{"skill": "SQL"}]})

    def test_parse_json_reply_ignores_text_around_json(self):
        from .managers.ai_manager import parse_json_reply

        reply = 'Here are the jobs I found:\n{"jobs": []}\nGood luck!'
        self.assertEqual(parse_json_reply(reply), {"jobs": []})

    def test_parse_json_reply_rejects_non_json(self):
        from .managers.ai_manager import parse_json_reply

        self.assertIsNone(parse_json_reply("PDF received"))
        self.assertIsNone(parse_json_reply("[1, 2]"))

    @override_settings(AI_MODE="live", AI_API_KEY="")
    def test_live_mode_without_key_gives_clear_error(self):
        from .managers.ai_manager import get_client

        with self.assertRaisesMessage(RuntimeError, "AI_API_KEY is not set"):
            get_client()


class DataManagerTests(TempDataDirMixin, TestCase):
    def test_missing_file_loads_as_empty(self):
        from .managers.data_manager import load_records

        self.assertEqual(load_records("resumes"), [])

    def test_save_then_load(self):
        from .managers.data_manager import load_records, save_record

        save_record("resumes", {"filename": "a.pdf"})
        save_record("resumes", {"filename": "b.pdf"})
        records = load_records("resumes")
        self.assertEqual([r["id"] for r in records], ["R001", "R002"])
        self.assertEqual(records[1]["filename"], "b.pdf")

    def test_broken_file_is_kept_as_backup(self):
        from .managers.data_manager import load_records, save_record

        (self.data_dir / "resumes.json").write_text("{not json")
        self.assertEqual(load_records("resumes"), [])

        save_record("resumes", {"filename": "a.pdf"})
        self.assertEqual(len(load_records("resumes")), 1)
        self.assertEqual((self.data_dir / "resumes.broken.json").read_text(), "{not json")


@override_settings(AI_MODE="mock", MAX_JOBS=2)
class JobSearchTests(TempDataDirMixin, TestCase):
    def test_sorts_by_score_and_cleans_ai_values(self):
        from unittest.mock import patch

        from .services.matching_service import match_jobs_to_resume

        self.save_resume()
        reply = json.dumps({"jobs": [
            {"title": "Low", "match_score": "40", "location": "Mars", "work_arrangement": "WFH"},
            {"title": "High", "match_score": 150, "industry": "Technology / IT"},
        ]})
        with patch("matcher.services.matching_service.ask_ai_text", return_value=reply):
            record = match_jobs_to_resume()
        high, low = record["jobs"]
        self.assertEqual((high["title"], high["match_score"]), ("High", 100))
        self.assertEqual((low["match_score"], low["location"], low["work_arrangement"]), (40, "", "WFH"))

    def save_resume(self):
        from .managers.data_manager import save_record

        return save_record("resumes", {"filename": "r.pdf", "skills": [{"skill": "Python"}]})

    def test_saves_jobs_for_resume(self):
        from .managers.data_manager import load_records
        from .services.matching_service import match_jobs_to_resume

        resume = self.save_resume()
        record = match_jobs_to_resume()
        self.assertEqual(record["resume_id"], resume["id"])
        self.assertEqual(len(record["jobs"]), 1)
        self.assertEqual(load_records("job_matches"), [record])

    def test_builds_jobstreet_links_skips_duplicates_and_caps_at_max_jobs(self):
        from unittest.mock import patch

        from .services.matching_service import match_jobs_to_resume

        self.save_resume()
        reply = json.dumps({"jobs": [
            {"title": "Junior Python Developer"},
            {"title": "junior python developer"},
            {"title": ""},
            {"title": "C++ / Embedded Engineer"},
            {"title": "Data Analyst"},
        ]})
        with patch("matcher.services.matching_service.ask_ai_text", return_value=reply):
            record = match_jobs_to_resume()
        self.assertEqual([job["url"] for job in record["jobs"]], [
            "https://sg.jobstreet.com/junior-python-developer-jobs",
            "https://sg.jobstreet.com/c-embedded-engineer-jobs",
        ])

    def test_no_saved_resume_raises(self):
        from .services.matching_service import match_jobs_to_resume

        with self.assertRaises(ValueError):
            match_jobs_to_resume()

    def test_failed_job_search_still_saves_resume(self):
        from unittest.mock import patch

        from .managers.data_manager import load_records

        with patch("matcher.views.match_jobs_to_resume", side_effect=RuntimeError("boom")):
            with self.assertLogs("matcher.views", level="ERROR"):
                response = self.client.post(
                    reverse("matcher:job_seeker_upload"),
                    {"resume_file": make_pdf_file("resume.pdf")},
                    follow=True,
                )
        self.assertContains(response, "the job search failed")
        self.assertEqual(len(load_records("resumes")), 1)


@override_settings(AI_MODE="mock", DATA_MODE="live")
class JobSuggestionResultsTests(TempDataDirMixin, TestCase):
    def upload_resume(self):
        return self.client.post(
            reverse("matcher:job_seeker_upload"),
            {"resume_file": make_pdf_file("resume.pdf")},
            follow=True,
        )

    def test_results_show_suggested_jobs_with_jobstreet_links(self):
        response = self.upload_resume()
        self.assertContains(response, "Junior Python Developer")
        self.assertContains(response, 'href="https://sg.jobstreet.com/junior-python-developer-jobs"')
        self.assertContains(response, "View jobs on Jobstreet")
        self.assertContains(response, "82%")
        self.assertContains(response, "Apply filters")

    def test_filters_apply_to_suggested_jobs(self):
        self.upload_resume()
        url = reverse("matcher:job_results")

        response = self.client.get(url, {"work_arrangement": ["Hybrid"], "locations": ["Central"]})
        self.assertContains(response, "Junior Python Developer")

        response = self.client.get(url, {"locations": ["North"]})
        self.assertNotContains(response, "Junior Python Developer")
        self.assertContains(response, "No jobs match these filters")

    def test_changing_filters_does_not_call_the_ai(self):
        from unittest.mock import patch

        self.upload_resume()
        with patch("matcher.services.matching_service.ask_ai_text") as ai_text, \
                patch("matcher.views.ask_ai") as ai_pdf:
            self.client.get(reverse("matcher:job_results"), {"locations": ["Central"]})
            self.client.get(reverse("matcher:job_results"), {"industry": "Technology / IT"})
        ai_text.assert_not_called()
        ai_pdf.assert_not_called()

    def test_other_visitors_do_not_see_your_jobs(self):
        self.upload_resume()
        self.client.cookies.clear()
        response = self.client.get(reverse("matcher:job_results"))
        self.assertNotContains(response, "Junior Python Developer")
        self.assertContains(response, "No matches yet")


class LogicManagerTests(TestCase):
    def test_rank_jobs_sorts_by_score_and_fills_missing_fields(self):
        from .managers.logic_manager import rank_jobs

        ranked = rank_jobs([{"title": "B", "match_score": 50}, {"title": "A", "match_score": 90}])
        self.assertEqual([(j["rank"], j["title"]) for j in ranked], [(1, "A"), (2, "B")])
        self.assertEqual(ranked[0]["location"], "")

    def test_filter_jobs_works_on_saved_job_dicts(self):
        from .managers.logic_manager import filter_jobs

        jobs = [
            {"title": "A", "location": "West", "work_arrangement": "On-site",
             "working_hours": "Standard", "industry": "Manufacturing"},
            {"title": "B", "location": "Central", "work_arrangement": "Hybrid",
             "working_hours": "Standard", "industry": "Technology / IT"},
        ]
        self.assertEqual([j["title"] for j in filter_jobs(jobs, [], ["West"], [], "")], ["A"])
        self.assertEqual([j["title"] for j in filter_jobs(jobs, ["Hybrid"], [], ["Standard"], "Technology / IT")], ["B"])
        self.assertEqual(len(filter_jobs(jobs, [], [], [], "")), 2)
