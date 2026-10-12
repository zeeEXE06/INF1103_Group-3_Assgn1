"""
Sample results shown when DATA_MODE=debug, so the pages can be tried
without uploading anything or calling the AI.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Candidate:
    """A sample candidate on the employer results page."""

    name: str
    experience: List[str]
    location: str
    match_score: int
    matched_skills: List[str]
    missing_skills: List[str] = field(default_factory=list)
    experience_match: bool = False
    location_match: bool = False
    work_arrangement_match: bool = False
    summary: str = ""
    rank: int = 0


@dataclass
class Job:
    """A sample job on the job seeker results page."""

    title: str
    company: str
    location: str
    work_arrangement: str  # "WFH" | "Hybrid" | "On-site" | "Flexible"
    working_hours: str  # "Standard" | "Flexible" | "Shift-based"
    industry: str  # one of INDUSTRY_CHOICES in io_manager.py
    match_score: int
    matched_skills: List[str]
    missing_skills: List[str] = field(default_factory=list)
    location_match: bool = False
    work_arrangement_match: bool = False
    working_hours_match: bool = False
    summary: str = ""
    rank: int = 0


def sample_ranked_candidates() -> List[Candidate]:
    """Sample ranked candidates for the employer results page."""
    return [
        Candidate(
            name="John Tan",
            experience=["Software Developer, 3 years"],
            location="Central",
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
            name="Priya Sundaram",
            experience=["Backend Engineer, 2 years"],
            location="North",
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
            name="Marcus Lim",
            experience=["Junior Developer, 1 year"],
            location="Central",
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


def sample_ranked_jobs() -> List[Job]:
    """Sample ranked jobs for the job seeker results page."""
    return [
        Job(
            title="Software Developer",
            company="Brightleaf Systems",
            location="Central",
            work_arrangement="WFH",
            working_hours="Flexible",
            industry="Technology / IT",
            match_score=91,
            matched_skills=["Python", "Django", "SQL"],
            missing_skills=[],
            location_match=True,
            work_arrangement_match=True,
            working_hours_match=True,
            summary="A near-complete skills match with fully compatible work arrangement.",
            rank=1,
        ),
        Job(
            title="Backend Engineer",
            company="Harborview Digital",
            location="East",
            work_arrangement="Hybrid",
            working_hours="Standard",
            industry="Technology / IT",
            match_score=68,
            matched_skills=["Python", "Docker"],
            missing_skills=["PostgreSQL", "AWS"],
            location_match=False,
            work_arrangement_match=True,
            working_hours_match=False,
            summary="Good technical overlap, though location and hours differ from your preferences.",
            rank=2,
        ),
        Job(
            title="Data Analyst",
            company="Quill & Compass",
            location="West",
            work_arrangement="On-site",
            working_hours="Shift-based",
            industry="Finance / Banking",
            match_score=35,
            matched_skills=["SQL"],
            missing_skills=["Excel", "Tableau"],
            location_match=False,
            work_arrangement_match=False,
            working_hours_match=False,
            summary="Limited overlap with your skill set and stated work preferences.",
            rank=3,
        ),
    ]
