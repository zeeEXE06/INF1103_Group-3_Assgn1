"""
Test doubles - stand-ins for the real services, so tests never call the AI.

    FakeProvider        an AIProvider that gives fixed replies instead of asking Gemini
    InMemoryRepository  a RecordRepository that keeps records in memory, not files
"""

from ..contracts.ai import AIProvider, AIProviderError
from ..contracts.data import RecordRepository


class FakeProvider(AIProvider):
    """An AIProvider that replies with fixed text, in order.

    A reply that is an exception is raised instead of returned. Once the
    replies run out it raises AIProviderError, like a real provider that
    can't be reached.

        provider = FakeProvider('{"skills": []}', AIProviderError("down"))
    """

    def __init__(self, *replies):
        self._replies = list(replies)
        self._calls = []

    @property
    def calls(self):
        """The contents of every generate() call so far, oldest first."""
        return [list(contents) for contents in self._calls]

    @property
    def call_count(self):
        return len(self._calls)

    def generate(self, contents):
        self._calls.append(list(contents))
        if not self._replies:
            raise AIProviderError("FakeProvider has no replies left")
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class InMemoryRepository(RecordRepository):
    """A RecordRepository that keeps records in a dict instead of JSON files.

    Records are copied in and out, like JsonRepository, so changing a
    returned record never changes what is stored.
    """

    def __init__(self):
        self._collections = {}

    def load(self, collection):
        return [dict(record) for record in self._collections.get(collection, [])]

    def save(self, collection, record):
        records = self._collections.setdefault(collection, [])
        record = {"id": f"{collection[0].upper()}{len(records) + 1:03d}", **record}
        records.append(dict(record))
        return record

    def collection_names(self):
        return sorted(self._collections)
