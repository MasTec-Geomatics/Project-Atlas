"""USFWS National Wetlands Inventory loader (issue #70).

Source page: https://www.fws.gov/program/national-wetlands-inventory/download-state-wetlands-data

Attributes:
    SOURCES: State code to the USFWS state GeoPackage download.
    COLUMNS: ``hydro.wetlands`` column to NWI source field (lowercased by ``ogr2ogr``).
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


def load_wetlands(engine: Engine) -> None:
    """Load NWI wetland polygons into ``hydro.wetlands`` for each state in ``SOURCES``.

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
        )
        run_load(engine, source)
