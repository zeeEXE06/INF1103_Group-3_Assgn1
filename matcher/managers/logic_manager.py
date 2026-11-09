"""
Logic Manager - ranks and filters jobs, and scores and ranks candidates.

It never calls the AI or reads files.

    SkillsComponent, MatchFlagComponent  the weighted parts of a candidate's
                                         score (ScoreComponent subclasses)
    StrongMatchRule                      decides the Strong Match label
"""

from ..contracts.scoring import ScoreComponent
from ..domain.candidate import Candidate


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


# ---------- Job seeker: rank and filter jobs ----------

# Fields every job on the results page has, with defaults for older saved
# records that are missing some of them
JOB_DEFAULTS = {
    "title": "",
    "url": "",
    "match_score": 0,
    "location": "",
    "work_arrangement": "",
    "working_hours": "",
    "industry": "",
    "matched_skills": [],
    "match_reason": "",
}


def to_score(value):
    """Turn a match score into a whole number from 0 to 100 (0 if it isn't a number)."""
    try:
        return max(0, min(100, round(float(value))))
    except (TypeError, ValueError):
        return 0


def select_top_jobs(jobs, max_jobs):
    """Keep the best max_jobs jobs, one per link, best match first.

    Jobs with the same url (e.g. the same title in different letter case)
    count once - the first one is kept.
    """
    unique_jobs = []
    seen_urls = set()
    for job in jobs:
        if job["url"] not in seen_urls:
            seen_urls.add(job["url"])
            unique_jobs.append(job)
    ranked = sorted(unique_jobs, key=lambda job: job["match_score"], reverse=True)
    return ranked[:max_jobs]


def rank_jobs(jobs):
    """Sort saved jobs best match first and number them 1, 2, 3...

    jobs: the "jobs" list of a job_matches.json record.
    Returns new dicts with every JOB_DEFAULTS field plus "rank".
    """
    ranked = sorted(jobs, key=lambda job: job.get("match_score", 0), reverse=True)
    return [
        {**JOB_DEFAULTS, **job, "rank": rank}
        for rank, job in enumerate(ranked, start=1)
    ]


def filter_jobs(jobs, work_arrangements, locations, working_hours, industry):
    """Keep only the jobs that match the chosen filters.

    Works on saved jobs, so changing filters never needs another AI call.
    An empty filter (nothing ticked, or "" for industry) means "show all".
    """
    filtered_jobs = []
    for job in jobs:
        if work_arrangements and job.get("work_arrangement") not in work_arrangements:
            continue
        if locations and job.get("location") not in locations:
            continue
        if working_hours and job.get("working_hours") not in working_hours:
            continue
        if industry and job.get("industry") != industry:
            continue
        filtered_jobs.append(job)
    return filtered_jobs


# ---------- Employer: score and rank candidates ----------

# How much each part counts towards a candidate's score (adds up to 100)
SCORE_WEIGHTS = {
    "skills": 40,
    "experience": 25,
    "education": 10,
    "location": 10,
    "work_arrangement": 10,
    "working_hours": 5,
}

# Strong Match needs at least this share of the job's skills
STRONG_MATCH_SKILLS_RATIO = 0.7


def skills_ratio(candidate):
    """Share of the job's skills the candidate has, from 0.0 to 1.0."""
    matched = len(candidate.get("matched_skills", []))
    missing = len(candidate.get("missing_skills", []))
    if matched + missing == 0:
        return 0.0
    return matched / (matched + missing)


def calculate_score(candidate):
    """Weighted match score from 0 to 100.

    candidate: dict with matched_skills, missing_skills and the AI's
    true/false checks (experience_match, education_match, location_match,
    work_arrangement_match, working_hours_match).
    """
    score = SCORE_WEIGHTS["skills"] * skills_ratio(candidate)
    for part in ("experience", "education", "location", "work_arrangement", "working_hours"):
        if candidate.get(f"{part}_match"):
            score += SCORE_WEIGHTS[part]
    return round(score)


def is_strong_match(candidate):
    """Strong Match = skills >= 70% AND experience match AND location match."""
    return (
        skills_ratio(candidate) >= STRONG_MATCH_SKILLS_RATIO
        and bool(candidate.get("experience_match"))
        and bool(candidate.get("location_match"))
    )


def rank_candidates(candidates):
    """Sort candidates best score first and number them 1, 2, 3...

    Candidates whose resume could not be read go last.
    Returns new dicts with "rank" added.
    """
    ranked = sorted(
        candidates,
        key=lambda c: (not c.get("unreadable", False), c.get("match_score", 0)),
        reverse=True,
    )
    return [{**c, "rank": rank} for rank, c in enumerate(ranked, start=1)]
