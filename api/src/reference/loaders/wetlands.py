"""USFWS National Wetlands Inventory loader (issue #70).

Source page: https://www.fws.gov/program/national-wetlands-inventory/download-state-wetlands-data

Download links are kept in ``public.sources`` as layer ``hydro.wetlands``, one row per
state, with format ``gpkg`` for the USFWS state GeoPackage downloads.

Attributes:
    COLUMNS: ``hydro.wetlands`` column to NWI source field (lowercased by ``ogr2ogr``).
    WETLAND_TYPES: The NWI ``WETLAND_TYPE`` values that are wetlands. NWI also maps open
        water (for example ``Freshwater Pond``, ``Lake``, ``Riverine`` and ``Estuarine and
        Marine Deepwater``); only the values listed here are loaded.
    LOADER: The wetlands loader, registered in ``src/reference/loaders/__init__.py``.
"""

from src.reference.load import LayerSource, Loader
from src.reference.models.hydro import Wetland
from src.reference.models.public import Source

COLUMNS = {
    "cowardin_code": "attribute",  # NWI ATTRIBUTE: the Cowardin classification code
    "wetland_type": "wetland_type",  # NWI WETLAND_TYPE
    "acres": "acres",  # NWI ACRES
}

WETLAND_TYPES = (
    "Freshwater Emergent Wetland",
    "Freshwater Forested/Shrub Wetland",
    "Estuarine and Marine Wetland",
)


def layer_source(source: Source) -> LayerSource:
    """Build the wetlands load for one state's ``public.sources`` row.

    Args:
        source: The ``hydro.wetlands`` row for one state.

    Returns:
        The load for that state, without open water.
    """
    return LayerSource(
        model=Wetland,
        state=source.state,
        url=source.download_url,
        source_layer=f"{source.state}_Wetlands",
        file_suffix=f".{source.format}",
        columns=COLUMNS,
        keep={"wetland_type": WETLAND_TYPES},
    )


LOADER = Loader(model=Wetland, layer_source=layer_source)
