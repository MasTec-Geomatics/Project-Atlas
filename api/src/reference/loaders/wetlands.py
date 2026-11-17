"""USFWS National Wetlands Inventory loader (issue #70).

Source page: https://www.fws.gov/program/national-wetlands-inventory/download-state-wetlands-data

Attributes:
    SOURCES: State code to the USFWS state GeoPackage download.
    COLUMNS: ``hydro.wetlands`` column to NWI source field (lowercased by ``ogr2ogr``).
    WETLAND_TYPES: The NWI ``WETLAND_TYPE`` values that are wetlands. NWI also maps open
        water (for example ``Freshwater Pond``, ``Lake``, ``Riverine`` and ``Estuarine and
        Marine Deepwater``); only the values listed here are loaded.
"""

from sqlalchemy import Engine

from src.reference.load import LayerSource, run_load
from src.reference.models.hydro import Wetland

SOURCES = {
    "TX": "https://documentst.ecosphere.fws.gov/wetlands/data/State-Downloads/TX_geopackage_wetlands.zip",
}

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


def load_wetlands(engine: Engine) -> None:
    """Load NWI wetlands, without open water, into ``hydro.wetlands`` for each state.

    Args:
        engine: Engine for the reference database.
    """
    for state, url in SOURCES.items():
        source = LayerSource(
            model=Wetland,
            state=state,
            url=url,
            source_layer=f"{state}_Wetlands",
            file_suffix=".gpkg",
            columns=COLUMNS,
            keep={"wetland_type": WETLAND_TYPES},
        )
        run_load(engine, source)
