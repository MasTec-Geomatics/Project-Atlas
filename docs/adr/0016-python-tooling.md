# 0016. Python Development Tooling

**Status:** Accepted
**Date:** 2026-11-09

## Decision

| Purpose            | Tool                                    |
| ------------------ | --------------------------------------- |
| Lint and format    | ruff                                    |
| Type checking      | mypy, with the Pydantic plugin          |
| Tests              | pytest + httpx                          |
| Task runner        | mise tasks                              |

- All tool configuration lives in `api/pyproject.toml`.
- Tests run against the local PostGIS pod.
- Checks run the same from VS Code, PyCharm, or the terminal.
