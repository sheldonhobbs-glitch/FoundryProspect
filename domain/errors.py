class DomainError(Exception):
    """A household-level problem a caller should surface as a clean message
    (not found, not allowed, integration unavailable) rather than a crash."""


class NotFound(DomainError):
    pass


class IntegrationError(DomainError):
    """An external service (e.g. Google Calendar) failed or isn't connected."""
