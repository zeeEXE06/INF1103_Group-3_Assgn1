"""
Tests for the AI tasks: each one builds the right prompt and files, and
rejects replies that don't have the structure it asked for.
"""

from ..contracts.ai import AITask
from ..managers.ai_tasks import ResumeExtractionTask
from .test_app import make_pdf_file


# ---------- Shared schema check ----------

def test_list_of_dicts_check_is_shared_by_every_task():
    check = AITask._list_of_dicts_problem
    assert check({"skills": [{"skill": "SQL"}]}, "skills") is None
    assert check({"skills": []}, "skills") is None
    assert check({}, "skills") == '"skills" is not a list'
    assert check({"skills": ["SQL"]}, "skills") == '"skills" must only contain objects'


# ---------- ResumeExtractionTask ----------

def test_resume_task_sends_the_pdf_and_the_prompt():
    resume_file = make_pdf_file()
    task = ResumeExtractionTask(resume_file)
    assert task.build_contents() == [resume_file, ResumeExtractionTask.PROMPT]
    assert "extract the candidate's education" in task.PROMPT
    assert task.name == "resume extraction"


def test_resume_task_schema():
    task = ResumeExtractionTask(make_pdf_file())
    assert task.schema_problem({"education": [], "experience": [{}], "skills": []}) is None
    assert task.schema_problem({"education": [], "skills": []}) == '"experience" is not a list'
    assert task.schema_problem({"education": ["BSc"], "experience": [], "skills": []}) is not None
