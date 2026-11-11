"""
AI contracts - what the AI Manager needs from an AI model and from a request.

    AIProvider  sends contents to a model and returns its text reply.
                e.g. GeminiProvider, or FakeProvider in the tests.
    AITask      one kind of request: what to send and what a valid reply
                looks like. e.g. ResumeExtractionTask.

The AI Manager runs any AITask through any AIProvider: it sends
task.build_contents(), parses the reply as JSON and rejects it if
task.schema_problem() finds a problem.
"""

from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """The AI gave no reply: bad API key, network down, every model busy, etc."""


class AIProvider(ABC):
    """Interface for an AI model that replies to a list of contents."""

    @abstractmethod
    def generate(self, contents):
        """Send contents to the model and return its reply as text.

        contents: a list of str (text) and uploaded files (PDFs). The
        provider turns each file into whatever its API expects.

        Asks for a JSON reply at temperature 0, so the same contents give
        the same reply. Raises AIProviderError if there is no reply.
        """


class AITask(ABC):
    """One kind of AI request, e.g. "read this resume"."""

    @property
    @abstractmethod
    def name(self):
        """Short name for log messages, e.g. "resume extraction"."""

    @abstractmethod
    def build_contents(self):
        """The prompt and files to send, as a list for AIProvider.generate()."""

    @abstractmethod
    def schema_problem(self, data):
        """Check a parsed reply (a dict) has the expected structure.

        Returns a short description of the first problem found, e.g.
        '"skills" is not a list', or None if the reply is valid.
        """

    @staticmethod
    def _list_of_dicts_problem(data, key):
        """Shared check for subclasses: a problem if data[key] isn't a list of objects, else None."""
        if not isinstance(data.get(key), list):
            return f'"{key}" is not a list'
        if not all(isinstance(item, dict) for item in data[key]):
            return f'"{key}" must only contain objects'
        return None
