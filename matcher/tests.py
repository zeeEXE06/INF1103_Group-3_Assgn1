"""
Sprint 1 tests: UI is reachable and basic upload validation works.

Later sprints add tests for the Data/AI/Logic Managers per the spec's
testing requirements (PDF validation edge cases, save/load, corrupt
data handling, schema validation, scoring, ranking, mocked AI calls).
"""

import io

from django.test import TestCase
from django.urls import reverse


def make_pdf_file(name="resume.pdf", content=b"%PDF-1.4 fake pdf content"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, content, content_type="application/pdf")


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

    def test_results_page_shows_ranked_candidates(self):
        response = self.client.get(reverse("matcher:employer_results"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "#1")


class JobSeekerWorkflowTests(TestCase):
    def test_upload_page_loads(self):
        response = self.client.get(reverse("matcher:job_seeker_upload"))
        self.assertEqual(response.status_code, 200)

    def test_valid_submission_redirects_to_results(self):
        response = self.client.post(
            reverse("matcher:job_seeker_upload"),
            {
                "resume_file": make_pdf_file("resume.pdf"),
                "work_arrangement": "wfh",
                "locations": ["central", "north"],
                "working_hours": "flexible",
            },
        )
        self.assertRedirects(response, reverse("matcher:job_results"))

    def test_missing_preferences_reshows_form_with_errors(self):
        response = self.client.post(
            reverse("matcher:job_seeker_upload"),
            {"resume_file": make_pdf_file("resume.pdf")},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")

    def test_results_page_shows_ranked_jobs(self):
        response = self.client.get(reverse("matcher:job_results"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "#1")
