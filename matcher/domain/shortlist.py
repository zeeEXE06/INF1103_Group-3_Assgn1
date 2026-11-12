"""
Shortlist - an employer's job posting and the scored candidates compared with it.
"""

from .candidate import MatchResult
from .job import JobPosting
from .scoring_profile import ScoringProfile


class Shortlist:
    """A job posting and the MatchResults of the resumes compared with it.

    The shortlist holds MatchResults that were made elsewhere (by the Logic
    Manager's CandidateScorer) and doesn't create them (aggregation): a
    MatchResult can exist on its own, and can be in more than one shortlist.

    file_hashes: fingerprints of the job posting then each resume, so the
    same set of files can be recognised and its saved shortlist reused.
    profile: the ScoringProfile the results were scored with ("Balanced"
    if not given).
    """

    def __init__(self, job, results=(), file_hashes=(), created_at="", record_id=None, profile=None):
        self._id = record_id
        self._job = job
        self._profile = ScoringProfile.default() if profile is None else profile
        self._results = list(results)
        self._file_hashes = list(file_hashes)
        self._created_at = created_at

    @property
    def id(self):
        """e.g. "C001", or None until the shortlist is saved."""
        return self._id

    @property
    def job(self):
        return self._job

    @property
    def profile(self):
        """The ScoringProfile the results were scored with."""
        return self._profile

    @property
    def results(self):
        """The MatchResults, in the order they were added."""
        return list(self._results)

    @property
    def file_hashes(self):
        return list(self._file_hashes)

    @property
    def created_at(self):
        return self._created_at

    @property
    def strong_matches(self):
        """The results labelled Strong Match."""
        return [result for result in self._results if result.strong_match]

    def add(self, result):
        """Add a MatchResult to the shortlist."""
        self._results.append(result)

    def ranked(self, ranker):
        """The results in the order the given ranker (e.g. CandidateRanker) puts them."""
        return ranker.rank(self._results)

    def __len__(self):
        return len(self._results)

    def to_dict(self):
        """Same shape as a record in data/candidate_matches.json."""
        record = {} if self._id is None else {"id": self._id}
        record.update({
            "file_hashes": self.file_hashes,
            "created_at": self._created_at,
            "job": self._job.to_dict(),
            "profile": self._profile.to_dict(),
            "candidates": [result.to_dict() for result in self._results],
        })
        return record

    @classmethod
    def from_dict(cls, record):
        """Build a Shortlist from a saved candidate_matches record.

        Records saved before profiles existed were scored as "Balanced".
        """
        profile = record.get("profile")
        return cls(
            job=JobPosting.from_dict(record.get("job", {})),
            results=[MatchResult.from_dict(candidate) for candidate in record.get("candidates", [])],
            file_hashes=record.get("file_hashes", []),
            created_at=record.get("created_at", ""),
            record_id=record.get("id"),
            profile=ScoringProfile.from_dict(profile) if profile else None,
        )
