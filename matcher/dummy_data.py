"""
Sprint 1 placeholder data layer.

These are plain Python dataclasses, NOT Django ORM models. They exist so
the UI (views, templates) has something realistic to render before the
Data Manager (Sprint 2) exists to load real records from CSV/JSON, and
before the AI Manager (Sprint 4) exists to produce real match analysis.

Field names deliberately mirror the structured record shapes described
in the project spec (candidate record, AI output schema) so that when
Sprint 2-4 land, the views barely need to change — only where the data
comes from changes.

Nothing in this file performs I/O. Loading/saving records is the Data
Manager's job (Sprint 2); this module only defines shapes and sample data.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class WorkPreferences:
    wfh: bool = False
    hybrid: bool = False
    on_site: bool = False
    flexible_hours: bool = False


@dataclass
class Candidate:
    """A job seeker's resume, once structured."""

    candidate_id: str
    filename: str
    name: str
    skills: List[str]
    experience: List[str]
    education: List[str]
    location: str
    work_preferences: WorkPreferences

    # --- Fields populated later by the AI Manager + Logic Manager ---
    match_score: int = 0
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    experience_match: bool = False
    location_match: bool = False
    work_arrangement_match: bool = False
    summary: str = ""
    rank: int = 0


@dataclass
class Job:
    """A job posting, once structured."""

    job_id: str
    title: str
    company: str
    required_skills: List[str]
    location: str
    work_arrangement: str  # "WFH" | "Hybrid" | "On-site" | "Flexible"
    working_hours: str  # "Standard" | "Flexible" | "Shift-based" | "No preference"

    # --- Fields populated later by the AI Manager + Logic Manager ---
    match_score: int = 0
    matched_skills: List[str] = field(default_factory=list)
    missing_skills: List[str] = field(default_factory=list)
    experience_match: bool = False
    location_match: bool = False
    work_arrangement_match: bool = False
    working_hours_match: bool = False
    summary: str = ""
    rank: int = 0


def sample_ranked_candidates() -> List[Candidate]:
    """Hardcoded, already-ranked candidates for the employer results page."""

    candidates = [
        Candidate(
            candidate_id="C001",
            filename="candidate_01.pdf",
            name="John Tan",
            skills=["Python", "Django", "SQL", "REST API"],
            experience=["Software Developer, 3 years"],
            education=["B.Sc. Computer Science"],
            location="Central",
            work_preferences=WorkPreferences(wfh=True, flexible_hours=True),
            match_score=92,
            matched_skills=["Python", "Django", "SQL", "REST API"],
            missing_skills=["Docker"],
            experience_match=True,
            location_match=True,
            work_arrangement_match=True,
            summary="Strong technical match with 3 years of directly relevant experience.",
            rank=1,
        ),
        Candidate(
            candidate_id="C002",
            filename="candidate_02.pdf",
            name="Priya Sundaram",
            skills=["Python", "Flask", "PostgreSQL", "Docker"],
            experience=["Backend Engineer, 2 years"],
            education=["B.Eng. Information Systems"],
            location="North",
            work_preferences=WorkPreferences(hybrid=True),
            match_score=78,
            matched_skills=["Python", "PostgreSQL", "Docker"],
            missing_skills=["Django", "REST API"],
            experience_match=True,
            location_match=False,
            work_arrangement_match=True,
            summary="Solid backend fundamentals but framework experience differs from the posting.",
            rank=2,
        ),
        Candidate(
            candidate_id="C003",
            filename="candidate_03.pdf",
            name="Marcus Lim",
            skills=["Java", "Spring Boot", "MySQL"],
            experience=["Junior Developer, 1 year"],
            education=["Diploma in IT"],
            location="Central",
            work_preferences=WorkPreferences(on_site=True),
            match_score=41,
            matched_skills=["MySQL"],
            missing_skills=["Python", "Django", "REST API"],
            experience_match=False,
            location_match=True,
            work_arrangement_match=False,
            summary="Different tech stack; limited overlap with the role's core requirements.",
            rank=3,
        ),
    ]
    return candidates


def sample_ranked_jobs() -> List[Job]:
    """Hardcoded, already-ranked jobs for the job seeker results page."""

    jobs = [
        Job(
            job_id="J001",
            title="Software Developer",
            company="Brightleaf Systems",
            required_skills=["Python", "Django", "SQL"],
            location="Central",
            work_arrangement="WFH",
            working_hours="Flexible",
            match_score=91,
            matched_skills=["Python", "Django", "SQL"],
            missing_skills=[],
            experience_match=True,
            location_match=True,
            work_arrangement_match=True,
            working_hours_match=True,
            summary="A near-complete skills match with fully compatible work arrangement.",
            rank=1,
        ),
        Job(
            job_id="J002",
            title="Backend Engineer",
            company="Harborview Digital",
            required_skills=["Python", "PostgreSQL", "Docker", "AWS"],
            location="East",
            work_arrangement="Hybrid",
            working_hours="Standard",
            match_score=68,
            matched_skills=["Python", "Docker"],
            missing_skills=["PostgreSQL", "AWS"],
            experience_match=True,
            location_match=False,
            work_arrangement_match=True,
            working_hours_match=False,
            summary="Good technical overlap, though location and hours differ from your preferences.",
            rank=2,
        ),
        Job(
            job_id="J003",
            title="Data Analyst",
            company="Quill & Compass",
            required_skills=["SQL", "Excel", "Tableau"],
            location="West",
            work_arrangement="On-site",
            working_hours="Shift-based",
            match_score=35,
            matched_skills=["SQL"],
            missing_skills=["Excel", "Tableau"],
            experience_match=False,
            location_match=False,
            work_arrangement_match=False,
            working_hours_match=False,
            summary="Limited overlap with your skill set and stated work preferences.",
            rank=3,
        ),
    ]
    return jobs
