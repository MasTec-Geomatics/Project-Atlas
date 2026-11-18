"""Census TIGER/Line counties loader (ADR 0021).

Source: the national county file, for example
https://www2.census.gov/geo/tiger/TIGER2026/COUNTY/tl_2026_us_county.zip

Each ``public.sources`` row for ``boundaries.counties`` points at the national file. A
load keeps only the counties whose ``STATEFP`` matches the source's state.

Attributes:
    COLUMNS: ``boundaries.counties`` column to TIGER/Line field (lowercased by ``ogr2ogr``).
    LOADER: The counties loader, registered in ``src/reference/loaders/__init__.py``.
"""

from src.reference.load import LayerSource, Loader
from src.reference.models.boundaries import County
from src.reference.models.public import Source
from src.reference.state_codes import STATE_FIPS

COLUMNS = {
    "geoid": "geoid",  # TIGER GEOID: state FIPS + county FIPS, e.g. 48453
    "name": "name",  # TIGER NAME, e.g. Travis
}


def layer_source(source: Source) -> LayerSource:
    """Build the counties load for one state's ``public.sources`` row.

    Args:
        source: The ``boundaries.counties`` row for one state.

    Returns:
        The load for that state's counties.
    """
    return LayerSource(
        model=County,
        state=source.state,
        url=source.download_url,
        file_suffix=f".{source.format}",
        columns=COLUMNS,
        keep={"statefp": (STATE_FIPS[source.state],)},  # TIGER STATEFP, e.g. 48
    )


LOADER = Loader(model=County, layer_source=layer_source)
