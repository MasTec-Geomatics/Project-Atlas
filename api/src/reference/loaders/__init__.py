"""Reference layer loaders, one module per layer (ADR 0018).

Attributes:
    LOADERS: Layer name, as used in the API route, to its loader.
"""

from src.reference.load import Loader
from src.reference.loaders import wetlands

LOADERS: dict[str, Loader] = {
    "wetlands": wetlands.LOADER,
}
