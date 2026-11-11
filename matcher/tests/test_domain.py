"""
Tests for the domain classes in matcher/domain: each one keeps its data
safe from outside changes and converts to and from saved records.
"""

from ..domain.candidate import Candidate, MatchResult
from ..domain.job import JobPosting, JobSuggestion
from ..domain.resume import Resume
from ..domain.shortlist import Shortlist
from .test_app import raises


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


# ---------- Candidate and MatchResult ----------

SAVED_CANDIDATE = {
    "filename": "alice.pdf",
    "name": "Alice Tan",
    "matched_skills": ["Python", "Django"],
    "missing_skills": ["SQL"],
    "experience": ["Developer, 2 years"],
    "education": ["B.Sc. Computer Science"],
    "location": "Central",
    "work_arrangement": "Hybrid",
    "working_hours": "Standard",
    "summary": "Good fit.",
    "unreadable": False,
    "experience_match": True,
    "education_match": True,
    "location_match": True,
    "work_arrangement_match": False,
    "working_hours_match": True,
    "match_score": 82,
    "strong_match": False,
}


def test_match_result_round_trips_through_a_saved_record():
    assert MatchResult.from_dict(SAVED_CANDIDATE).to_dict() == SAVED_CANDIDATE


def test_candidate_skills_ratio():
    assert Candidate.from_dict(SAVED_CANDIDATE).skills_ratio == 2 / 3
    assert Candidate("a.pdf").skills_ratio == 0.0


def test_candidate_without_a_name_uses_the_filename():
    assert Candidate("bob.pdf", name="  ").name == "bob.pdf"


def test_unreadable_resume_placeholder():
    candidate = Candidate.unreadable_resume("broken.pdf")
    assert candidate.unreadable and candidate.name == "broken.pdf"
    assert not any(getattr(candidate, field) for field in Candidate.MATCH_FIELDS)
    assert candidate.summary == "Could not read this resume."


def test_candidate_cannot_be_changed_from_outside():
    candidate = Candidate.from_dict(SAVED_CANDIDATE)
    candidate.matched_skills.append("Java")
    assert raises(AttributeError, setattr, candidate, "location_match", False)
    assert candidate.matched_skills == ["Python", "Django"] and candidate.location_match


def test_match_result_shares_its_candidate():
    candidate = Candidate.from_dict(SAVED_CANDIDATE)
    first, second = MatchResult(candidate, 82, False), MatchResult(candidate, 60, False)
    assert first.candidate is second.candidate is candidate


def test_match_result_rejects_bad_scores():
    candidate = Candidate("a.pdf")
    for score in (-1, 101, 50.5, "80", True):
        assert raises(ValueError, MatchResult, candidate, score, False)
    assert MatchResult(candidate, 0, False).score == 0


# ---------- Shortlist ----------

SAVED_SHORTLIST = {
    "id": "C001",
    "file_hashes": ["job-hash", "alice-hash"],
    "created_at": "2026-11-11T10:00:00+00:00",
    "job": SAVED_POSTING,
    "candidates": [SAVED_CANDIDATE],
}


class ByScore:
    """A minimal ranker: highest score first."""

    def rank(self, results):
        return sorted(results, key=lambda result: result.score, reverse=True)


def test_shortlist_round_trips_through_a_saved_record():
    assert Shortlist.from_dict(SAVED_SHORTLIST).to_dict() == SAVED_SHORTLIST


def test_shortlist_holds_results_it_did_not_create():
    """Aggregation: the same MatchResult can be in two shortlists and outlive them."""
    result = MatchResult.from_dict(SAVED_CANDIDATE)
    job = JobPosting.from_dict(SAVED_POSTING)
    first, second = Shortlist(job, [result]), Shortlist(job)
    second.add(result)
    del first
    assert second.results[0] is result and len(second) == 1


def test_shortlist_ranks_with_the_ranker_it_is_given():
    low = MatchResult(Candidate("low.pdf"), 20, False)
    high = MatchResult(Candidate("high.pdf"), 90, True)
    shortlist = Shortlist(JobPosting("job.pdf"), [low, high])
    assert shortlist.ranked(ByScore()) == [high, low]
    assert shortlist.results == [low, high]  # ranking doesn't reorder the shortlist


def test_shortlist_strong_matches():
    strong = MatchResult(Candidate("a.pdf"), 90, True)
    shortlist = Shortlist(JobPosting("job.pdf"), [strong, MatchResult(Candidate("b.pdf"), 50, False)])
    assert shortlist.strong_matches == [strong]


def test_unsaved_shortlist_has_no_id_and_cannot_be_changed_from_outside():
    shortlist = Shortlist(JobPosting("job.pdf"))
    shortlist.results.append(MatchResult(Candidate("a.pdf"), 10, False))
    assert shortlist.id is None and "id" not in shortlist.to_dict() and len(shortlist) == 0

