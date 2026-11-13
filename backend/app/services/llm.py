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

    def complete_json(self, prompt: str) -> Any:
        """Return mock JSON response or raise error."""
        if self.fail:
            raise RuntimeError("Fake LLM upstream service failure")
        if self.malformed:
            raise json.JSONDecodeError("Expecting value", "bad json", 0)

        # Check if prompt is structured chunk extraction
        if "chunk text:" in prompt.lower() or "chunk index:" in prompt.lower():
            chunk_match = re.search(r'Chunk Text:\s*"""(.*?)"""', prompt, re.DOTALL)
            text_body = chunk_match.group(1).strip() if chunk_match else prompt
            # Split text body into distinct non-empty sentences/lines
            lines = [l.strip() for l in re.split(r'\.\s+|\n+', text_body) if len(l.strip()) > 15]
            if not lines:
                lines = [text_body.strip()]

            # Pick primary sentence for high-precision proximal extraction
            base_sentence = lines[0]
            words = re.findall(r'\b[A-Za-z]{3,}\b', base_sentence)
            name_1 = words[0].capitalize() if len(words) > 0 else "SystemA"
            name_2 = words[-1].capitalize() if len(words) > 1 else "TaskB"

            return {
                "mentions": [
                    {
                        "mention_id": "m1",
                        "surface_form": name_1,
                        "node_type": "Method",
                        "is_claim": False,
                        "evidence_quote": base_sentence,
                    },
                    {
                        "mention_id": "m2",
                        "surface_form": name_2,
                        "node_type": "Problem",
                        "is_claim": False,
                        "evidence_quote": base_sentence,
                    },
                ],
                "relations": [
                    {
                        "source_mention_id": "m1",
                        "target_mention_id": "m2",
                        "relation_type": "solves",
                        "evidence_quote": base_sentence,
                        "reason": f"{name_1} addresses {name_2} in context.",
                    }
                ],
            }

        # Check if prompt is entity adjudication
        if "adjudicate" in prompt.lower() or "same entity" in prompt.lower():
            return {
                "verdict": "DISTINCT",
                "confidence": 0.85,
                "reason": "Different conceptual variants based on context",
            }

        # Check if prompt is sentence classification format
        if "classify" in prompt.lower() or "classifications" in prompt.lower():
            sent_indices = [int(m) for m in re.findall(r"\[(\d+)\]", prompt)]
            if not sent_indices:
                sent_indices = [int(m) for m in re.findall(r"Sentence\s*ID\s*(\d+)", prompt, re.IGNORECASE)]
            if sent_indices:
                sample_labels = ["Claim", "Evidence", "Definition", "Method", "Result", "Problem", "Solution", None]
                return {
                    "classifications": [
                        {
                            "idx": idx,
                            "label": sample_labels[idx % len(sample_labels)],
                        }
                        for idx in sent_indices
                    ]
                }

        # Check if prompt is batched format with Candidate IDs
        cand_ids = [int(m) for m in re.findall(r"Candidate ID\s*(\d+)", prompt)]
        if not cand_ids:
            cand_ids = [int(m) for m in re.findall(r"candidate_id[\"']?\s*:\s*(\d+)", prompt)]

        if cand_ids:
            return {
                "relations": [
                    {
                        "candidate_id": cid,
                        "type": self.default_type,
                        "direction": "forward",
                        "reason": "Automated relationship inference by LLM analysis",
                    }
                    for cid in cand_ids
                ]
            }

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

        # Scan messages for citation IDs [s...], [a...], [r...]
        combined = " ".join(m.get("content", "") for m in messages)
        # Search for context section if present to avoid capturing prompt instruction examples ([s1], [a2], [r3])
        context_match = re.search(r"===\s*(?:Global Corpus )?Context.*?===\s*(.*)", combined, re.DOTALL)
        search_target = context_match.group(1) if context_match else combined

        raw_ids = re.findall(r"\[([sar]\d+)\]", search_target)

        # Keep ordered unique IDs
        unique_ids = list(dict.fromkeys(raw_ids))

        if not unique_ids:
            return "Based on the provided document, I could not find information regarding this question."

        cited_str = " ".join(f"[{cid}]" for cid in unique_ids[:3])

        snippets = []
        for cid in unique_ids[:3]:
            pattern = re.escape(f"[{cid}]") + r"\s*([^\n\r]+)"
            match = re.search(pattern, search_target)
            if match:
                snippet = match.group(1).strip()
                snippets.append(f"{snippet} [{cid}]")
            else:
                snippets.append(f"[{cid}]")

        evidence_summary = " Furthermore, ".join(snippets) if snippets else cited_str
        return f"According to the document text and annotations, the answer is confirmed by {cited_str}: {evidence_summary}"


def _extract_json_object(content: str) -> Any:
    """Parse JSON object or array from text, handling markdown fences, trailing text, and extra braces."""
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
        idx_brace = trimmed.find("{")
        idx_sq = trimmed.find("[")
        if idx_brace != -1 and (idx_sq == -1 or idx_brace < idx_sq):
            idx = idx_brace
            match_pattern = r"\{.*\}"
        elif idx_sq != -1:
            idx = idx_sq
            match_pattern = r"\[.*\]"
        else:
            raise

        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(trimmed[idx:])
            if isinstance(obj, (dict, list)):
                return obj
        except Exception:
            pass

        match = re.search(match_pattern, trimmed, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


class OpenAILLMClient(BaseLLMClient):
    """OpenAI API client implementation."""

    def __init__(
        self,
        endpoint: str = "https://api.openai.com/v1/chat/completions",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.llm_api_key
        if not self.api_key:
            raise LLMNotConfiguredError("LLM API key is not configured in settings")
        self.model = model or settings.llm_model
        self.endpoint = endpoint
        self.timeout = settings.llm_timeout_seconds
        self.extra_headers = extra_headers or {}
        self._semaphore = threading.Semaphore(settings.llm_max_concurrency)

    def _get_headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }
        if extra:
            headers.update(extra)
        return headers

    def _post_with_retry(self, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> httpx.Response:
        """Execute HTTP post with transient error retry."""
        import time

        req_headers = headers if headers is not None else self._get_headers()
        max_attempts = 3
        last_err = None
        for attempt in range(max_attempts):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(self.endpoint, json=payload, headers=req_headers)
                    if resp.status_code == 400 and "response_format" in resp.text:
                        p2 = dict(payload)
                        p2.pop("response_format", None)
                        resp = client.post(self.endpoint, json=p2, headers=req_headers)
                    resp.raise_for_status()
                    return resp
            except Exception as exc:
                last_err = exc
                if attempt < max_attempts - 1:
                    time.sleep(0.6 * (attempt + 1))
                else:
                    raise last_err

    def complete_json(self, prompt: str) -> Dict[str, Any]:
        """Call chat completion API expecting JSON response."""
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
        payload = {
            "model": self.model,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": 512,
        }

        with self._semaphore:
            headers = self._get_headers()
            resp = self._post_with_retry(payload, headers)
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return _extract_json_object(content)

    def complete(self, messages: List[Dict[str, str]]) -> str:
        """Call chat completions API expecting plain text response."""
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 1024,
        }

        with self._semaphore:
            headers = self._get_headers()
            resp = self._post_with_retry(payload, headers)
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()


class HuggingFaceLLMClient(BaseLLMClient):
    """Hugging Face Serverless Inference client using official huggingface_hub."""

    DEFAULT_MODEL = "meta-llama/Llama-3.1-8B-Instruct"

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


class OpenRouterLLMClient(OpenAILLMClient):
    """OpenRouter API client implementation using standard OpenAI-compatible endpoints."""

    def __init__(self) -> None:
        settings = get_settings()
        api_key = settings.openrouter_key or settings.llm_api_key
        if not api_key:
            raise LLMNotConfiguredError(
                "OpenRouter API key is not configured. Set OPENROUTER_KEY or LLM_API_KEY in your environment."
            )
        super().__init__(
            endpoint=settings.openrouter_endpoint,
            api_key=api_key,
            model=settings.llm_model or "meta-llama/llama-3.1-8b-instruct",
            extra_headers={
                "HTTP-Referer": "https://github.com/documesh",
                "X-Title": "DocuMesh",
            },
        )


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

    if provider in ("openrouter", "open_router"):
        return OpenRouterLLMClient()

    if provider in ("huggingface", "hf"):
        return HuggingFaceLLMClient()

    if provider == "openai":
        return OpenAILLMClient()

    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def set_shared_llm_client(client: Optional[BaseLLMClient]) -> None:
    """Explicitly override LLM client instance (for test mocking)."""
    global _shared_llm_client
    _shared_llm_client = client
