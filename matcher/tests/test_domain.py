"""
Tests for the domain classes in matcher/domain: each one keeps its data
safe from outside changes and converts to and from saved records.
"""

from ..domain.job import JobPosting, JobSuggestion
from ..domain.resume import Resume


# ---------- Resume ----------

SAVED_RESUME = {
    "id": "R001",
    "file_hash": "abc123",
    "filename": "resume.pdf",
    "uploaded_at": "2026-11-04T10:00:00+00:00",
    "education": [{"qualification": "B.Sc.", "institution": "Sample University"}],
    "experience": [{"job_title": "Developer Intern", "company": "Sample Company"}],
    "skills": [{"skill": "Python"}, {"skill": " "}, {"skill": "Django"}],
}


def test_resume_round_trips_through_a_saved_record():
    assert Resume.from_dict(SAVED_RESUME).to_dict() == SAVED_RESUME


def test_unsaved_resume_has_no_id():
    resume = Resume("resume.pdf", "abc123")
    assert resume.id is None
    assert "id" not in resume.to_dict()


def test_resume_skill_names_leave_out_blanks():
    assert Resume.from_dict(SAVED_RESUME).skill_names == ["Python", "Django"]


def test_resume_cannot_be_changed_from_outside():
    skills = [{"skill": "Python"}]
    resume = Resume("resume.pdf", "abc123", skills=skills)

    skills.append({"skill": "Java"})
    resume.skills.append({"skill": "Go"})
    resume.skills[0]["skill"] = "C"

    assert resume.skill_names == ["Python"]


def test_old_resume_record_loads_with_defaults():
    resume = Resume.from_dict({"id": "R002", "filename": "old.pdf"})
    assert resume.education == [] and resume.skills == []
    assert resume.details_for_ai() == {"education": [], "experience": [], "skills": []}


# ---------- JobSuggestion and JobPosting ----------

SAVED_JOB = {
    "title": "Software Developer",
    "url": "https://sg.jobstreet.com/software-developer-jobs",
    "match_score": 91,
    "location": "Central",
    "work_arrangement": "WFH",
    "working_hours": "Flexible",
    "industry": "Technology / IT",
    "matched_skills": ["Python", "Django"],
    "match_reason": "Uses the candidate's Python and Django skills.",
}

SAVED_POSTING = {
    "filename": "job.pdf",
    "title": "Junior Python Developer",
    "company": "Sample Tech",
    "required_skills": ["Python", "Django", "SQL"],
    "location": "Central",
    "work_arrangement": "Hybrid",
    "working_hours": "Standard",
    "industry": "Technology / IT",
}


def test_job_suggestion_round_trips_through_a_saved_record():
    assert JobSuggestion.from_dict(SAVED_JOB).to_dict() == SAVED_JOB


def test_job_suggestion_score_is_always_0_to_100():
    def score(value):
        return JobSuggestion("Developer", "url", match_score=value).match_score

    assert score(85.6) == 86
    assert score(150) == 100
    assert score(-5) == 0
    assert score("high") == 0
    assert score(None) == 0
    assert score(float("inf")) == 0


def test_old_job_record_loads_with_defaults():
    job = JobSuggestion.from_dict({"title": " Data Analyst "})
    assert job.title == "Data Analyst"
    assert job.match_score == 0 and job.matched_skills == [] and job.url == ""


def test_job_suggestion_skills_cannot_be_changed_from_outside():
    job = JobSuggestion.from_dict(SAVED_JOB)
    job.matched_skills.append("Java")
    assert job.matched_skills == ["Python", "Django"]


def test_job_posting_round_trips_through_a_saved_record():
    assert JobPosting.from_dict(SAVED_POSTING).to_dict() == SAVED_POSTING


def test_job_posting_drops_blank_required_skills():
    posting = JobPosting("job.pdf", required_skills=["Python", "", "  ", "SQL"])
    assert posting.required_skills == ["Python", "SQL"]
