"""
AI tasks - the kinds of request the app sends to the AI.

    ResumeExtractionTask  read a job seeker's resume PDF

Each task is an AITask (contracts/ai.py): it builds its own prompt and
checks the reply has the structure it asked for. The AI Manager runs any
task the same way, so a new kind of request is a new subclass, with no
change to the AI Manager. No scoring or business logic here - that is the
Logic Manager's job.
"""

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
