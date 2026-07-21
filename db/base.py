from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Importing here registers each model's table on Base.metadata so that
# Alembic's autogenerate can see them. Add new model modules as phases add them.
from db import models  # noqa: E402,F401
