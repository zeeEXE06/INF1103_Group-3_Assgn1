"""
Test doubles - stand-ins for the real services, so tests never call the AI.

    FakeProvider  an AIProvider that gives fixed replies instead of asking Gemini
"""

from ..contracts.ai import AIProvider, AIProviderError


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
