"""Census TIGER/Line places loader (ADR 0021).

Source: one file per state, for example Texas (state FIPS 48):
https://www2.census.gov/geo/tiger/TIGER2026/PLACE/tl_2026_48_place.zip

Places are cities, towns, villages, and Census designated places. The file holds only
that state's places, so every row is loaded.

Attributes:
    COLUMNS: ``boundaries.places`` column to TIGER/Line field (lowercased by ``ogr2ogr``).
    LOADER: The places loader, registered in ``src/reference/loaders/__init__.py``.
"""

from src.reference.load import LayerSource, Loader
from src.reference.models.boundaries import Place
from src.reference.models.public import Source

COLUMNS = {
    "geoid": "geoid",  # TIGER GEOID: state FIPS + place FIPS, e.g. 4805000
    "name": "name",  # TIGER NAME, e.g. Austin
}


def layer_source(source: Source) -> LayerSource:
    """Build the places load for one state's ``public.sources`` row.

    Args:
        source: The ``boundaries.places`` row for one state.

    Returns:
        The load for that state's places.
    """
    return LayerSource(
        model=Place,
        state=source.state,
        url=source.download_url,
        file_suffix=f".{source.format}",
        columns=COLUMNS,
    )


LOADER = Loader(model=Place, layer_source=layer_source)
