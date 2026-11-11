"""
Tests for the contracts in matcher/contracts: the abstract base classes
can't be used until a subclass fills in every abstract method.
"""

from ..contracts.ai import AIProvider, AIProviderError, AITask
from ..contracts.data import RecordRepository
from ..contracts.scoring import ScoreComponent
from .test_app import raises


# ---------- AI contracts ----------

class EchoProvider(AIProvider):
    """Replies with the text parts it was sent."""

    def generate(self, contents):
        return " ".join(part for part in contents if isinstance(part, str))


class SkillsTask(AITask):
    name = "skills"

    def build_contents(self):
        return ["List the skills."]

    def schema_problem(self, data):
        return None if isinstance(data.get("skills"), list) else '"skills" is not a list'


def test_ai_contracts_cannot_be_created_directly():
    assert raises(TypeError, AIProvider)
    assert raises(TypeError, AITask)


def test_ai_subclass_must_fill_in_every_abstract_method():
    class NoSchemaTask(AITask):
        name = "incomplete"

        def build_contents(self):
            return []

    assert raises(TypeError, NoSchemaTask)


def test_any_task_runs_through_any_provider():
    task = SkillsTask()
    assert EchoProvider().generate(task.build_contents()) == "List the skills."
    assert task.schema_problem({"skills": []}) is None
    assert task.schema_problem({}) == '"skills" is not a list'


def test_provider_error_is_an_exception():
    assert issubclass(AIProviderError, Exception)


# ---------- Data contract ----------

class DictRepository(RecordRepository):
    """The smallest repository: only load, save and collection_names."""

    def __init__(self):
        self._collections = {}

    def load(self, collection):
        return list(self._collections.get(collection, []))

    def save(self, collection, record):
        records = self._collections.setdefault(collection, [])
        record = {"id": f"{collection[0].upper()}{len(records) + 1:03d}", **record}
        records.append(record)
        return record

    def collection_names(self):
        return sorted(self._collections)


def test_repository_contract_cannot_be_created_directly():
    assert raises(TypeError, RecordRepository)


def test_repository_subclass_gets_find_and_filter_for_free():
    repository = DictRepository()
    first = repository.save("resumes", {"filename": "a.pdf", "file_hash": "x"})
    repository.save("resumes", {"filename": "b.pdf", "file_hash": "y"})

    assert repository.find("resumes", first["id"]) == first
    assert repository.find("resumes", "R999") is None
    assert repository.find("resumes", "") is None
    assert [r["filename"] for r in repository.filter("resumes", file_hash="y")] == ["b.pdf"]
    assert repository.filter("resumes", file_hash="z") == []


def test_repository_newest_returns_the_last_match():
    repository = DictRepository()
    repository.save("job_matches", {"resume_id": "R001", "max_jobs": 5})
    newer = repository.save("job_matches", {"resume_id": "R001", "max_jobs": 5})

    assert repository.newest("job_matches", resume_id="R001") == newer
    assert repository.newest("job_matches", resume_id="R002") is None


def test_repository_loads_everything_at_startup():
    repository = DictRepository()
    repository.save("resumes", {"filename": "a.pdf"})
    repository.save("job_matches", {"resume_id": "R001"})

    everything = repository.load_everything()
    assert sorted(everything) == ["job_matches", "resumes"]
    assert len(everything["resumes"]) == 1


# ---------- Scoring contract ----------

class ShareOfSkills(ScoreComponent):
    """Test component: the share of skills a candidate has."""

    name = "skills"

    def fraction(self, candidate):
        return candidate["share"]


def test_score_component_contract_cannot_be_created_directly():
    assert raises(TypeError, ScoreComponent, 10)


def test_score_component_points_are_weight_times_fraction():
    component = ShareOfSkills(40)
    assert component.weight == 40
    assert component.points({"share": 0.5}) == 20
    assert component.points({"share": 1.0}) == 40


def test_score_component_points_stay_between_0_and_weight():
    component = ShareOfSkills(40)
    assert component.points({"share": 1.5}) == 40
    assert component.points({"share": -0.5}) == 0


def test_score_component_rejects_bad_weights():
    assert raises(ValueError, ShareOfSkills, -1)
    assert raises(ValueError, ShareOfSkills, "40")
    assert raises(ValueError, ShareOfSkills, True)
    assert ShareOfSkills(0).points({"share": 1.0}) == 0
