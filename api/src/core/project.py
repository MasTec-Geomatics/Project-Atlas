"""Project name and version, read from ``pyproject.toml``."""

import tomllib
from pathlib import Path

# api/src/core/project.py -> api/, where pyproject.toml lives.
API_ROOT = Path(__file__).resolve().parents[2]


def _read_project() -> tuple[str, str]:
    """Read the project name and version from ``pyproject.toml``.

    Returns:
        The ``name`` and ``version`` values from the ``[project]`` table.
    """
    with (API_ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)["project"]
    return str(project["name"]), str(project["version"])


PROJECT_NAME, PROJECT_VERSION = _read_project()
