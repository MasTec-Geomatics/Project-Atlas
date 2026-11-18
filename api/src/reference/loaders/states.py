"""Census TIGER/Line states loader (ADR 0021).

Source: the national state file, for example
https://www2.census.gov/geo/tiger/TIGER2026/STATE/tl_2026_us_state.zip

Each ``public.sources`` row for ``boundaries.states`` points at the national file. A load
keeps only the row whose ``STUSPS`` matches the source's state.

Attributes:
    COLUMNS: ``boundaries.states`` column to TIGER/Line field (lowercased by ``ogr2ogr``).
    LOADER: The states loader, registered in ``src/reference/loaders/__init__.py``.
"""

from src.reference.load import LayerSource, Loader
from src.reference.models.boundaries import State
from src.reference.models.public import Source

COLUMNS = {
    "name": "name",  # TIGER NAME, e.g. Texas
}


def layer_source(source: Source) -> LayerSource:
    """Build the states load for one state's ``public.sources`` row.

    Args:
        source: The ``boundaries.states`` row for one state.

    Returns:
        The load for that state's outline.
    """
    return LayerSource(
        model=State,
        state=source.state,
        url=source.download_url,
        file_suffix=f".{source.format}",
        columns=COLUMNS,
        keep={"stusps": (source.state,)},  # TIGER STUSPS, e.g. TX
    )


LOADER = Loader(model=State, layer_source=layer_source)
