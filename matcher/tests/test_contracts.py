"""
Tests for the contracts in matcher/contracts: the abstract base classes
can't be used until a subclass fills in every abstract method.
"""

from ..contracts.ai import AIProvider, AIProviderError, AITask
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
