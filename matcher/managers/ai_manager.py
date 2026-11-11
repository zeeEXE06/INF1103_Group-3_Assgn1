"""
AI Manager - runs the AI tasks through an AI provider and returns only
replies that have the expected JSON structure.

    ai_providers.py  GeminiProvider - talks to Google Gemini
    ai_tasks.py      ResumeExtractionTask, JobSuggestionTask,
                     CandidateComparisonTask - what to ask, and what a
                     valid reply looks like
    ai_manager.py    AIManager - asks, checks the reply, asks again if
                     it is in the wrong format

It never raises: if the AI fails or keeps replying in the wrong format, the
error is logged and None is returned.

No scoring or business logic here - that is the Logic Manager's job.
"""

import json
import logging

from ..contracts.ai import AIProviderError

logger = logging.getLogger(__name__)


class AIManager:
    """Runs any AITask through an AIProvider and returns only valid replies.

    The provider is given to the AI Manager rather than made by it, so the
    same AI Manager works with Gemini or, in the tests, a FakeProvider.

    run() never raises: if the AI fails or keeps replying in the wrong
    format, the problem is logged and None is returned.
    """

    # Times to ask before giving up on a reply in the wrong format
    REPLY_ATTEMPTS = 2

    def __init__(self, provider):
        self._provider = provider

    @property
    def provider(self):
        return self._provider

    def run(self, task):
        """Ask the AI for this task and return its reply as a dict, or None.

        A reply that is not JSON, or fails task.schema_problem(), is
        rejected and asked for again (up to REPLY_ATTEMPTS times).
        """
        logger.info("AI Manager running %s", task.name)
        for attempt in range(1, self.REPLY_ATTEMPTS + 1):
            try:
                reply = self._provider.generate(task.build_contents())
            except AIProviderError:
                logger.exception("AI request for %s failed", task.name)
                return None

            data = self.parse_json_reply(reply)
            problem = "not valid JSON" if data is None else task.schema_problem(data)
            if problem is None:
                return data
            logger.warning(
                "AI reply for %s rejected (%s), attempt %s of %s",
                task.name, problem, attempt, self.REPLY_ATTEMPTS,
            )
        return None

    @staticmethod
    def parse_json_reply(reply):
        """Turn the AI's text reply into a dict. Returns None if it is not a JSON object."""
        text = (reply or "").strip()

        # Models often wrap JSON in ```json ... ```
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            text = text.rsplit("```", 1)[0]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Some replies add a sentence around the JSON - try just the {...} part
            start, end = text.find("{"), text.rfind("}")
            data = None
            if start != -1 and end > start:
                try:
                    data = json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            if data is None:
                logger.warning("AI reply is not valid JSON: %.200s", reply)
                return None

        if not isinstance(data, dict):
            logger.warning("AI reply is JSON but not an object: %.200s", reply)
            return None
        return data
