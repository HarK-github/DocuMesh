"""LLM client interface for relationship suggestion extraction."""

import json
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx
from backend.app.settings import get_settings


class LLMNotConfiguredError(Exception):
    """Raised when an LLM call is attempted without an API key or configuration."""
    pass


class BaseLLMClient(ABC):
    """Abstract interface for LLM JSON completions."""

    @abstractmethod
    def complete_json(self, prompt: str) -> Dict[str, Any]:
        """Send prompt and return structured parsed JSON object."""
        pass


class FakeLLMClient(BaseLLMClient):
    """Deterministic fake LLM client for tests."""

    def __init__(self, default_type: str = "supports", fail: bool = False, malformed: bool = False) -> None:
        self.default_type = default_type
        self.fail = fail
        self.malformed = malformed

    def complete_json(self, prompt: str) -> Dict[str, Any]:
        """Return mock JSON response or raise error."""
        if self.fail:
            raise RuntimeError("Fake LLM upstream service failure")
        if self.malformed:
            raise json.JSONDecodeError("Expecting value", "bad json", 0)

        # Parse prompt to determine intelligent fake relation
        return {
            "type": self.default_type,
            "reason": "Automated relationship inference by LLM analysis",
        }


class OpenAILLMClient(BaseLLMClient):
    """OpenAI API client implementation."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.llm_api_key:
            raise LLMNotConfiguredError("LLM API key is not configured in settings")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds

    def complete_json(self, prompt: str) -> Dict[str, Any]:
        """Call OpenAI chat completion API expecting JSON response."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are a precise relational knowledge graph extraction assistant. You only output valid JSON."},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)


_shared_llm_client: Optional[BaseLLMClient] = None


def get_llm_client() -> BaseLLMClient:
    """Return configured LLM client instance or raise LLMNotConfiguredError."""
    global _shared_llm_client
    if _shared_llm_client is not None:
        return _shared_llm_client

    settings = get_settings()
    if settings.llm_provider == "fake":
        return FakeLLMClient()

    if not settings.llm_api_key:
        raise LLMNotConfiguredError("LLM_API_KEY environment variable is missing or empty")

    if settings.llm_provider == "openai":
        return OpenAILLMClient()

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def set_shared_llm_client(client: Optional[BaseLLMClient]) -> None:
    """Explicitly override LLM client instance (for test mocking)."""
    global _shared_llm_client
    _shared_llm_client = client
