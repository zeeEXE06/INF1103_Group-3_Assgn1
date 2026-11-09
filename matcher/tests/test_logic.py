"""
Tests for the Logic Manager's classes: score components, the Strong Match
rule, and ranking and filtering. They use domain objects only - no AI, no files.
"""

from ..contracts.scoring import ScoreComponent
from ..domain.candidate import Candidate, MatchResult
from ..managers.logic_manager import (
    CandidateRanker,
    CandidateScorer,
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


def test_default_weights():
    # Half the skills (20) + experience (25) + location (10)
    candidate = make_candidate(matched=1, missing=1, experience_match=True, location_match=True)
    assert CandidateScorer().score(candidate).score == 55
    assert CandidateScorer().weights == CandidateScorer.DEFAULT_WEIGHTS


def test_unreadable_resume_scores_0():
    result = CandidateScorer().score(Candidate.unreadable_resume("broken.pdf"))
    assert (result.score, result.strong_match) == (0, False)


def test_custom_weights_change_the_score():
    weights = dict(CandidateScorer.DEFAULT_WEIGHTS, skills=20, experience=45)
    candidate = make_candidate(matched=0, missing=3, experience_match=True)
    assert CandidateScorer().score(candidate).score == 25
    assert CandidateScorer(weights).score(candidate).score == 45


def test_weights_must_cover_every_part_and_add_up_to_100():
    assert raises(ValueError, CandidateScorer, dict(CandidateScorer.DEFAULT_WEIGHTS, skills=50))
    assert raises(ValueError, CandidateScorer, {"skills": 100})
    assert raises(ValueError, CandidateScorer, dict(CandidateScorer.DEFAULT_WEIGHTS, salary=0))


def test_scorer_uses_the_strong_match_rule_it_is_given():
    candidate = make_candidate(5, 5, experience_match=True, location_match=True)
    assert not CandidateScorer().score(candidate).strong_match
    assert CandidateScorer(strong_match_rule=StrongMatchRule(0.5)).score(candidate).strong_match


def test_scorer_keeps_its_components_to_itself():
    scorer = CandidateScorer()
    scorer.weights["skills"] = 0
    assert scorer.weights["skills"] == 40


# ---------- CandidateRanker ----------

def test_rank_candidates_best_first_and_unreadable_last():
    scorer = CandidateScorer()
    low = scorer.score(make_candidate(matched=0, missing=3))
    high = scorer.score(make_candidate(**FULL_MATCH))
    unreadable = scorer.score(Candidate.unreadable_resume("broken.pdf"))
    assert CandidateRanker().rank([unreadable, low, high]) == [high, low, unreadable]
