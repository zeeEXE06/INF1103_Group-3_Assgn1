"""
Matching service - the three AI flows, connecting the AI, Data and Logic Managers.

The same input always gives the same output: every uploaded PDF is
fingerprinted, and if the same file (or set of files) was processed before,
the saved result is returned instead of asking the AI again.

    MatchingService.read_resume()              resume PDF -> saved Resume
    MatchingService.match_jobs_to_resume()     saved resume -> suggested jobs with Jobstreet links
    MatchingService.match_candidates_to_job()  job posting + resume PDFs -> saved Shortlist
"""

import hashlib
import logging
import re

from django.conf import settings
from django.utils import timezone

from ..domain.candidate import Candidate
from ..domain.job import JobPosting, JobSuggestion
from ..domain.resume import Resume
from ..domain.shortlist import Shortlist
from ..managers.ai_manager import AIManager
from ..managers.ai_providers import GeminiProvider
from ..managers.ai_tasks import CandidateComparisonTask, JobSuggestionTask, ResumeExtractionTask
from ..managers.data_manager import JsonRepository
from ..managers.io_manager import (
    INDUSTRY_CHOICES,
    LOCATION_CHOICES,
    WORK_ARRANGEMENT_CHOICES,
    WORKING_HOURS_CHOICES,
    JobFilterForm,
)
from ..managers.logic_manager import CandidateRanker, CandidateScorer, JobFilter, JobRanker

logger = logging.getLogger(__name__)


class MatchingError(ValueError):
    """An AI flow could not finish, e.g. the AI could not read the resume.

    A ValueError, because the upload couldn't be turned into a result.
    """


class MatchingService:
    """Runs the app's AI flows by coordinating the AI, Data and Logic Managers.

    The managers are given to the service rather than made by it
    (association): the service uses them but doesn't own them, so the
    tests can pass a FakeProvider and an InMemoryRepository instead of
    Gemini and the JSON files. MatchingService.default() builds the real ones.
    """

    JOBSTREET_BASE_URL = "https://sg.jobstreet.com"

    def __init__(self, ai_manager, repository, scorer, candidate_ranker, job_ranker):
        self._ai = ai_manager
        self._repository = repository
        self._scorer = scorer
        self._candidate_ranker = candidate_ranker
        self._job_ranker = job_ranker

    @classmethod
    def default(cls):
        """The service the app uses: Gemini, the JSON files and the default scoring."""
        return cls(
            AIManager(GeminiProvider()),
            JsonRepository(),
            CandidateScorer(),
            CandidateRanker(),
            JobRanker(),
        )

    # ---------- Job seeker ----------

    def read_resume(self, resume_file):
        """Read a resume PDF with the AI and save it. Returns the saved Resume.

        Raises MatchingError if the AI could not read it.
        """
        resume_hash = self._file_hash(resume_file)
        previous = self._previous("resumes", file_hash=resume_hash)
        if previous:
            return Resume.from_dict(previous)

        reply = self._ai.run(ResumeExtractionTask(resume_file))
        if reply is None:
            raise MatchingError("The AI could not read the resume")

        resume = Resume(
            filename=resume_file.name,
            file_hash=resume_hash,
            education=reply.get("education", []),
            experience=reply.get("experience", []),
            skills=reply.get("skills", []),
            uploaded_at=self._now(),
        )
        return Resume.from_dict(self._repository.save("resumes", resume.to_dict()))

    def match_jobs_to_resume(self, resume_id=None):
        """Ask the AI for job titles that suit a saved resume, and save them
        with a Jobstreet search link for each.

        Uses the newest saved resume unless resume_id is given. Returns the saved
        record, e.g. {"id": "J001", "resume_id": "R001", "jobs": [...]}.
        Raises MatchingError if there is no resume or the AI could not suggest jobs.
        """
        records = self._repository.load("resumes")
        if resume_id is not None:
            records = [record for record in records if record.get("id") == resume_id]
        if not records:
            raise MatchingError(f"No saved resume found (resume_id={resume_id})")
        resume = Resume.from_dict(records[-1])

        max_jobs = settings.MAX_JOBS
        previous = self._previous("job_matches", resume_id=resume.id, max_jobs=max_jobs)
        if previous:
            return previous

        reply = self._ai.run(JobSuggestionTask(resume, max_jobs, JobFilterForm.options_for_ai()))
        if reply is None:
            raise MatchingError("The AI could not suggest jobs")

        jobs = [self._job_suggestion(ai_job) for ai_job in reply["jobs"] if ai_job["title"].strip()]
        return self._repository.save("job_matches", {
            "resume_id": resume.id,
            "max_jobs": max_jobs,
            "searched_at": self._now(),
            "jobs": [job.to_dict() for job in self._job_ranker.select_top(jobs, max_jobs)],
        })

    def suggested_jobs(self, job_match_id):
        """The saved jobs for a job search, best match first ([] if not found)."""
        record = self._repository.find("job_matches", job_match_id)
        if not record:
            return []
        return self._job_ranker.rank([JobSuggestion.from_dict(job) for job in record.get("jobs", [])])

    @staticmethod
    def job_filter(filters):
        """A JobFilter for the filters picked on the results page (see JobFilterForm.filters)."""
        return JobFilter(filters["work_arrangement"], filters["locations"],
                         filters["working_hours"], filters["industry"])

    # ---------- Employer ----------

    def match_candidates_to_job(self, job_file, candidate_files):
        """Compare several resumes to one job posting in ONE AI call, score them
        and save the result. Returns the saved Shortlist.

        Raises MatchingError if the AI could not compare them.
        """
        # The job posting's fingerprint, then each resume's, in upload order
        file_hashes = [self._file_hash(job_file)] + [self._file_hash(f) for f in candidate_files]
        previous = self._previous("candidate_matches", file_hashes=file_hashes)
        if previous:
            return Shortlist.from_dict(previous)

        reply = self._ai.run(CandidateComparisonTask(job_file, candidate_files, JobFilterForm.options_for_ai()))
        if reply is None:
            raise MatchingError("The AI could not compare the resumes")

        # Match each AI candidate back to its file by resume number
        by_number = {}
        for ai_candidate in reply["candidates"]:
            by_number.setdefault(ai_candidate["resume_number"], ai_candidate)

        shortlist = Shortlist(self._job_posting(reply["job"], job_file.name),
                              file_hashes=file_hashes, created_at=self._now())
        for number, resume_file in enumerate(candidate_files, start=1):
            ai_candidate = by_number.get(number)
            if ai_candidate is None:
                logger.warning("AI returned no result for resume %s (%s)", number, resume_file.name)
                candidate = Candidate.unreadable_resume(resume_file.name)
            else:
                candidate = self._candidate(ai_candidate, resume_file.name)
            # Logic Manager decides the score and the Strong Match label
            shortlist.add(self._scorer.score(candidate))

        return Shortlist.from_dict(self._repository.save("candidate_matches", shortlist.to_dict()))

    def find_shortlist(self, shortlist_id):
        """The saved Shortlist with this id, or None."""
        record = self._repository.find("candidate_matches", shortlist_id)
        return Shortlist.from_dict(record) if record else None

    def ranked_candidates(self, shortlist):
        """The shortlist's results, best first and unreadable resumes last."""
        return shortlist.ranked(self._candidate_ranker)

    # ---------- Turning the AI's reply into domain objects ----------

    def _job_suggestion(self, ai_job):
        title = ai_job["title"].strip()
        return JobSuggestion(
            title,
            self._jobstreet_url(title),
            match_score=ai_job.get("match_score"),
            location=JobFilterForm.allowed_value(ai_job.get("location"), LOCATION_CHOICES),
            work_arrangement=JobFilterForm.allowed_value(ai_job.get("work_arrangement"), WORK_ARRANGEMENT_CHOICES),
            working_hours=JobFilterForm.allowed_value(ai_job.get("working_hours"), WORKING_HOURS_CHOICES),
            industry=JobFilterForm.allowed_value(ai_job.get("industry"), INDUSTRY_CHOICES),
            matched_skills=self._as_list(ai_job.get("matched_skills")),
            match_reason=str(ai_job.get("match_reason", "")),
        )

    def _candidate(self, ai_candidate, filename):
        return Candidate(
            filename,
            name=ai_candidate.get("name", ""),
            matched_skills=self._as_list(ai_candidate.get("matched_skills")),
            missing_skills=self._as_list(ai_candidate.get("missing_skills")),
            experience=self._as_list(ai_candidate.get("experience")),
            education=self._as_list(ai_candidate.get("education")),
            location=JobFilterForm.allowed_value(ai_candidate.get("location"), LOCATION_CHOICES),
            work_arrangement=JobFilterForm.allowed_value(ai_candidate.get("work_arrangement"), WORK_ARRANGEMENT_CHOICES),
            working_hours=JobFilterForm.allowed_value(ai_candidate.get("working_hours"), WORKING_HOURS_CHOICES),
            summary=ai_candidate.get("summary", ""),
            # Only a real true counts, so e.g. "false" or 1 from the AI is not a match
            **{field: ai_candidate.get(field) is True for field in Candidate.MATCH_FIELDS},
        )

    def _job_posting(self, ai_job, filename):
        return JobPosting(
            filename,
            title=str(ai_job.get("title", "")).strip(),
            company=str(ai_job.get("company", "")).strip(),
            required_skills=self._as_list(ai_job.get("required_skills")),
            location=JobFilterForm.allowed_value(ai_job.get("location"), LOCATION_CHOICES),
            work_arrangement=JobFilterForm.allowed_value(ai_job.get("work_arrangement"), WORK_ARRANGEMENT_CHOICES),
            working_hours=JobFilterForm.allowed_value(ai_job.get("working_hours"), WORKING_HOURS_CHOICES),
            industry=JobFilterForm.allowed_value(ai_job.get("industry"), INDUSTRY_CHOICES),
        )

    # ---------- Helpers ----------

    def _previous(self, collection, **fields):
        """The newest saved record with these field values, or None."""
        previous = self._repository.newest(collection, **fields)
        if previous:
            logger.info("Same input as %s %s - reusing the saved result", collection, previous["id"])
        return previous

    @classmethod
    def _jobstreet_url(cls, title):
        """e.g. "Junior Python Developer" -> https://sg.jobstreet.com/junior-python-developer-jobs"""
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        return f"{cls.JOBSTREET_BASE_URL}/{slug}-jobs"

    @staticmethod
    def _file_hash(uploaded_file):
        """Fingerprint of a file's contents (SHA-256), the same for identical files."""
        digest = hashlib.sha256()
        for chunk in uploaded_file.chunks():
            digest.update(chunk)
        uploaded_file.seek(0)
        return digest.hexdigest()

    @staticmethod
    def _as_list(value):
        """Keep a list of non-empty strings, whatever the AI sent."""
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    @staticmethod
    def _now():
        return timezone.now().isoformat(timespec="seconds")
