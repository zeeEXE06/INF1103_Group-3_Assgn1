"""
Resume - a job seeker's resume, as read by the AI.
"""


class Resume:
    """A job seeker's education, experience and skills.

    education:  [{"qualification", "institution", "field_of_study", "start_date", "end_date"}]
    experience: [{"job_title", "company", "start_date", "end_date"}]
    skills:     [{"skill": "Python"}, ...]
    """

    def __init__(self, filename, file_hash, education=(), experience=(), skills=(),
                 uploaded_at="", record_id=None):
        self._id = record_id
        self._filename = filename
        self._file_hash = file_hash
        self._uploaded_at = uploaded_at
        # Copies, so changing the caller's lists can't change this resume
        self._education = [dict(item) for item in education]
        self._experience = [dict(item) for item in experience]
        self._skills = [dict(item) for item in skills]

    @property
    def id(self):
        """e.g. "R001", or None until the resume is saved."""
        return self._id

    @property
    def filename(self):
        return self._filename

    @property
    def file_hash(self):
        """SHA-256 fingerprint of the PDF, the same for identical files."""
        return self._file_hash

    @property
    def uploaded_at(self):
        return self._uploaded_at

    @property
    def education(self):
        return [dict(item) for item in self._education]

    @property
    def experience(self):
        return [dict(item) for item in self._experience]

    @property
    def skills(self):
        return [dict(item) for item in self._skills]

    @property
    def skill_names(self):
        """e.g. ["Python", "Django"] - blank skills are left out."""
        names = (str(item.get("skill", "")).strip() for item in self._skills)
        return [name for name in names if name]

    def details_for_ai(self):
        """The parts of the resume the AI needs to suggest jobs."""
        return {"education": self.education, "experience": self.experience, "skills": self.skills}

    def to_dict(self):
        record = {} if self._id is None else {"id": self._id}
        record.update({
            "file_hash": self._file_hash,
            "filename": self._filename,
            "uploaded_at": self._uploaded_at,
            **self.details_for_ai(),
        })
        return record

    @classmethod
    def from_dict(cls, record):
        """Build a Resume from a saved record. Missing fields get empty defaults."""
        return cls(
            filename=record.get("filename", ""),
            file_hash=record.get("file_hash", ""),
            education=record.get("education", []),
            experience=record.get("experience", []),
            skills=record.get("skills", []),
            uploaded_at=record.get("uploaded_at", ""),
            record_id=record.get("id"),
        )
