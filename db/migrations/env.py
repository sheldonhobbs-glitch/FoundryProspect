import socket
import sys
from logging.config import fileConfig
from urllib.parse import urlparse

from alembic import context
from sqlalchemy import engine_from_config, pool

from api.config import get_settings
from db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

target_metadata = Base.metadata


def _log(msg: str) -> None:
    print(f"[MIGRATION-DEBUG] {msg}", flush=True)
    sys.stdout.flush()


def _preflight_check(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port or 5432
    _log(f"target host={host} port={port}")
    try:
        _log("resolving DNS...")
        addr = socket.getaddrinfo(host, port)
        _log(f"DNS resolved to: {[a[4] for a in addr]}")
    except Exception as exc:
        _log(f"DNS resolution FAILED: {exc!r}")
        return
    try:
        _log("attempting raw TCP connect (5s timeout)...")
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        _log("raw TCP connect SUCCEEDED")
    except Exception as exc:
        _log(f"raw TCP connect FAILED: {exc!r}")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _log("run_migrations_online: start")
    _preflight_check(settings.database_url)

    _log("building engine...")
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    _log("engine built. opening connection (this is the likely hang point)...")
    with connectable.connect() as connection:
        _log("connection OPENED successfully.")
        context.configure(connection=connection, target_metadata=target_metadata)
        _log("context configured. beginning transaction...")
        with context.begin_transaction():
            _log("transaction begun. running migrations...")
            context.run_migrations()
            _log("migrations complete.")
    _log("run_migrations_online: done")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
