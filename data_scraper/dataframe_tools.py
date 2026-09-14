"""Utilities for filtering the scraped inventory dataframe."""

from collections.abc import Iterable

import pandas as pd


INVENTORY_COLUMNS = (
    "PRODUCTO",
    "LINEA",
    "SUBLINEA",
    "TIENDA",
    "ALMACEN",
    "CANTIDAD UNITARIA",
    "PRESENTACION",
    "CANT",
    "N° CAJAS",
    "IMPORTE",
)
FILTER_COLUMNS = ("TIENDA", "LINEA", "SUBLINEA", "ALMACEN")


def _as_values(value):
    """Return a filter value as a set, preserving a single string as one value."""
    if value is None:
        return None
    if isinstance(value, str):
        return {value}
    if isinstance(value, Iterable):
        return set(value)
    return {value}


def _validate_inventory_dataframe(dataframe: pd.DataFrame):
    """Ensure the dataframe has the columns produced by the scraper."""
    missing_columns = [
        column for column in INVENTORY_COLUMNS if column not in dataframe.columns
    ]
    if missing_columns:
        raise ValueError(
            "Inventory dataframe is missing columns: "
            + ", ".join(missing_columns)
        )


def filter_inventory_dataframe(
    dataframe: pd.DataFrame,
    tienda,
    linea=None,
    sublinea=None,
    almacen=None,
) -> pd.DataFrame:
    """Filter inventory by required store and optional hierarchy dimensions.

    Each filter accepts a single value or an iterable of values. The input
    dataframe is never modified.
    """
    _validate_inventory_dataframe(dataframe)

    filters = {
        "TIENDA": _as_values(tienda),
        "LINEA": _as_values(linea),
        "SUBLINEA": _as_values(sublinea),
        "ALMACEN": _as_values(almacen),
    }
    if not filters["TIENDA"]:
        raise ValueError("TIENDA is required")

    filtered = dataframe
    for column, values in filters.items():
        if values is not None:
            filtered = filtered[filtered[column].isin(values)]

    return filtered.copy()


def get_filter_options(
    dataframe: pd.DataFrame,
    tienda,
    linea=None,
    sublinea=None,
) -> dict[str, list[str]]:
    """Return available LINEA, SUBLINEA, and ALMACEN values for a store."""
    filtered = filter_inventory_dataframe(
        dataframe,
        tienda=tienda,
        linea=linea,
        sublinea=sublinea,
    )
    return {
        column: sorted(filtered[column].dropna().unique().tolist())
        for column in ("LINEA", "SUBLINEA", "ALMACEN")
    }
