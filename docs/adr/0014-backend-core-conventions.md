# 0014. Backend Core Conventions

**Status:** Accepted
**Date:** 2026-11-09

## Decision

### Settings

- Settings load from environment variables and the repository `.env` using `python-dotenv` and a Pydantic `BaseModel` in `src/core/config.py`.
- Secrets use `SecretStr` so they do not appear in logs or errors.

### Logging

- Use structlog on top of Python's standard `logging`.
- Development output is readable console logs, with Rich-formatted tracebacks.
- Production output is one JSON object per log line, with structured tracebacks.
- Uvicorn and SQLAlchemy logs use the same output.

### Request ID

- Every request gets an ID, returned in the `X-Request-ID` response header.
- The ID is attached to every log line written during that request.

### Error Handling

- Application exceptions live in `src/core/errors.py`.
- Exception handlers return one consistent JSON error shape.
- Unhandled exceptions are logged with the full traceback and request ID. The client receives a generic error with the request ID.

### Health Checks

- `GET /api/health`: the process is running.
- `GET /api/ready`: the database is reachable.

### Error Tracking

- Sentry is used in production and wired in as needed.
