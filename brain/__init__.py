"""The Ember Brain: natural-language requests in, tool calls against the
household domain out. Layers, top to bottom:

    orchestrator  — the request loop, confirmation gating, tracing
    tools         — the capability registry; each tool declares its own risk
    provider      — the model vendor adapter (Anthropic today)

The domain/ package underneath knows nothing about any of this."""
