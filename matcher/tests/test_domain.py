"""
Tests for the domain classes in matcher/domain: each one keeps its data
safe from outside changes and converts to and from saved records.
"""

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
