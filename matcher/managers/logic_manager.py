"""
Logic Manager - ranks and filters jobs, and scores and ranks candidates.

It never calls the AI or reads files.

    SkillsComponent, MatchFlagComponent  the weighted parts of a candidate's
                                         score (ScoreComponent subclasses)
    StrongMatchRule                      decides the Strong Match label
    CandidateScorer                      scores a candidate with a ScoringProfile
                                         (owns its components)
    CandidateRanker                      puts scored candidates in order
    JobRanker, JobFilter                 rank and filter suggested jobs
"""

from functools import partial

from ..contracts.scoring import ScoreComponent
from ..domain.candidate import Candidate, MatchResult
from ..domain.scoring_profile import ScoringProfile


# ---------- Employer: the parts of a candidate's score ----------

class SkillsComponent(ScoreComponent):
    """Points for the share of the job's skills the candidate has."""

    name = "skills"

    def fraction(self, candidate):
        return candidate.skills_ratio


class MatchFlagComponent(ScoreComponent):
    """Full points if one of the AI's true/false checks is true, none if false.

    e.g. MatchFlagComponent("experience_match", 25)
    """

    def __init__(self, field, weight):
        if field not in Candidate.MATCH_FIELDS:
            raise ValueError(f"{field!r} is not one of {Candidate.MATCH_FIELDS}")
        super().__init__(weight)
        self._field = field

    @property
    def name(self):
        """e.g. "experience" for experience_match."""
        return self._field.removesuffix("_match")

    def fraction(self, candidate):
        return 1.0 if getattr(candidate, self._field) else 0.0


class StrongMatchRule:
    """Strong Match = skills >= 70% AND experience match AND location match.

    Uses three fields of the AI's reply, so one good field alone is not enough.
    """

    def __init__(self, min_skills_ratio=0.7):
        if not 0 <= min_skills_ratio <= 1:
            raise ValueError(f"min_skills_ratio must be from 0 to 1, not {min_skills_ratio!r}")
        self._min_skills_ratio = min_skills_ratio

    @property
    def min_skills_ratio(self):
        return self._min_skills_ratio

    def is_met(self, candidate):
        return (
            candidate.skills_ratio >= self._min_skills_ratio
            and candidate.experience_match
            and candidate.location_match
        )


class CandidateScorer:
    """Scores candidates out of 100 and labels Strong Matches, using a ScoringProfile.

    The scorer creates its own score components and Strong Match rule from
    the profile and owns them (composition): they exist only inside this
    scorer. Every component is used the same way - points(candidate) - so
    the scorer never checks which kind it has.

    A new part of the score is a new ScoreComponent added to
    COMPONENT_TYPES (or passed in as component_types), with no change to
    this class (open/closed principle).
    """

    # Which ScoreComponent each weight in a profile becomes. Each entry
    # makes a component from its weight, e.g. SkillsComponent(40).
    COMPONENT_TYPES = {
        "skills": SkillsComponent,
        "experience": partial(MatchFlagComponent, "experience_match"),
        "education": partial(MatchFlagComponent, "education_match"),
        "location": partial(MatchFlagComponent, "location_match"),
        "work_arrangement": partial(MatchFlagComponent, "work_arrangement_match"),
        "working_hours": partial(MatchFlagComponent, "working_hours_match"),
    }

    def __init__(self, profile=None, component_types=None):
        """profile: a ScoringProfile (default "Balanced") that weights every component type."""
        self._profile = ScoringProfile.default() if profile is None else profile
        self._component_types = dict(self.COMPONENT_TYPES if component_types is None else component_types)
        if set(self._profile.weights) != set(self._component_types):
            raise ValueError(f"The profile must weight exactly {sorted(self._component_types)}")

        self._components = [
            self._component_types[part](weight) for part, weight in self._profile.weights.items()
        ]
        self._strong_match_rule = StrongMatchRule(self._profile.strong_match_ratio)

    def with_profile(self, profile):
        """A new scorer with the same component types, scoring with another profile."""
        return type(self)(profile, self._component_types)

    @property
    def profile(self):
        return self._profile

    @property
    def weights(self):
        """e.g. {"skills": 40, "experience": 25, ...}"""
        return {component.name: component.weight for component in self._components}

    def score(self, candidate):
        """Return a MatchResult: the candidate with its score and Strong Match label."""
        if candidate.unreadable:
            return MatchResult(candidate, 0, False)
        total = round(sum(component.points(candidate) for component in self._components))
        return MatchResult(candidate, total, self._strong_match_rule.is_met(candidate))


class CandidateRanker:
    """Puts scored candidates in order: best score first, unreadable resumes last."""

    def rank(self, results):
        """results: MatchResults. Returns a new list, best first."""
        return sorted(
            results,
            key=lambda result: (not result.candidate.unreadable, result.score),
            reverse=True,
        )


# ---------- Job seeker: rank and filter jobs ----------

class JobRanker:
    """Puts suggested jobs (JobSuggestions) in order, best match first."""

    def rank(self, jobs):
        """Best match_score first; jobs with equal scores keep their order."""
        return sorted(jobs, key=lambda job: job.match_score, reverse=True)

    def select_top(self, jobs, max_jobs):
        """Keep the best max_jobs jobs, one per link, best match first.

        Jobs with the same url (e.g. the same title in different letter case)
        count once - the first one is kept.
        """
        unique_jobs, seen_urls = [], set()
        for job in jobs:
            if job.url not in seen_urls:
                seen_urls.add(job.url)
                unique_jobs.append(job)
        return self.rank(unique_jobs)[:max_jobs]


class JobFilter:
    """The filters picked on the job results page.

    Works on saved jobs, so changing filters never needs another AI call.
    An empty filter (nothing ticked, or "" for industry) means "show all".
    """

    def __init__(self, work_arrangements=(), locations=(), working_hours=(), industry=""):
        self._work_arrangements = set(work_arrangements)
        self._locations = set(locations)
        self._working_hours = set(working_hours)
        self._industry = industry

    def matches(self, job):
        """True if a JobSuggestion passes every filter that is set."""
        return (
            (not self._work_arrangements or job.work_arrangement in self._work_arrangements)
            and (not self._locations or job.location in self._locations)
            and (not self._working_hours or job.working_hours in self._working_hours)
            and (not self._industry or job.industry == self._industry)
        )

    def apply(self, jobs):
        """The jobs that pass every filter, in the same order."""
        return [job for job in jobs if self.matches(job)]
