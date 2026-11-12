"""
Tests for the Logic Manager's classes: score components, the Strong Match
rule, and ranking and filtering. They use domain objects only - no AI, no files.
"""

from ..contracts.scoring import ScoreComponent
from ..domain.candidate import Candidate, MatchResult
from ..domain.job import JobSuggestion
from ..domain.scoring_profile import ScoringProfile
from ..managers.logic_manager import (
    CandidateRanker,
    CandidateScorer,
    JobFilter,
    JobRanker,
    MatchFlagComponent,
    SkillsComponent,
    StrongMatchRule,
)
from .test_app import raises


def make_candidate(matched=3, missing=0, **matches):
    return Candidate("c.pdf", matched_skills=[f"s{i}" for i in range(matched)],
                     missing_skills=[f"m{i}" for i in range(missing)], **matches)


# ---------- Score components ----------

def test_skills_component_gives_points_for_the_share_of_skills():
    component = SkillsComponent(40)
    assert component.points(make_candidate(matched=1, missing=1)) == 20
    assert component.points(make_candidate(matched=3, missing=0)) == 40
    assert component.points(make_candidate(matched=0, missing=0)) == 0


def test_match_flag_component_is_all_or_nothing():
    component = MatchFlagComponent("experience_match", 25)
    assert component.name == "experience"
    assert component.points(make_candidate(experience_match=True)) == 25
    assert component.points(make_candidate(experience_match=False)) == 0


def test_match_flag_component_rejects_unknown_fields():
    assert raises(ValueError, MatchFlagComponent, "salary_match", 10)


def test_every_component_is_a_score_component():
    """The scorer can add up any of them the same way."""
    components = [SkillsComponent(40), MatchFlagComponent("location_match", 10)]
    candidate = make_candidate(matched=1, missing=1, location_match=True)
    assert all(isinstance(c, ScoreComponent) for c in components)
    assert sum(c.points(candidate) for c in components) == 30


# ---------- Strong Match ----------

def test_strong_match_needs_skills_experience_and_location():
    rule = StrongMatchRule()
    assert rule.is_met(make_candidate(7, 3, experience_match=True, location_match=True))
    assert not rule.is_met(make_candidate(6, 4, experience_match=True, location_match=True))
    assert not rule.is_met(make_candidate(3, 0, experience_match=False, location_match=True))
    assert not rule.is_met(make_candidate(3, 0, experience_match=True, location_match=False))


def test_strong_match_threshold_can_be_changed():
    candidate = make_candidate(5, 5, experience_match=True, location_match=True)
    assert not StrongMatchRule().is_met(candidate)
    assert StrongMatchRule(min_skills_ratio=0.5).is_met(candidate)
    assert raises(ValueError, StrongMatchRule, 1.5)


# ---------- CandidateScorer ----------

FULL_MATCH = dict(experience_match=True, education_match=True, location_match=True,
                  work_arrangement_match=True, working_hours_match=True)


def test_full_match_scores_100_and_is_strong():
    result = CandidateScorer().score(make_candidate(**FULL_MATCH))
    assert isinstance(result, MatchResult)
    assert (result.score, result.strong_match) == (100, True)


def test_default_profile_is_balanced():
    # Half the skills (20) + experience (25) + location (10)
    candidate = make_candidate(matched=1, missing=1, experience_match=True, location_match=True)
    assert CandidateScorer().score(candidate).score == 55
    assert CandidateScorer().weights == ScoringProfile.DEFAULT_WEIGHTS
    assert CandidateScorer().profile.name == "Balanced"


def test_unreadable_resume_scores_0():
    result = CandidateScorer().score(Candidate.unreadable_resume("broken.pdf"))
    assert (result.score, result.strong_match) == (0, False)


def profile(strong_match_skills=70, **weights):
    return ScoringProfile("Custom", dict(ScoringProfile.DEFAULT_WEIGHTS, **weights), strong_match_skills)


def test_custom_weights_change_the_score():
    candidate = make_candidate(matched=0, missing=3, experience_match=True)
    assert CandidateScorer().score(candidate).score == 25
    assert CandidateScorer(profile(skills=20, experience=45)).score(candidate).score == 45


def test_custom_weights_change_the_ranking():
    """A skilled newcomer against an experienced candidate with fewer skills."""
    skilled = make_candidate(matched=3, missing=0)
    experienced = make_candidate(matched=1, missing=2, experience_match=True)
    by_skills = CandidateScorer(profile(skills=60, experience=5))
    by_experience = CandidateScorer(profile(skills=20, experience=45))

    def ranking(scorer):
        results = [scorer.score(skilled), scorer.score(experienced)]
        return [result.candidate for result in CandidateRanker().rank(results)]

    assert ranking(by_skills) == [skilled, experienced]
    assert ranking(by_experience) == [experienced, skilled]


def test_profile_must_weight_every_component():
    no_salary = ScoringProfile("No salary", dict(ScoringProfile.DEFAULT_WEIGHTS, skills=30, salary=10))
    skills_only = ScoringProfile("Skills only", {"skills": 100})
    assert raises(ValueError, CandidateScorer, no_salary)
    assert raises(ValueError, CandidateScorer, skills_only)


def test_profile_sets_the_strong_match_threshold():
    candidate = make_candidate(5, 5, experience_match=True, location_match=True)
    assert not CandidateScorer().score(candidate).strong_match
    assert CandidateScorer(profile(strong_match_skills=50)).score(candidate).strong_match


def test_scorer_with_another_profile_is_a_new_scorer():
    scorer = CandidateScorer()
    other = scorer.with_profile(profile(skills=20, experience=45))
    assert other is not scorer and other.weights["skills"] == 20
    assert scorer.weights["skills"] == 40


def test_scorer_keeps_its_components_to_itself():
    scorer = CandidateScorer()
    scorer.weights["skills"] = 0
    assert scorer.weights["skills"] == 40


class SummaryComponent(ScoreComponent):
    """A new part of the score, written outside the Logic Manager: full
    points if the AI wrote a summary of the candidate."""

    name = "summary"

    def fraction(self, candidate):
        return 1.0 if candidate.summary else 0.0


def test_a_new_score_component_needs_no_change_to_the_scorer():
    """Open/closed: CandidateScorer is extended with a new component type, not edited."""
    component_types = {**CandidateScorer.COMPONENT_TYPES, "summary": SummaryComponent}
    with_summary = ScoringProfile("With summary", dict(ScoringProfile.DEFAULT_WEIGHTS, skills=30, summary=10))
    scorer = CandidateScorer(with_summary, component_types)

    assert scorer.weights["summary"] == 10
    assert scorer.score(make_candidate(matched=0, missing=3, summary="Good fit.")).score == 10
    assert scorer.score(make_candidate(matched=0, missing=3)).score == 0
    # with_profile() keeps the new component type
    assert scorer.with_profile(with_summary).weights == scorer.weights


# ---------- CandidateRanker ----------

def test_rank_candidates_best_first_and_unreadable_last():
    scorer = CandidateScorer()
    low = scorer.score(make_candidate(matched=0, missing=3))
    high = scorer.score(make_candidate(**FULL_MATCH))
    unreadable = scorer.score(Candidate.unreadable_resume("broken.pdf"))
    assert CandidateRanker().rank([unreadable, low, high]) == [high, low, unreadable]


# ---------- JobRanker ----------

def job(title, score=0, url=None, **fields):
    return JobSuggestion(title, url or f"/{title.lower()}", match_score=score, **fields)


def titles(jobs):
    return [j.title for j in jobs]


def test_rank_jobs_best_match_first():
    assert titles(JobRanker().rank([job("B", 50), job("A", 90), job("C", 50)])) == ["A", "B", "C"]


def test_select_top_jobs_removes_duplicate_links_sorts_and_caps():
    jobs = [job("A", 50, "/a"), job("a", 99, "/a"), job("B", 80), job("C", 70)]
    assert titles(JobRanker().select_top(jobs, 2)) == ["B", "C"]
    assert titles(JobRanker().select_top(jobs, 10)) == ["B", "C", "A"]


# ---------- JobFilter ----------

JOBS = [
    job("A", location="West", work_arrangement="On-site", working_hours="Standard", industry="Manufacturing"),
    job("B", location="Central", work_arrangement="Hybrid", working_hours="Standard", industry="Technology / IT"),
]


def test_no_filters_keeps_every_job():
    assert titles(JobFilter().apply(JOBS)) == ["A", "B"]


def test_filters_combine():
    assert titles(JobFilter(locations=["West"]).apply(JOBS)) == ["A"]
    assert titles(JobFilter(["Hybrid"], [], ["Standard"], "Technology / IT").apply(JOBS)) == ["B"]
    assert titles(JobFilter(locations=["West"], industry="Technology / IT").apply(JOBS)) == []


def test_filter_allows_any_of_several_ticked_values():
    assert titles(JobFilter(locations=["West", "Central"]).apply(JOBS)) == ["A", "B"]
