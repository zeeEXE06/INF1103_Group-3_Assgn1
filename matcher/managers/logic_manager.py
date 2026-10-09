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

