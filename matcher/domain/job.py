"""
Jobs - a job title suggested to a job seeker, and an employer's job posting.
"""

from .text import clean_strings


class JobSuggestion:
    """A job title the AI suggested for a resume, with a Jobstreet search link.

    match_score is always a whole number from 0 to 100.
    """

    def __init__(self, title, url, match_score=0, location="", work_arrangement="",
                 working_hours="", industry="", matched_skills=(), match_reason=""):
        self._title = title.strip()
        self._url = url
        self._match_score = self._to_score(match_score)
        self._location = location
        self._work_arrangement = work_arrangement
        self._working_hours = working_hours
        self._industry = industry
        self._matched_skills = clean_strings(matched_skills)
        self._match_reason = match_reason

    @staticmethod
    def _to_score(value):
        """A whole number from 0 to 100 (0 if it isn't a number)."""
        try:
            return max(0, min(100, round(float(value))))
        except (TypeError, ValueError, OverflowError):
            return 0

    @property
    def title(self):
        return self._title

    @property
    def url(self):
        return self._url

    @property
    def match_score(self):
        return self._match_score

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
    def industry(self):
        return self._industry

    @property
    def matched_skills(self):
        return list(self._matched_skills)

    @property
    def match_reason(self):
        return self._match_reason

    def to_dict(self):
        return {
            "title": self._title,
            "url": self._url,
            "match_score": self._match_score,
            "location": self._location,
            "work_arrangement": self._work_arrangement,
            "working_hours": self._working_hours,
            "industry": self._industry,
            "matched_skills": self.matched_skills,
            "match_reason": self._match_reason,
        }

    @classmethod
    def from_dict(cls, record):
        """Build from one job in a saved job_matches record. Missing fields get defaults."""
        return cls(
            title=record.get("title", ""),
            url=record.get("url", ""),
            match_score=record.get("match_score", 0),
            location=record.get("location", ""),
            work_arrangement=record.get("work_arrangement", ""),
            working_hours=record.get("working_hours", ""),
            industry=record.get("industry", ""),
            matched_skills=record.get("matched_skills", []),
            match_reason=record.get("match_reason", ""),
        )


class JobPosting:
    """An employer's job posting, as read by the AI."""

    def __init__(self, filename, title="", company="", required_skills=(), location="",
                 work_arrangement="", working_hours="", industry=""):
        self._filename = filename
        self._title = title
        self._company = company
        self._required_skills = clean_strings(required_skills)
        self._location = location
        self._work_arrangement = work_arrangement
        self._working_hours = working_hours
        self._industry = industry

    @property
    def filename(self):
        return self._filename

    @property
    def title(self):
        return self._title

    @property
    def company(self):
        return self._company

    @property
    def required_skills(self):
        return list(self._required_skills)

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
    def industry(self):
        return self._industry

    def to_dict(self):
        return {
            "filename": self._filename,
            "title": self._title,
            "company": self._company,
            "required_skills": self.required_skills,
            "location": self._location,
            "work_arrangement": self._work_arrangement,
            "working_hours": self._working_hours,
            "industry": self._industry,
        }

    @classmethod
    def from_dict(cls, record):
        """Build from the "job" of a saved candidate_matches record."""
        return cls(
            filename=record.get("filename", ""),
            title=record.get("title", ""),
            company=record.get("company", ""),
            required_skills=record.get("required_skills", []),
            location=record.get("location", ""),
            work_arrangement=record.get("work_arrangement", ""),
            working_hours=record.get("working_hours", ""),
            industry=record.get("industry", ""),
        )
