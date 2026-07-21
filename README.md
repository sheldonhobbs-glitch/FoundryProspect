# Ember

Household management for two. Not a multi-tenant product — one shared login,
one household, no roles.

## Phase 0: local dev

1. Copy the env template and fill in the required values:

   ```
   cp .env.example .env
   python -c "import secrets; print(secrets.token_hex(32))"     # -> SECRET_KEY
   python -c "import secrets; print(secrets.token_urlsafe(32))" # -> HOUSEHOLD_LOGIN_TOKEN
   ```

   Set `SECRET_KEY` and `HOUSEHOLD_LOGIN_TOKEN` in `.env` from the output
   above. Leave the Phase 2+ keys (Google, Anthropic, VAPID) blank for now.

2. Start everything:

   ```
   docker compose up --build
   ```

   This starts Postgres, runs Alembic migrations (currently a no-op — no
   domain tables yet), then starts the API on `http://localhost:8000` and
   the worker process.

3. Check it's alive:

   ```
   curl http://localhost:8000/api/health
   ```

   Then log in by opening `http://localhost:8000/login/<HOUSEHOLD_LOGIN_TOKEN>`
   in a browser — there's no username or password. Bookmark that URL (or add
   it to your home screen) on both of your phones; that bookmark is the login.

## Structure

- `api/` — FastAPI app: routes, auth, config
- `worker/` — background job process (separate from the request/response cycle)
- `db/` — SQLAlchemy models + Alembic migrations
- `frontend/` — PWA: plain HTML/CSS/JS, chat-style shell
