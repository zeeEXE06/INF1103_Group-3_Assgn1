"""
AI providers - the AI models the AI Manager can talk to.

    GeminiProvider  Google Gemini, with retries and backup models

Every provider implements the AIProvider interface (contracts/ai.py), so
the AI Manager works with any of them, e.g. FakeProvider in the tests.

Settings (in .env):
    AI_API_KEY         free Gemini key from https://aistudio.google.com/apikey (required)
    AI_MODEL           Gemini model to use
    AI_FALLBACK_MODELS models to try, in order, if AI_MODEL is busy
    AI_TIMEOUT_SECONDS longest wait for one reply
"""

import logging

import httpx

from django.conf import settings

from ..contracts.ai import AIProvider, AIProviderError

logger = logging.getLogger(__name__)


class GeminiProvider(AIProvider):
    """Google Gemini. Moves on to a backup model if the main one is busy."""

    # Server errors worth retrying on the same model (server error, overloaded, timeout)
    RETRY_STATUS_CODES = (500, 503, 504)
    # Errors that move on to the next model. 429 = this model's quota is used up,
    # and each model has its own quota.
    FALLBACK_STATUS_CODES = (429, *RETRY_STATUS_CODES)

    def __init__(self, api_key=None, model=None, fallback_models=None, timeout_seconds=None):
        """Uses the settings in .env unless other values are given."""
        self._api_key = settings.AI_API_KEY if api_key is None else api_key
        main_model = settings.AI_MODEL if model is None else model
        backups = settings.AI_FALLBACK_MODELS if fallback_models is None else fallback_models
        self._models = [main_model, *backups]
        self._timeout_seconds = settings.AI_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
        if self._timeout_seconds <= 0:
            raise ValueError(f"timeout_seconds must be more than 0, not {self._timeout_seconds!r}")
        self._client = None  # created on the first request

    @property
    def timeout_seconds(self):
        """Longest wait for one reply before giving up."""
        return self._timeout_seconds

    @property
    def models(self):
        """The models to try, in order: the main model, then the backups."""
        return list(self._models)

    def generate(self, contents):
        """Send contents to Gemini and return its reply text.

        Any failure - no API key, bad key, network down, no reply in
        time, every model busy - is raised as AIProviderError, so callers
        only need to handle one kind of error.
        """
        try:
            return self._generate([self._to_part(item) for item in contents])
        except AIProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise AIProviderError(f"Gemini did not reply within {self._timeout_seconds} seconds") from exc
        except Exception as exc:
            raise AIProviderError(f"Gemini request failed: {exc}") from exc

    def _generate(self, parts):
        """Try each model in turn, moving on only if a model is busy.

        Errors that waiting won't fix, like a bad API key, are raised straight away.
        """
        from google.genai import errors

        client = self._get_client()
        config = self._json_config()
        for i, model in enumerate(self._models):
            try:
                response = client.models.generate_content(model=model, contents=parts, config=config)
                return response.text or ""
            except errors.APIError as exc:
                is_last = i == len(self._models) - 1
                if exc.code not in self.FALLBACK_STATUS_CODES or is_last:
                    raise
                logger.warning("%s unavailable (%s), trying %s", model, exc.code, self._models[i + 1])

    def _get_client(self):
        """The Gemini client, created once. Retries busy servers and timeouts after ~2s and ~4s."""
        if self._client is None:
            from google import genai
            from google.genai import types

            if not self._api_key:
                raise AIProviderError("AI_API_KEY is not set in .env")
            self._client = genai.Client(
                api_key=self._api_key,
                http_options=types.HttpOptions(
                    timeout=self._timeout_seconds * 1000,  # the SDK counts in milliseconds
                    retry_options=types.HttpRetryOptions(
                        attempts=3,
                        initial_delay=2,
                        max_delay=10,
                        http_status_codes=list(self.RETRY_STATUS_CODES),
                    ),
                ),
            )
        return self._client

    @staticmethod
    def _json_config():
        """Ask for JSON, and temperature 0 so the same input gives the same answer."""
        from google.genai import types

        return types.GenerateContentConfig(response_mime_type="application/json", temperature=0)

    @staticmethod
    def _to_part(item):
        """Text is sent as it is; an uploaded file is sent as a PDF part."""
        if isinstance(item, str):
            return item
        from google.genai import types

        item.seek(0)
        return types.Part.from_bytes(data=item.read(), mime_type="application/pdf")
