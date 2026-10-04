"""LLM client interface for relationship suggestion extraction and document chat."""

import json
import re
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import httpx
from backend.app.settings import get_settings


class LLMNotConfiguredError(Exception):
    """Raised when an LLM call is attempted without an API key or configuration."""
    pass


class BaseLLMClient(ABC):
    """Abstract interface for LLM completions."""

    @abstractmethod
    def complete_json(self, prompt: str) -> Dict[str, Any]:
        """Send prompt and return structured parsed JSON object."""
        pass

    @abstractmethod
    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Send conversation messages and return plain text completion."""
        pass


class FakeLLMClient(BaseLLMClient):
    """Deterministic fake LLM client for tests."""

    def __init__(
        self,
        default_type: str = "supports",
        fail: bool = False,
        malformed: bool = False,
        canned_answer: Optional[str] = None,
    ) -> None:
        self.default_type = default_type
        self.fail = fail
        self.malformed = malformed
        self.canned_answer = canned_answer

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

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Return deterministic answer citing IDs given in the context."""
        if self.fail:
            raise RuntimeError("Fake LLM upstream service failure")
        if self.canned_answer is not None:
            return self.canned_answer

        # Scan messages for citation IDs [s1], [a2], [r3]
        combined = " ".join(m.get("content", "") for m in messages)
        raw_ids = re.findall(r"\[([sar]\d+)\]", combined)

        # Keep ordered unique IDs
        unique_ids = []
        for cid in raw_ids:
            if cid not in unique_ids:
                unique_ids.append(cid)

        if not unique_ids:
            return "Based on the provided document, I could not find information regarding this question."

        cited_str = " ".join(f"[{cid}]" for cid in unique_ids[:3])
        return f"According to the document text and annotations, the answer is confirmed by {cited_str}."


def _extract_json_object(content: str) -> Dict[str, Any]:
    """Parse JSON object from text, handling markdown fences, trailing text, and extra braces."""
    trimmed = content.strip()
    if trimmed.startswith("```"):
        lines = trimmed.splitlines()
        if len(lines) >= 2 and lines[-1].strip().startswith("```"):
            trimmed = "\n".join(lines[1:-1]).strip()
        elif lines[0].strip().startswith("```"):
            trimmed = "\n".join(lines[1:]).strip()

    try:
        return json.loads(trimmed)
    except json.JSONDecodeError:
        idx = trimmed.find("{")
        if idx != -1:
            try:
                decoder = json.JSONDecoder()
                obj, _ = decoder.raw_decode(trimmed[idx:])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass
        match = re.search(r"\{.*\}", trimmed, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


class OpenAILLMClient(BaseLLMClient):
    """OpenAI API client implementation."""

    def __init__(self) -> None:
        settings = get_settings()
        if not settings.llm_api_key:
            raise LLMNotConfiguredError("LLM API key is not configured in settings")
        self.api_key = settings.llm_api_key
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout_seconds
        self._semaphore = threading.Semaphore(settings.llm_max_concurrency)

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
                {
                    "role": "system",
                    "content": "You are a precise relational knowledge graph extraction assistant. You only output valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
        }

        with self._semaphore:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return _extract_json_object(content)

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Call OpenAI chat completions API expecting plain text response."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
        }

        with self._semaphore:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"]


class HuggingFaceLLMClient(BaseLLMClient):
    """Hugging Face Serverless Inference client using official huggingface_hub."""

    DEFAULT_MODEL = "meta-llama/Llama-3.2-1B-Instruct"

    def __init__(self) -> None:
        from huggingface_hub import InferenceClient

        settings = get_settings()
        token = settings.hf_token or settings.llm_api_key
        if not token:
            raise LLMNotConfiguredError(
                "Hugging Face token is not configured. Set HF_TOKEN or LLM_API_KEY in your environment."
            )
        self.api_key = token
        if settings.llm_model and settings.llm_model != "gpt-4o-mini":
            self.model = settings.llm_model
        else:
            self.model = self.DEFAULT_MODEL

        self.timeout = settings.llm_timeout_seconds
        self._semaphore = threading.Semaphore(settings.llm_max_concurrency)
        provider = settings.hf_provider if settings.hf_provider else None
        self._client = InferenceClient(
            api_key=self.api_key,
            provider=provider,
            timeout=self.timeout,
        )

    def _call_with_retry(self, **kwargs) -> Any:
        """Execute chat completion with transient error retries."""
        import time

        max_attempts = 3
        last_error = None
        for attempt in range(max_attempts):
            try:
                return self._client.chat.completions.create(**kwargs)
            except Exception as exc:
                last_error = exc
                if attempt < max_attempts - 1:
                    time.sleep(0.8 * (attempt + 1))
                else:
                    raise last_error

    def complete_json(self, prompt: str) -> Dict[str, Any]:
        """Call Hugging Face chat completion API expecting JSON response."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a precise relational knowledge graph extraction assistant. "
                    "You must return ONLY a raw JSON object with no Markdown backticks, "
                    "no explanations, and no other text."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        with self._semaphore:
            resp = self._call_with_retry(
                model=self.model,
                messages=messages,
                max_tokens=512,
                temperature=0.0,
            )
            content = resp.choices[0].message.content
            return _extract_json_object(content)

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Call Hugging Face chat completions API expecting plain text response."""
        with self._semaphore:
            resp = self._call_with_retry(
                model=self.model,
                messages=messages,
                max_tokens=1024,
                temperature=0.0,
            )
            return resp.choices[0].message.content.strip()


_shared_llm_client: Optional[BaseLLMClient] = None


def get_llm_client() -> BaseLLMClient:
    """Return configured LLM client instance or raise LLMNotConfiguredError."""
    global _shared_llm_client
    if _shared_llm_client is not None:
        return _shared_llm_client

    settings = get_settings()
    provider = (settings.llm_provider or "").lower().strip()
    if provider == "fake":
        return FakeLLMClient()

    if provider in ("huggingface", "hf"):
        return HuggingFaceLLMClient()

    if provider == "openai":
        return OpenAILLMClient()

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def set_shared_llm_client(client: Optional[BaseLLMClient]) -> None:
    """Explicitly override LLM client instance (for test mocking)."""
    global _shared_llm_client
    _shared_llm_client = client
