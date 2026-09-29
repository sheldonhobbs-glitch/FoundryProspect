"""Ember's domain layer: household business logic shared by the HTTP routes,
the background worker, and the Ember Brain's tools. Functions here take a
Session, mutate/flush, and leave committing to the caller, so a caller can
wrap one or more operations in a single transaction."""
