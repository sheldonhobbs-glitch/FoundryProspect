# Ember architecture

Ember's goal is to reduce household admin: people say what happened or ask a
question, and Ember works out which part of the household it concerns, looks
things up or acts, and replies in a sentence. The modules (bills, calendar,
meals, …) are capabilities the Ember Brain operates, not the main product
surface.

```
PWA (composer, digest, screens)          future SwiftUI app / voice / Shortcuts
            │                                         │
            └──────────── FastAPI (api/) ─────────────┘
                              │
            ┌─────────────────┴─────────────────┐
     HTTP routes                         Ember Brain (brain/)
     (screens)                   orchestrator → tool registry → provider
            │                                   │
            └──────────── domain/ ──────────────┘
                              │
                 PostgreSQL · Google Calendar (adapter) · worker
```

## Layers

**`domain/`** holds all household business logic (recurring bills rolling
forward, maintenance intervals, meal-plan upserts, calendar writes, shopping
list, reminders). Functions take a `Session`, flush, and leave committing to
the caller. Routes, the worker, and Brain tools all call these same functions
— there is one implementation of each household action.

**`brain/provider/`** — `AIProvider` is the only place that knows about a model
vendor. The boundary is one model turn: messages + tool specs in, a
normalised `ModelTurn` out. The orchestrator owns the loop, so tools and
domain code never touch vendor types. `AnthropicProvider` is the current
implementation; another vendor means another class, not a rewrite.

**`brain/tools/`** — the capability registry. A `Tool` is a Pydantic input
model, a handler that calls `domain/`, and a **risk level set in code**:

| Risk | Behaviour | Examples |
|---|---|---|
| `read` | runs immediately | list bills, what's on, pantry |
| `low` | runs immediately, reported back | add to shopping list, mark bill paid, set a meal, create a reminder |
| `confirm` | held as a `PendingAction` until a person taps Confirm | cancel a subscription, move or delete a calendar event |

Adding a capability means adding a `Tool` in `brain/tools/catalog/`; gating,
validation and tracing apply automatically.

**`brain/orchestrator.py`** — the request loop (at most 6 model rounds):
every tool call is validated against its input model before anything runs;
invalid input goes back to the model as an error. Read/low tools each run in
their own transaction and roll back on failure. Confirm tools store the
validated input; approving executes exactly that input without consulting
the model again. Refused or truncated model turns never run their tools.

## Key decisions

- **Intelligence is server-side.** API keys never reach the browser; any
  client (PWA today, native app later, voice later) calls the same
  `/api/ember/message`.
- **The model proposes, the application decides.** Risk levels, validation,
  confirmation and limits are enforced in code, not by prompt.
- **Input validation in code, not strict tool schemas.** The API caps strict
  schemas at 20 tools / 24 optional parameters in total, which the household
  catalog exceeds; Pydantic validation covers the same ground.
- **Append-only conversations.** History is stored in the provider's native
  shape and replayed verbatim (editing earlier turns would invalidate the
  model's reasoning blocks). Conversations idle for 30 minutes or longer than
  20 turns end and a new one starts, rather than being trimmed. Messages are
  retained for context; they are not needed long-term.
- **Stable prompt prefix.** The system prompt and tool list are byte-identical
  between requests (tools sorted, no dates in the prompt) so they're cached;
  the date/time and speaker go in each user message.
- **One household clock.** The server runs in UTC; "today" is always computed
  in `HOUSEHOLD_TIMEZONE`, on the server and (via `/api/today`) in the browser.
- **Traces without content.** `ember_traces` records tool names, outcomes,
  rounds, tokens and latency per request — never message text.
- **Calendar writes are off by default** until a dedicated household calendar
  is connected, so the assistant can't write to a personal/work calendar.
- **Identity is attribution, not auth (for now).** The shared magic link is
  the login; the Sheldon/Partner picker only attributes votes, reminders and
  conversations. Individual accounts are planned (Phase 2/6).

## Known limits (Phase 1)

- No household memory yet: Ember doesn't know people, pets, vehicles or
  preferences beyond what's in records (Phase 2).
- No photo/document capture (Phase 3); no proactive briefing or push (Phase 4).
- Member names are a stopgap mapping in `domain/household.py`.
- Brain replies are not streamed; a request takes a few seconds.
