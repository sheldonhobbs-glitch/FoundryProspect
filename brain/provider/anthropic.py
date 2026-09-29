import logging

import anthropic

from brain.provider.base import ModelTurn, ProviderError, ToolCall, ToolResult, ToolSpec

logger = logging.getLogger("ember.brain.anthropic")

# Short replies and small tool inputs; well under the non-streaming ceiling.
MAX_TOKENS = 8000
# Server-side refusal fallback: an over-cautious decline is retried on another
# model inside the same call instead of failing the household's request.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

_STOP_MAP = {"end_turn": "end_turn", "tool_use": "tool_use", "max_tokens": "max_tokens", "refusal": "refusal"}


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, effort: str = "low", timeout: float = 60.0):
        self._client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=2)
        self._model = model
        self._effort = effort

    def run_turn(self, *, system: str, messages: list[dict], tools: list[ToolSpec]) -> ModelTurn:
        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
                tools=[
                    {"name": t.name, "description": t.description, "input_schema": t.input_schema}
                    for t in tools
                ],
                output_config={"effort": self._effort},
                # Caches the stable prefix (tools + system + earlier turns).
                cache_control={"type": "ephemeral"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.AuthenticationError as exc:
            logger.error("Anthropic authentication failed — check ANTHROPIC_API_KEY")
            raise ProviderError("The AI service rejected Ember's API key.") from exc
        except anthropic.RateLimitError as exc:
            logger.warning("Anthropic rate limited the request")
            raise ProviderError("The AI service is busy right now. Try again in a minute.") from exc
        except anthropic.APIStatusError as exc:
            logger.error("Anthropic API error: status=%s request_id=%s", exc.status_code, exc.request_id)
            raise ProviderError("The AI service returned an error.") from exc
        except anthropic.APIConnectionError as exc:
            logger.error("Could not reach the Anthropic API: %s", type(exc).__name__)
            raise ProviderError("Couldn't reach the AI service.") from exc

        usage = response.usage
        return ModelTurn(
            stop=_STOP_MAP.get(response.stop_reason, "other"),
            text="".join(b.text for b in response.content if b.type == "text").strip(),
            tool_calls=[
                ToolCall(id=b.id, name=b.name, input=dict(b.input))
                for b in response.content if b.type == "tool_use"
            ],
            # Stored and replayed verbatim — thinking blocks must round-trip
            # unchanged or later turns lose them.
            raw_content=[b.to_dict(mode="json") for b in response.content],
            model=response.model,
            input_tokens=usage.input_tokens or 0,
            output_tokens=usage.output_tokens or 0,
            cache_read_tokens=usage.cache_read_input_tokens or 0,
        )

    def user_text_message(self, text: str) -> dict:
        return {"role": "user", "content": [{"type": "text", "text": text}]}

    def assistant_message(self, turn: ModelTurn) -> dict:
        return {"role": "assistant", "content": turn.raw_content}

    def tool_results_message(self, results: list[ToolResult]) -> dict:
        return {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content, "is_error": r.is_error}
                for r in results
            ],
        }
