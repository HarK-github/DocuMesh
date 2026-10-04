"""Unit tests for Hugging Face serverless inference LLM client."""

import json
import pytest
from unittest.mock import MagicMock

from backend.app.settings import get_settings
from backend.app.services.llm import (
    HuggingFaceLLMClient,
    LLMNotConfiguredError,
    get_llm_client,
    set_shared_llm_client,
    _extract_json_object,
)


def test_extract_json_object_variants():
    """Verify JSON extractor handles raw JSON, code fences, trailing text, and extra braces."""
    # Plain JSON
    assert _extract_json_object('{"type": "supports", "reason": "ok"}') == {
        "type": "supports",
        "reason": "ok",
    }

    # Markdown fenced JSON with json tag
    fenced_tag = '```json\n{"type": "defines", "reason": "glossary"}\n```'
    assert _extract_json_object(fenced_tag) == {"type": "defines", "reason": "glossary"}

    # Markdown fenced JSON without tag
    fenced_raw = '```\n{"type": "refutes", "reason": "counterexample"}\n```'
    assert _extract_json_object(fenced_raw) == {"type": "refutes", "reason": "counterexample"}

    # Text before or after
    surrounded = 'Here is the relation:\n{"type": "similar_to", "reason": "shared topic"}\nHope this helps!'
    assert _extract_json_object(surrounded) == {"type": "similar_to", "reason": "shared topic"}

    # Extra trailing brace (common with small LLMs)
    trailing_brace = '{"type": "supports", "reason": "valid proposition"}}'
    assert _extract_json_object(trailing_brace) == {
        "type": "supports",
        "reason": "valid proposition",
    }

    # Invalid JSON
    with pytest.raises(json.JSONDecodeError):
        _extract_json_object("Definitely not json at all")


def test_hf_client_requires_token(monkeypatch):
    """Verify HuggingFaceLLMClient raises LLMNotConfiguredError when token is missing."""
    monkeypatch.setenv("HF_TOKEN", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    get_settings.cache_clear()

    with pytest.raises(LLMNotConfiguredError, match="Hugging Face token is not configured"):
        HuggingFaceLLMClient()


def test_hf_client_initialization_defaults_and_overrides(monkeypatch):
    """Verify HuggingFaceLLMClient defaults to 1B instruct model or respects overrides."""
    # Default model
    monkeypatch.setenv("HF_TOKEN", "hf_testtoken123")
    monkeypatch.setenv("LLM_MODEL", "gpt-4o-mini")  # default openai model should get mapped to HF default
    get_settings.cache_clear()

    client = HuggingFaceLLMClient()
    assert client.api_key == "hf_testtoken123"
    assert client.model == "meta-llama/Llama-3.2-1B-Instruct"

    # Custom model
    monkeypatch.setenv("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
    get_settings.cache_clear()

    client_custom = HuggingFaceLLMClient()
    assert client_custom.model == "Qwen/Qwen2.5-1.5B-Instruct"


def test_hf_client_fallback_to_llm_api_key(monkeypatch):
    """Verify HuggingFaceLLMClient uses LLM_API_KEY if HF_TOKEN is empty."""
    monkeypatch.setenv("HF_TOKEN", "")
    monkeypatch.setenv("LLM_API_KEY", "hf_fallback_key")
    get_settings.cache_clear()

    client = HuggingFaceLLMClient()
    assert client.api_key == "hf_fallback_key"


def test_hf_client_complete_json(monkeypatch):
    """Verify complete_json sends expected payload to router and parses response."""
    monkeypatch.setenv("HF_TOKEN", "hf_mocktoken")
    monkeypatch.setenv("LLM_MODEL", "meta-llama/Llama-3.2-1B-Instruct")
    get_settings.cache_clear()

    client = HuggingFaceLLMClient()

    mock_choice = MagicMock()
    mock_choice.message.content = '```json\n{"type": "supports", "reason": "Empirical evidence validates hypothesis"}\n```'
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_internal_client = MagicMock()
    mock_internal_client.chat.completions.create.return_value = mock_resp
    client._client = mock_internal_client

    result = client.complete_json("Analyze relationship between A and B")

    assert result == {
        "type": "supports",
        "reason": "Empirical evidence validates hypothesis",
    }
    mock_internal_client.chat.completions.create.assert_called_once()
    kwargs = mock_internal_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "meta-llama/Llama-3.2-1B-Instruct"
    assert kwargs["temperature"] == 0.0


def test_hf_client_complete(monkeypatch):
    """Verify complete sends chat messages and extracts text response."""
    monkeypatch.setenv("HF_TOKEN", "hf_mocktoken")
    monkeypatch.setenv("LLM_MODEL", "meta-llama/Llama-3.2-1B-Instruct")
    get_settings.cache_clear()

    client = HuggingFaceLLMClient()

    mock_choice = MagicMock()
    mock_choice.message.content = "Machines can simulate discrete state machines as proven in [s1]."
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_internal_client = MagicMock()
    mock_internal_client.chat.completions.create.return_value = mock_resp
    client._client = mock_internal_client

    messages = [
        {"role": "system", "content": "Context with [s1]"},
        {"role": "user", "content": "Can machines think?"},
    ]
    answer = client.complete(messages)

    assert answer == "Machines can simulate discrete state machines as proven in [s1]."
    mock_internal_client.chat.completions.create.assert_called_once()
    kwargs = mock_internal_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "meta-llama/Llama-3.2-1B-Instruct"
    assert kwargs["messages"] == messages


def test_get_llm_client_hf_provider(monkeypatch):
    """Verify get_llm_client returns HuggingFaceLLMClient when configured."""
    set_shared_llm_client(None)
    monkeypatch.setenv("LLM_PROVIDER", "huggingface")
    monkeypatch.setenv("HF_TOKEN", "hf_provider_token")
    get_settings.cache_clear()

    client = get_llm_client()
    assert isinstance(client, HuggingFaceLLMClient)

    # Test "hf" shorthand
    set_shared_llm_client(None)
    monkeypatch.setenv("LLM_PROVIDER", "hf")
    get_settings.cache_clear()

    client_short = get_llm_client()
    assert isinstance(client_short, HuggingFaceLLMClient)

    set_shared_llm_client(None)
