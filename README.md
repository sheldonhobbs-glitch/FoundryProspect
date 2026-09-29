# Ember

An intelligent operating system for our home: it keeps household
information organised and lets us manage it by just saying what happened —
"the electricity bill is paid", "add milk and bread", "what's on tomorrow?".

FastAPI + PostgreSQL backend, a background worker, and a plain HTML/CSS/JS
PWA. All AI runs server-side. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
for how the pieces fit together and why.

## Structure

| Path | What it is |
|---|---|
| `api/` | FastAPI app: HTTP routes, auth, config, Google Calendar adapter |
| `brain/` | The Ember Brain: model provider, tool catalog, orchestrator |
| `domain/` | Household business logic shared by routes, worker and Brain |
| `db/` | SQLAlchemy models + Alembic migrations |
| `worker/` | Background process: calendar sync, daily due-date/reminder scan |
| `frontend/` | The PWA |
| `tests/` | pytest suite (real Postgres, scripted model — no API calls) |
| `scripts/ember_live_check.py` | Runs real commands against the live model; reports cost |

## Local development

Requires Python 3.12 and PostgreSQL.

```
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"     # -> SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(32))" # -> HOUSEHOLD_LOGIN_TOKEN
```

Put those in `.env`, point `DATABASE_URL` at a local database, then:

```
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn api.main:app --reload     # web app on :8000 (runs migrations on startup)
.venv/bin/python -m worker.main              # worker, in another terminal
```

Log in by opening `http://localhost:8000/login/<HOUSEHOLD_LOGIN_TOKEN>` — the
bookmarked link *is* the login. Or run everything with `docker compose up --build`.

To use the assistant, set `ANTHROPIC_API_KEY`. Without it the rest of Ember
works normally and the composer says the assistant isn't set up yet.

## Tests

```
createdb ember_test          # once
.venv/bin/pytest
```

Tests use `TEST_DATABASE_URL` (default `postgresql://ember:ember@localhost:5432/ember_test`),
migrate it to head, and roll back every test. The model is replaced by a
scripted fake, so tests are deterministic and free.

To check behaviour against the real model (costs a few cents, uses the test
database and rolls back):

```
ANTHROPIC_API_KEY=... .venv/bin/python -m scripts.ember_live_check
```

## Configuration

All settings are environment variables — see `.env.example`. The ones
specific to the Ember Brain:

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Enables the assistant. Server-side only. |
| `EMBER_MODEL` | `claude-opus-5-5` | Model used by the assistant |
| `EMBER_EFFORT` | `low` | Reasoning effort per request |
| `EMBER_DAILY_REQUEST_LIMIT` | `200` | Cap on assistant requests per day |
| `EMBER_CALENDAR_WRITES_ENABLED` | `false` | Lets the assistant add/change/delete events. Turn on only once `GOOGLE_CALENDAR_ID` is a dedicated household calendar. |
| `HOUSEHOLD_TIMEZONE` | `Australia/Brisbane` | Defines "today" (the server runs in UTC) |

## Deployment (Render)

Two services from this repo: a **web service** (`uvicorn api.main:app --host 0.0.0.0 --port $PORT`)
and a **background worker** (`python -m worker.main`), both with the same
environment variables, plus a Render PostgreSQL database. The web service
runs migrations on startup and refuses to start if they fail, so a broken
deploy leaves the previous version running.
