"""Wiring: builds the configured provider and the tool registry once per
process. The only place that knows which vendor is in use."""

from functools import lru_cache

from api.config import get_settings
from brain.provider import AIProvider
from brain.provider.anthropic import AnthropicProvider
from brain.tools import ToolRegistry
from brain.tools.catalog import build_registry


@lru_cache
def get_registry() -> ToolRegistry:
    return build_registry()


def get_provider() -> AIProvider | None:
    """None when no API key is configured — the Brain is then unavailable
    but the rest of Ember works normally."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    return _anthropic(settings.anthropic_api_key, settings.ember_model, settings.ember_effort)


@lru_cache
def _anthropic(api_key: str, model: str, effort: str) -> AnthropicProvider:
    return AnthropicProvider(api_key=api_key, model=model, effort=effort)
