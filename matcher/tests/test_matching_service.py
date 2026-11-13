"""
Tests for MatchingService. The service is given a FakeProvider and an
InMemoryRepository instead of Gemini and the JSON files, which it accepts
because it only depends on what it is given (association).
"""

import json

from django.conf import settings
from django.test import override_settings

from ..domain.scoring_profile import ScoringProfile
from ..domain.shortlist import Shortlist
from ..managers.ai_manager import AIManager
from ..managers.logic_manager import CandidateRanker, CandidateScorer, JobRanker
from ..services.matching_service import MatchingError, MatchingService
from .fakes import FakeProvider, InMemoryRepository
from .test_app import JOBS_REPLY, RESUME_REPLY, comparison_reply, make_pdf_file, raises


def service(*replies, scorer=None):
    """A MatchingService using fake parts. Returns (service, provider, repository)."""
    provider, repository = FakeProvider(*replies), InMemoryRepository()
    matching = MatchingService(AIManager(provider), repository, scorer or CandidateScorer(),
                               CandidateRanker(), JobRanker())
    return matching, provider, repository


# ---------- Job seeker ----------

def test_read_resume_saves_what_the_ai_found():
    matching, _, repository = service(RESUME_REPLY)
    resume = matching.read_resume(make_pdf_file("cv.pdf"))
    assert (resume.id, resume.filename) == ("R001", "cv.pdf")
    assert resume.skill_names == ["Python", "Django"]
    assert repository.load("resumes") == [resume.to_dict()]


def test_same_resume_is_not_sent_to_the_ai_twice():
    matching, provider, _ = service(RESUME_REPLY)
    first = matching.read_resume(make_pdf_file("cv.pdf"))
    second = matching.read_resume(make_pdf_file("cv.pdf"))
    assert provider.call_count == 1 and second.id == first.id


def test_unreadable_resume_raises_and_saves_nothing():
    matching, _, repository = service()  # no replies: the AI fails
    assert raises(MatchingError, matching.read_resume, make_pdf_file())
    assert repository.load("resumes") == []


@override_settings(MAX_JOBS=2)
def test_suggested_jobs_are_ranked_capped_and_linked():
    matching, _, _ = service(RESUME_REPLY, JOBS_REPLY)
    resume = matching.read_resume(make_pdf_file())
    record = matching.match_jobs_to_resume(resume.id)
    assert record["resume_id"] == resume.id
    assert [job["title"] for job in record["jobs"]] == ["Software Developer", "Backend Engineer"]
    assert record["jobs"][0]["url"] == "https://sg.jobstreet.com/software-developer-jobs"

    jobs = matching.suggested_jobs(record["id"])
    assert [job.title for job in jobs] == ["Software Developer", "Backend Engineer"]
    assert matching.suggested_jobs("J999") == []


def test_job_search_without_a_resume_raises():
    matching, provider, _ = service()
    assert raises(MatchingError, matching.match_jobs_to_resume)
    assert provider.call_count == 0


def test_job_filter_uses_the_picked_filters():
    matching, _, _ = service(RESUME_REPLY, JOBS_REPLY)
    record = matching.match_jobs_to_resume(matching.read_resume(make_pdf_file()).id)
    filters = {"work_arrangement": [], "locations": ["East"], "working_hours": [], "industry": ""}
    shown = matching.job_filter(filters).apply(matching.suggested_jobs(record["id"]))
    assert [job.title for job in shown] == ["Backend Engineer"]


# ---------- Employer ----------

def test_candidates_are_scored_and_saved_as_a_shortlist():
    matching, _, repository = service(comparison_reply(2))
    shortlist = matching.match_candidates_to_job(make_pdf_file("job.pdf"),
                                                 [make_pdf_file("a.pdf"), make_pdf_file("b.pdf")])
    assert isinstance(shortlist, Shortlist) and shortlist.id == "C001"
    assert shortlist.job.title == "Junior Python Developer"
    assert [r.candidate.filename for r in shortlist.results] == ["a.pdf", "b.pdf"]
    assert shortlist.results[0].strong_match and not shortlist.results[1].strong_match
    assert repository.load("candidate_matches") == [shortlist.to_dict()]


def test_resume_the_ai_skipped_is_marked_unreadable_and_ranked_last():
    reply = json.dumps({"job": {"title": "Dev"}, "candidates": [
        {"resume_number": 2, "name": "Bo", "matched_skills": ["Python"], "missing_skills": []},
    ]})
    matching, _, _ = service(reply)
    shortlist = matching.match_candidates_to_job(make_pdf_file("job.pdf"),
                                                 [make_pdf_file("skipped.pdf"), make_pdf_file("bo.pdf")])
    ranked = matching.ranked_candidates(shortlist)
    assert [r.candidate.filename for r in ranked] == ["bo.pdf", "skipped.pdf"]
    assert ranked[-1].candidate.unreadable and ranked[-1].score == 0


def test_only_a_real_true_from_the_ai_counts_as_a_match():
    reply = json.dumps({"job": {}, "candidates": [
        {"resume_number": 1, "experience_match": "true", "location_match": 1, "education_match": True},
    ]})
    matching, _, _ = service(reply)
    candidate = matching.match_candidates_to_job(make_pdf_file("job.pdf"), [make_pdf_file("a.pdf")]).results[0].candidate
    assert (candidate.experience_match, candidate.location_match, candidate.education_match) == (False, False, True)


def test_the_service_uses_the_scorer_it_is_given():
    """Resume 2 is a partial match: 2 of 3 skills, no experience match."""
    weights = dict(ScoringProfile.DEFAULT_WEIGHTS, skills=10, experience=55)
    files = lambda: (make_pdf_file("job.pdf"), [make_pdf_file("a.pdf"), make_pdf_file("b.pdf")])
    default, _, _ = service(comparison_reply(2))
    custom, _, _ = service(comparison_reply(2), scorer=CandidateScorer(ScoringProfile("Custom", weights)))
    assert default.match_candidates_to_job(*files()).results[1].score == 57  # 26.7 skills + 30
    assert custom.match_candidates_to_job(*files()).results[1].score == 37   # 6.7 skills + 30


def test_same_employer_files_reuse_the_saved_shortlist():
    matching, provider, _ = service(comparison_reply(1))
    files = (make_pdf_file("job.pdf"), [make_pdf_file("a.pdf")])
    first = matching.match_candidates_to_job(*files)
    second = matching.match_candidates_to_job(*files)
    assert provider.call_count == 1 and second.to_dict() == first.to_dict()
    assert matching.find_shortlist(first.id).to_dict() == first.to_dict()
    assert matching.find_shortlist("C999") is None


def test_shortlist_is_scored_with_the_chosen_profile():
    experience_first = ScoringProfile.built_in()[2]
    matching, _, _ = service(comparison_reply(2))
    shortlist = matching.match_candidates_to_job(make_pdf_file("job.pdf"),
                                                 [make_pdf_file("a.pdf"), make_pdf_file("b.pdf")],
                                                 experience_first)
    assert shortlist.profile.to_dict() == experience_first.to_dict()
    assert shortlist.results[1].score == 45  # 20 skills + 10 education + 10 location + 5 work arrangement


def test_same_files_with_another_profile_are_scored_again_without_the_ai():
    matching, provider, repository = service(comparison_reply(2))
    files = lambda: (make_pdf_file("job.pdf"), [make_pdf_file("a.pdf"), make_pdf_file("b.pdf")])
    balanced = matching.match_candidates_to_job(*files())
    experience_first = matching.match_candidates_to_job(*files(), ScoringProfile.built_in()[2])
    balanced_again = matching.match_candidates_to_job(*files())

    assert provider.call_count == 1
    assert [r.score for r in balanced.results] == [100, 57]
    assert [r.score for r in experience_first.results] == [100, 45]
    assert experience_first.job.title == balanced.job.title
    assert balanced_again.id == balanced.id  # reused, not saved again
    assert len(repository.load("candidate_matches")) == 2


def test_scoring_profiles_are_the_built_in_ones_then_the_saved_ones():
    matching, _, repository = service()
    mine = ScoringProfile("Location matters", dict(ScoringProfile.DEFAULT_WEIGHTS, skills=20, location=30))
    saved = matching.save_profile(mine)
    repository.save("scoring_profiles", {"name": "Broken", "weights": {"skills": 5}})

    assert saved.id == "S001" and saved.name == "Location matters"
    assert [p.name for p in matching.scoring_profiles()] == [
        "Balanced", "Skills first", "Experience first", "Location matters"]
    assert matching.find_profile("S001").weights == mine.weights
    assert matching.find_profile("balanced").name == "Balanced"
    assert matching.find_profile("S999") is None and matching.find_profile(None) is None


def test_the_same_profile_is_not_saved_twice():
    matching, _, repository = service()
    mine = ScoringProfile("Mine", dict(ScoringProfile.DEFAULT_WEIGHTS, skills=30, experience=35))
    assert matching.save_profile(mine).id == matching.save_profile(mine).id == "S001"
    assert len(repository.load("scoring_profiles")) == 1


def test_a_profile_the_scorer_cannot_use_is_not_saved():
    matching, _, repository = service()
    unknown_part = ScoringProfile("Salary", dict(ScoringProfile.DEFAULT_WEIGHTS, skills=30, salary=10))
    assert raises(MatchingError, matching.save_profile, unknown_part)
    assert repository.load("scoring_profiles") == []


# ---------- Broken saved records ----------

BALANCED = ScoringProfile.default().to_dict()


def test_broken_saved_shortlist_is_treated_as_missing():
    matching, _, repository = service()
    repository.save("candidate_matches", {"job": "oops", "candidates": [{"match_score": 500}]})
    repository.save("candidate_matches", {"job": {}, "profile": {"name": "Bad", "weights": {"skills": 3}},
                                          "candidates": []})
    assert matching.find_shortlist("C001") is None
    assert matching.find_shortlist("C002") is None


def test_broken_saved_jobs_are_treated_as_missing():
    matching, _, repository = service()
    repository.save("job_matches", {"jobs": "oops"})
    repository.save("job_matches", {"jobs": [5]})
    repository.save("job_matches", {})
    assert [matching.suggested_jobs(job_id) for job_id in ("J001", "J002", "J003")] == [[], [], []]


def test_broken_saved_comparison_is_compared_again_by_the_ai():
    matching, provider, repository = service(comparison_reply(1))
    files = (make_pdf_file("job.pdf"), [make_pdf_file("a.pdf")])
    file_hashes = [MatchingService._file_hash(f) for f in (files[0], *files[1])]
    repository.save("candidate_matches", {"file_hashes": file_hashes, "profile": BALANCED,
                                          "job": {}, "candidates": [{"match_score": 500}]})

    shortlist = matching.match_candidates_to_job(*files)
    assert provider.call_count == 1 and shortlist.id == "C002"
    assert shortlist.results[0].candidate.name == "Candidate 1"


def test_broken_saved_resume_is_read_again_by_the_ai():
    matching, provider, repository = service(RESUME_REPLY)
    resume_file = make_pdf_file()
    repository.save("resumes", {"file_hash": MatchingService._file_hash(resume_file), "skills": 5})
    assert matching.read_resume(resume_file).id == "R002" and provider.call_count == 1


def test_job_search_for_a_broken_saved_resume_raises():
    matching, provider, repository = service(JOBS_REPLY)
    repository.save("resumes", {"skills": "oops", "education": 5})
    assert raises(MatchingError, matching.match_jobs_to_resume, "R001")
    assert provider.call_count == 0


def test_broken_saved_profiles_are_skipped():
    matching, _, repository = service()
    repository.save("scoring_profiles", {"name": 3})
    repository.save("scoring_profiles", {"name": "Bad", "weights": "oops"})
    assert [p.name for p in matching.scoring_profiles()] == ["Balanced", "Skills first", "Experience first"]


def test_ai_failure_when_comparing_raises():
    matching, _, repository = service()
    assert raises(MatchingError, matching.match_candidates_to_job, make_pdf_file("job.pdf"), [make_pdf_file("a.pdf")])
    assert repository.load("candidate_matches") == []


def test_in_memory_service_never_touches_the_data_folder():
    matching, _, _ = service(RESUME_REPLY)
    matching.read_resume(make_pdf_file())
    assert not list(settings.DATA_DIR.glob("*.json"))
