"""Who's in the household. Stopgap until household members become real
records in Phase 2 — this is the only place display names should live."""

MEMBERS = {"sheldon": "Sheldon", "partner": "Partner"}


def member_name(key: str | None) -> str:
    return MEMBERS.get(key or "", "someone in the household")
