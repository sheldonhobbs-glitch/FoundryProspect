# Ember

Household management for two. Not a multi-tenant product — one shared login,
one household, no roles.

## Phase 0: local dev

1. Copy the env template and fill in the required values:

   ```
   cp .env.example .env
   python -c "import secrets; print(secrets.token_hex(32))"   # -> SECRET_KEY
   pip install passlib[bcrypt]  # if not already installed locally
   python scripts/hash_password.py "your-chosen-password"     # -> HOUSEHOLD_PASSWORD_HASH
   ```

   Set `HOUSEHOLD_USERNAME` and `HOUSEHOLD_PASSWORD_HASH` in `.env` from the
   output above. Leave the Phase 2+ keys (Google, Anthropic, VAPID) blank for
   now.

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

   Then open `http://localhost:8000` in a browser and log in with the
   username/password you set in `.env`.

## Structure

- `api/` — FastAPI app: routes, auth, config
- `worker/` — background job process (separate from the request/response cycle)
- `db/` — SQLAlchemy models + Alembic migrations
- `frontend/` — PWA: plain HTML/CSS/JS, chat-style shell
