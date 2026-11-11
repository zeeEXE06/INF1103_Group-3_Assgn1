"""
Tests for the AIManager class. FakeProvider stands in for Gemini, and a
small SkillsTask stands in for the app's real AI tasks.
"""

from unittest.mock import MagicMock, patch

from ..contracts.ai import AIProviderError, AITask
from ..managers.ai_manager import AIManager
from ..managers.ai_providers import GeminiProvider
from .fakes import FakeProvider

GOOD_REPLY = '{"skills": ["Python"]}'
WRONG_SHAPE_REPLY = '{"skills": "Python"}'


class SkillsTask(AITask):
    """A minimal task: the reply needs a "skills" list."""

    name = "skills"

    def build_contents(self):
        return ["List the skills."]

    def schema_problem(self, data):
        return None if isinstance(data.get("skills"), list) else '"skills" is not a list'


# ---------- Running a task ----------

def test_valid_reply_is_returned():
    provider = FakeProvider(GOOD_REPLY)
    assert AIManager(provider).run(SkillsTask()) == {"skills": ["Python"]}
    assert provider.calls == [["List the skills."]]


def test_broken_or_wrong_shape_reply_is_asked_again():
    for bad in ('{"broken', WRONG_SHAPE_REPLY):
        provider = FakeProvider(bad, GOOD_REPLY)
        assert AIManager(provider).run(SkillsTask()) == {"skills": ["Python"]}
        assert provider.call_count == 2


def test_gives_up_after_repeated_wrong_shape():
    provider = FakeProvider(WRONG_SHAPE_REPLY, WRONG_SHAPE_REPLY, GOOD_REPLY)
    assert AIManager(provider).run(SkillsTask()) is None
    assert provider.call_count == AIManager.REPLY_ATTEMPTS


def test_provider_failure_returns_none_instead_of_crashing():
    provider = FakeProvider(AIProviderError("every model busy"), GOOD_REPLY)
    assert AIManager(provider).run(SkillsTask()) is None
    assert provider.call_count == 1  # a provider failure is not asked again


def test_unreachable_ai_returns_none():
    assert AIManager(FakeProvider()).run(SkillsTask()) is None


def test_manager_keeps_the_provider_it_was_given():
    provider = FakeProvider()
    assert AIManager(provider).provider is provider


def test_manager_gives_the_same_result_with_any_provider():
    """Gemini and FakeProvider can replace each other without changing the result."""
    client = MagicMock()
    client.models.generate_content.return_value = MagicMock(text=GOOD_REPLY)
    with patch.object(GeminiProvider, "_get_client", return_value=client):
        from_gemini = AIManager(GeminiProvider(api_key="test", fallback_models=[])).run(SkillsTask())
    from_fake = AIManager(FakeProvider(GOOD_REPLY)).run(SkillsTask())
    assert from_gemini == from_fake == {"skills": ["Python"]}


# ---------- Reading the reply ----------

def test_parse_json_reply():
    parse = AIManager.parse_json_reply
    assert parse('```json\n{"skills": [{"skill": "SQL"}]}\n```') == {"skills": [{"skill": "SQL"}]}
    assert parse('Here are the jobs I found:\n{"jobs": []}\nGood luck!') == {"jobs": []}
    assert parse("PDF received") is None
    assert parse("[1, 2]") is None
    assert parse("") is None and parse(None) is None
