"""Cleaning of the raw DVF data.

Each function applies exactly ONE cleaning decision. That is what makes them
testable in isolation, and what lets us justify every choice separately.

Note on naming: column names stay in French because they come from the DVF
dataset, which is French. Everything the code itself defines is in English.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# The only property types this model handles.
DWELLING_TYPES = frozenset({"Maison", "Appartement"})

# Only arm's length sales reflect a market price.
KEPT_SALE_TYPES = frozenset({"Vente"})

# Domain bounds: below this it is not a real transaction, above it the
# property is exceptional and out of the model's scope.
MIN_PRICE = 10_000.0
MAX_PRICE = 5_000_000.0

MIN_LIVING_AREA = 9.0
MAX_LIVING_AREA = 1000.0


def keep_market_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only the transactions that are genuine market sales."""
    before = len(df)
    result = df[df["nature_mutation"].isin(KEPT_SALE_TYPES)]
    logger.info("keep_market_sales: %d -> %d rows", before, len(result))
    return result


def drop_missing_price(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with no price.

    We never impute a missing target value: the model would learn the value
    we made up instead of reality.
    """
    before = len(df)
    result = df.dropna(subset=["valeur_fonciere"])
    logger.info("drop_missing_price: %d -> %d rows", before, len(result))
    return result


def aggregate_by_sale(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce every sale to a single row.

    One sale can cover several lots (dwelling, parking space, cellar), and DVF
    repeats the total price on each of them. We therefore sum the dwelling
    areas and keep the price only once.
    """
    work = df.copy()
    work["est_logement"] = work["type_local"].isin(DWELLING_TYPES)
    work["surface_logement"] = work["surface_reelle_bati"].where(work["est_logement"])
    work["pieces_logement"] = work["nombre_pieces_principales"].where(work["est_logement"])

    aggregated = work.groupby("id_mutation").agg(
        date_mutation=("date_mutation", "first"),
        prix=("valeur_fonciere", "first"),
        nom_commune=("nom_commune", "first"),
        code_postal=("code_postal", "first"),
        nb_logements=("est_logement", "sum"),
        nb_lots=("id_mutation", "size"),
        surface_bati=("surface_logement", "sum"),
        nb_pieces=("pieces_logement", "sum"),
        surface_terrain=("surface_terrain", "sum"),
        longitude=("longitude", "first"),
        latitude=("latitude", "first"),
    )

    dwellings = work[work["est_logement"]]
    aggregated["type_bien"] = dwellings.groupby("id_mutation")["type_local"].first()

    logger.info("aggregate_by_sale: %d rows -> %d sales", len(df), len(aggregated))
    return aggregated.reset_index()


def keep_single_dwelling(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only sales covering exactly one dwelling.

    A sale bundling two flats has no usable unit price.
    """
    before = len(df)
    result = df[df["nb_logements"] == 1]
    logger.info("keep_single_dwelling: %d -> %d sales", before, len(result))
    return result


def filter_price_range(
    df: pd.DataFrame,
    min_price: float = MIN_PRICE,
    max_price: float = MAX_PRICE,
) -> pd.DataFrame:
    """Drop prices outside the model's scope."""
    before = len(df)
    result = df[df["prix"].between(min_price, max_price)]
    logger.info("filter_price_range: %d -> %d sales", before, len(result))
    return result


def filter_area_range(df: pd.DataFrame) -> pd.DataFrame:
    """Drop zero or implausible living areas."""
    before = len(df)
    result = df[df["surface_bati"].between(MIN_LIVING_AREA, MAX_LIVING_AREA)]
    logger.info("filter_area_range: %d -> %d sales", before, len(result))
    return result


def clean_sales(df: pd.DataFrame) -> pd.DataFrame:
    """Run every cleaning step, in order."""
    return (
        df.pipe(keep_market_sales)
        .pipe(drop_missing_price)
        .pipe(aggregate_by_sale)
        .pipe(keep_single_dwelling)
        .pipe(filter_price_range)
        .pipe(filter_area_range)
        .reset_index(drop=True)
    )
