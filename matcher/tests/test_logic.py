"""
Tests for the Logic Manager's classes: score components, the Strong Match
rule, and ranking and filtering. They use domain objects only - no AI, no files.
"""

from ..contracts.scoring import ScoreComponent
from ..domain.candidate import Candidate
from ..managers.logic_manager import MatchFlagComponent, SkillsComponent, StrongMatchRule
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
