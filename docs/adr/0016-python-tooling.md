# 0016. Python Development Tooling

**Status:** Accepted
**Date:** 2026-11-09
**Updated:** 2026-11-17

## Decision

| Purpose         | Tool                           |
| --------------- | ------------------------------ |
| Lint and format | ruff                           |
| Type checking   | mypy, with the Pydantic plugin |
| Tests           | pytest + httpx                 |
| Task runner     | just                           |

- All tool configuration lives in `api/pyproject.toml`.
- Checks run the same from VS Code, PyCharm, or the terminal.

### Python Version

- Development runs on Python 3.15 (`api/.python-version`).
- Python 3.14 is still supported: `requires-python = ">=3.14"`, and mypy checks against 3.14 (`python_version = "3.14"`).

### Test Databases

- Tests never run against the `atlas` or `reference` databases, and no test database is kept next to them.
- When a test run starts, pytest creates a temporary database (`reference_test`) on the same server as `REFERENCE_DATABASE_URL` and migrates it to head.
- When the run ends, pytest drops it.

## Consequences

- The local PostgreSQL pod must be running for tests that use the database.
- The login in `REFERENCE_DATABASE_URL` must be allowed to create and drop databases.
- A test run that is killed partway can leave `reference_test` behind. The next run drops and recreates it.
