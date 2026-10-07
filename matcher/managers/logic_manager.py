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


def filter_jobs(jobs, work_arrangements, locations, working_hours, industry):
    """Keep only the jobs that match the chosen filters.

    An empty filter (nothing ticked / "" for industry) means "show all".
    """
    filtered_jobs = []
    for job in jobs:
        if work_arrangements and job.work_arrangement not in work_arrangements:
            continue
        if locations and job.location not in locations:
            continue
        if working_hours and job.working_hours not in working_hours:
            continue
        if industry and job.industry != industry:
            continue
        filtered_jobs.append(job)
    return filtered_jobs


# TODO (Sprint 3): calculate_score()
# TODO (Sprint 3): is_strong_match()
# TODO (Sprint 3): rank_candidates() / rank_jobs()
