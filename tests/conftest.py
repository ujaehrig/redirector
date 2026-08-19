"""Shared test fixtures and constants."""

INSERT_REDIRECT_SQL = (
    "INSERT INTO redirects"
    " (short_code, destination_url, status_code,"
    " created_at, enabled)"
    " VALUES (?, ?, ?, ?, ?)"
)
