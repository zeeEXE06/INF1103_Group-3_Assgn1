"""
Logic Manager - scores, ranks and filters the matches.

Sprint 1: filter_jobs() works. Scoring and ranking not built yet -
          dummy_data.py gives already-ranked sample data.
Sprint 3: build the scoring (Skills 40%, Experience 25%, Education 10%,
          Location 10%, Work Arrangement 10%, Working Hours 5%), the
          "Strong Match" rule and the ranking.
Sprint 4: use the AI Manager's output as input.

This file does not call the AI API or read files directly.
"""

# DATA: fields every AI-suggested job has on the results page, with defaults
# for older saved records that are missing some of them
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


def get_field(job, name):
    """Read a field from a job saved as a dict (job_matches.json) or an object (sample data)."""
    if isinstance(job, dict):
        return job.get(name, "")
    return getattr(job, name, "")


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

    Works on the saved jobs from job_matches.json, so filtering never needs
    another AI call. An empty filter (nothing ticked / "" for industry)
    means "show all".
    """
    filtered_jobs = []
    for job in jobs:
        if work_arrangements and get_field(job, "work_arrangement") not in work_arrangements:
            continue
        if locations and get_field(job, "location") not in locations:
            continue
        if working_hours and get_field(job, "working_hours") not in working_hours:
            continue
        if industry and get_field(job, "industry") != industry:
            continue
        filtered_jobs.append(job)
    return filtered_jobs


# ---------- Employer: score and rank candidates ----------

# DATA: how much each part counts towards a candidate's score (adds up to 100)
SCORE_WEIGHTS = {
    "skills": 40,
    "experience": 25,
    "education": 10,
    "location": 10,
    "work_arrangement": 10,
    "working_hours": 5,
}

# "Strong Match" rule: skills at least this share of the job's skills AND
# experience match AND location match
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
