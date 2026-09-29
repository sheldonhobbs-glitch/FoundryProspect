"""Test setup. Runs against a real Postgres test database (default
ember_test on localhost) so migrations, JSONB and constraints behave exactly
as in production. Each test runs inside a transaction that's rolled back;
code under test can commit/rollback freely (those become savepoints)."""

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://ember:ember@localhost:5432/ember_test"
)
os.environ["ANTHROPIC_API_KEY"] = ""  # tests must never reach a real model
os.environ["HOUSEHOLD_LOGIN_TOKEN"] = "test-login-token"
os.environ["SECRET_KEY"] = "test-secret-key"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from db.session import engine  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture
def db():
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()
