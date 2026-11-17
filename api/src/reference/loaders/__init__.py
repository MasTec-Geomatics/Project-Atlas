"""Reference layer loaders, one module per layer (ADR 0018).

Attributes:
    LOADERS: Layer name, as typed on the command line, to its loader function.
"""

from collections.abc import Callable

from sqlalchemy import Engine

from src.reference.loaders.wetlands import load_wetlands

LOADERS: dict[str, Callable[[Engine], None]] = {
    "wetlands": load_wetlands,
}
