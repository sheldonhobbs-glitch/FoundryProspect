"""The Anthropic adapter, with the SDK call stubbed out (no network)."""

import pytest
from anthropic.types.beta import BetaMessage

from brain.provider import ProviderError, ToolResult, ToolSpec
from brain.provider.anthropic import FALLBACK_BETA, AnthropicProvider


def _message(content, stop_reason):
    return BetaMessage.model_validate({
        "id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 1200, "output_tokens": 40, "cache_read_input_tokens": 900},
    })


@pytest.fixture
def provider(monkeypatch):
    p = AnthropicProvider(api_key="test", model="claude-opus-5-5", effort="low")
    p.calls = []

    def fake_create(**kwargs):
        p.calls.append(kwargs)
        return p.next_response

    monkeypatch.setattr(p._client.beta.messages, "create", fake_create)
    return p


def test_tool_use_response_is_normalised(provider):
    provider.next_response = _message([
        {"type": "text", "text": "Let me check."},
        {"type": "tool_use", "id": "toolu_1", "name": "list_bills", "input": {"due_within_days": 7}},
    ], "tool_use")

    turn = provider.run_turn(system="sys", messages=[{"role": "user", "content": "hi"}],
                             tools=[ToolSpec("list_bills", "List bills.", {"type": "object", "properties": {}})])

    assert turn.stop == "tool_use"
    assert turn.tool_calls[0].name == "list_bills" and turn.tool_calls[0].input == {"due_within_days": 7}
    assert (turn.input_tokens, turn.output_tokens, turn.cache_read_tokens) == (1200, 40, 900)
    # Raw content is replayable as-is on the next turn.
    assert provider.assistant_message(turn)["content"][1]["type"] == "tool_use"


def test_request_uses_configured_model_effort_caching_and_fallback(provider):
    provider.next_response = _message([{"type": "text", "text": "Hi"}], "end_turn")
    provider.run_turn(system="sys", messages=[], tools=[])

    sent = provider.calls[0]
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_config"] == {"effort": "low"}
    assert sent["cache_control"] == {"type": "ephemeral"}
    assert sent["betas"] == [FALLBACK_BETA] and sent["fallbacks"] == "default"
    assert "tool_choice" not in sent  # forced tool use is rejected on this model


def test_refusal_is_mapped(provider):
    provider.next_response = _message([], "refusal")
    assert provider.run_turn(system="s", messages=[], tools=[]).stop == "refusal"


def test_tool_results_message_shape(provider):
    msg = provider.tool_results_message([ToolResult("toolu_1", "ok"), ToolResult("toolu_2", "bad", True)])
    assert msg["role"] == "user"
    assert [b["is_error"] for b in msg["content"]] == [False, True]


def test_sdk_errors_become_provider_errors(provider, monkeypatch):
    import anthropic

    def boom(**kwargs):
        raise anthropic.APIConnectionError(request=None)

    monkeypatch.setattr(provider._client.beta.messages, "create", boom)
    with pytest.raises(ProviderError):
        provider.run_turn(system="s", messages=[], tools=[])
