"""
AI tasks - the kinds of request the app sends to the AI.

    ResumeExtractionTask  read a job seeker's resume PDF
    JobSuggestionTask     suggest job titles that suit a saved resume

Each task is an AITask (contracts/ai.py): it builds its own prompt and
checks the reply has the structure it asked for. The AI Manager runs any
task the same way, so a new kind of request is a new subclass, with no
change to the AI Manager. No scoring or business logic here - that is the
Logic Manager's job.
"""

import json

from ..contracts.ai import AITask


class ResumeExtractionTask(AITask):
    """Read a resume PDF. A valid reply is {"education", "experience", "skills"}."""

    name = "resume extraction"

    PROMPT = """
Analyze the uploaded resume and extract the candidate's education,
experience and skills.

- Education: degrees, diplomas, certificates, fields of study, schools, dates.
- Experience: job titles, companies, dates of employment.
- Skills: every skill mentioned.

Return ONLY valid JSON in this format (use empty lists if nothing is found):

{
    "education": [
        {
            "qualification": "",
            "institution": "",
            "field_of_study": "",
            "start_date": "",
            "end_date": ""
        }
    ],
    "experience": [
        {
            "job_title": "",
            "company": "",
            "start_date": "",
            "end_date": ""
        }
    ],
    "skills": [
        {
            "skill": ""
        }
    ]
}

Do not invent information that is not present in the resume.
"""

    def __init__(self, resume_file):
        self._resume_file = resume_file

    def build_contents(self):
        return [self._resume_file, self.PROMPT]

    def schema_problem(self, data):
        """Expected: {"education": [{...}], "experience": [{...}], "skills": [{...}]}"""
        for key in ("education", "experience", "skills"):
            problem = self._list_of_dicts_problem(data, key)
            if problem:
                return problem
        return None


class JobSuggestionTask(AITask):
    """Suggest job titles for a saved resume. A valid reply is {"jobs": [{"title": ...}]}.

    options: the values the AI must choose from for each filter, e.g.
    {"locations": "North, South, ...", "work_arrangements": ..., ...}.
    """

    name = "job suggestion"

    PROMPT = """
You are a career advisor in Singapore. Suggest job titles that suit the
candidate below, so they can search for them on Jobstreet.

Candidate resume (JSON):
{resume_json}

Rules:
- Suggest at most {max_jobs} job titles, best match first.
- match_score is a whole number from 0 to 100: how well the resume fits
  the job title's usual requirements (skills, experience, education).
- Use common job titles people actually search for on job sites,
  2-4 words each (e.g. "Junior Python Developer", "Data Analyst").
- No company names, no locations, no duplicate titles.
- matched_skills must only use skills from the resume.
- For location, work_arrangement, working_hours and industry, give what is
  most typical in Singapore for this job title. Use ONLY these values:
  location: {locations}
  work_arrangement: {work_arrangements}
  working_hours: {working_hours}
  industry: {industries}

Return ONLY valid JSON in this format:

{{
    "jobs": [
        {{
            "title": "",
            "match_score": 0,
            "location": "",
            "work_arrangement": "",
            "working_hours": "",
            "industry": "",
            "matched_skills": [""],
            "match_reason": ""
        }}
    ]
}}
"""

    def __init__(self, resume, max_jobs, options):
        """resume: a Resume (matcher/domain/resume.py)."""
        self._resume = resume
        self._max_jobs = max_jobs
        self._options = dict(options)

    def build_contents(self):
        prompt = self.PROMPT.format(
            resume_json=json.dumps(self._resume.details_for_ai(), indent=2),
            max_jobs=self._max_jobs,
            **self._options,
        )
        return [prompt]

    def schema_problem(self, data):
        """Expected: {"jobs": [{"title": "...", ...}]}"""
        problem = self._list_of_dicts_problem(data, "jobs")
        if problem:
            return problem
        if not all(isinstance(job.get("title"), str) for job in data["jobs"]):
            return 'every job needs a "title" string'
        return None
