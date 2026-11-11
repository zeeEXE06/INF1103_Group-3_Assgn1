"""
Candidates - a resume compared with an employer's job posting, and its score.

    Candidate    what the AI found when comparing one resume with the job
    MatchResult  a Candidate with the score and Strong Match label the
                 Logic Manager gave it
"""

from .text import clean_strings


class Candidate:
    """One resume compared with the job posting.

    The five *_match fields are the AI's true/false checks against the job.
    """

    MATCH_FIELDS = (
        "experience_match", "education_match", "location_match",
        "work_arrangement_match", "working_hours_match",
    )

    def __init__(self, filename, name="", matched_skills=(), missing_skills=(), experience=(),
                 education=(), location="", work_arrangement="", working_hours="", summary="",
                 experience_match=False, education_match=False, location_match=False,
                 work_arrangement_match=False, working_hours_match=False, unreadable=False):
        self._filename = filename
        self._name = str(name).strip() or filename
        self._matched_skills = clean_strings(matched_skills)
        self._missing_skills = clean_strings(missing_skills)
        self._experience = clean_strings(experience)
        self._education = clean_strings(education)
        self._location = location
        self._work_arrangement = work_arrangement
        self._working_hours = working_hours
        self._summary = str(summary).strip()
        self._experience_match = bool(experience_match)
        self._education_match = bool(education_match)
        self._location_match = bool(location_match)
        self._work_arrangement_match = bool(work_arrangement_match)
        self._working_hours_match = bool(working_hours_match)
        self._unreadable = bool(unreadable)

    @classmethod
    def unreadable_resume(cls, filename):
        """A placeholder for a resume the AI could not read - it scores 0 and goes last."""
        return cls(filename, summary="Could not read this resume.", unreadable=True)

    @property
    def filename(self):
        return self._filename

    @property
    def name(self):
        """The candidate's name, or the filename if the AI found no name."""
        return self._name

    @property
    def matched_skills(self):
        """Skills the job asks for that the candidate has."""
        return list(self._matched_skills)

    @property
    def missing_skills(self):
        """Skills the job asks for that the candidate does not have."""
        return list(self._missing_skills)

    @property
    def experience(self):
        return list(self._experience)

    @property
    def education(self):
        return list(self._education)

    @property
    def location(self):
        return self._location

    @property
    def work_arrangement(self):
        return self._work_arrangement

    @property
    def working_hours(self):
        return self._working_hours

    @property
    def summary(self):
        return self._summary

    @property
    def experience_match(self):
        return self._experience_match

    @property
    def education_match(self):
        return self._education_match

    @property
    def location_match(self):
        return self._location_match

    @property
    def work_arrangement_match(self):
        return self._work_arrangement_match

    @property
    def working_hours_match(self):
        return self._working_hours_match

    @property
    def unreadable(self):
        return self._unreadable

    @property
    def skills_ratio(self):
        """Share of the job's skills the candidate has, from 0.0 to 1.0."""
        total = len(self._matched_skills) + len(self._missing_skills)
        return len(self._matched_skills) / total if total else 0.0

    def to_dict(self):
        return {
            "filename": self._filename,
            "name": self._name,
            "matched_skills": self.matched_skills,
            "missing_skills": self.missing_skills,
            "experience": self.experience,
            "education": self.education,
            "location": self._location,
            "work_arrangement": self._work_arrangement,
            "working_hours": self._working_hours,
            "summary": self._summary,
            "unreadable": self._unreadable,
            **{field: getattr(self, field) for field in self.MATCH_FIELDS},
        }

    @classmethod
    def from_dict(cls, record):
        """Build from one candidate in a saved candidate_matches record."""
        return cls(
            filename=record.get("filename", ""),
            name=record.get("name", ""),
            matched_skills=record.get("matched_skills", []),
            missing_skills=record.get("missing_skills", []),
            experience=record.get("experience", []),
            education=record.get("education", []),
            location=record.get("location", ""),
            work_arrangement=record.get("work_arrangement", ""),
            working_hours=record.get("working_hours", ""),
            summary=record.get("summary", ""),
            unreadable=record.get("unreadable", False),
            **{field: record.get(field, False) for field in cls.MATCH_FIELDS},
        )


class MatchResult:
    """A Candidate with the score and Strong Match label the Logic Manager gave it.

    The candidate is shared, not copied: the same Candidate can be scored
    again, e.g. with a different scoring profile, giving a new MatchResult.
    """

    def __init__(self, candidate, score, strong_match):
        if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 100:
            raise ValueError(f"A match score must be a whole number from 0 to 100, not {score!r}")
        self._candidate = candidate
        self._score = score
        self._strong_match = bool(strong_match)

    @property
    def candidate(self):
        return self._candidate

    @property
    def score(self):
        return self._score

    @property
    def strong_match(self):
        return self._strong_match

    def to_dict(self):
        """The candidate's fields plus match_score and strong_match, as saved."""
        return {**self._candidate.to_dict(), "match_score": self._score, "strong_match": self._strong_match}

    @classmethod
    def from_dict(cls, record):
        return cls(
            Candidate.from_dict(record),
            score=record.get("match_score", 0),
            strong_match=record.get("strong_match", False),
        )
