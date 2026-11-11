"""
Tests for the AI tasks: each one builds the right prompt and files, and
rejects replies that don't have the structure it asked for.
"""

from ..contracts.ai import AITask
from ..domain.resume import Resume
from ..managers.ai_tasks import JobSuggestionTask, ResumeExtractionTask
from .test_app import make_pdf_file

OPTIONS = {
    "locations": "North, South, East, West, Central",
    "work_arrangements": "WFH, Hybrid, On-site, Flexible",
    "working_hours": "Standard, Flexible, Shift-based",
    "industries": "Technology / IT, Finance / Banking",
}


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


# ---------- JobSuggestionTask ----------

def job_task(max_jobs=5):
    resume = Resume("r.pdf", "abc", skills=[{"skill": "Python"}], experience=[{"job_title": "Intern"}])
    return JobSuggestionTask(resume, max_jobs, OPTIONS)


def test_job_task_prompt_includes_the_resume_limit_and_options():
    [prompt] = job_task(max_jobs=7).build_contents()
    assert '"skill": "Python"' in prompt and '"job_title": "Intern"' in prompt
    assert "at most 7 job titles" in prompt
    assert "location: North, South, East, West, Central" in prompt
    assert "industry: Technology / IT, Finance / Banking" in prompt


def test_job_task_prompt_asks_for_json():
    [prompt] = job_task().build_contents()
    assert '"jobs": [' in prompt and "{resume_json}" not in prompt


def test_job_task_schema():
    task = job_task()
    assert task.schema_problem({"jobs": [{"title": "Dev"}]}) is None
    assert task.schema_problem({"jobs": []}) is None
    assert task.schema_problem({"jobs": "none"}) == '"jobs" is not a list'
    assert task.schema_problem({"jobs": [{"title": 5}]}) == 'every job needs a "title" string'
    assert task.schema_problem({"jobs": [{}]}) is not None


def test_job_task_keeps_its_own_copy_of_the_options():
    options = dict(OPTIONS)
    task = JobSuggestionTask(Resume("r.pdf", "abc"), 5, options)
    options["locations"] = "Mars"
    assert "Mars" not in task.build_contents()[0]
