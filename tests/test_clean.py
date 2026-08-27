"""Tests for the cleaning pipeline.

We build small dataframes by hand rather than reading the real file: a test
must be fast, reproducible, and independent of any external file. Each test
checks exactly ONE cleaning decision.
"""

import pandas as pd

from dvf.data.clean import (
    aggregate_by_sale,
    clean_sales,
    drop_missing_price,
    filter_price_range,
    keep_market_sales,
    keep_single_dwelling,
)

COLUMNS = [
    "id_mutation",
    "date_mutation",
    "nature_mutation",
    "valeur_fonciere",
    "nom_commune",
    "code_postal",
    "type_local",
    "surface_reelle_bati",
    "nombre_pieces_principales",
    "surface_terrain",
    "longitude",
    "latitude",
]


def make_row(
    sale_id: str,
    nature: str = "Vente",
    price: float | None = 200_000.0,
    local_type: str | None = "Appartement",
    area: float | None = 60.0,
    rooms: float | None = 3.0,
) -> dict[str, object]:
    """Build a plausible DVF row, with sane defaults."""
    return {
        "id_mutation": sale_id,
        "date_mutation": "2024-03-15",
        "nature_mutation": nature,
        "valeur_fonciere": price,
        "nom_commune": "Bordeaux",
        "code_postal": 33000.0,
        "type_local": local_type,
        "surface_reelle_bati": area,
        "nombre_pieces_principales": rooms,
        "surface_terrain": 0.0,
        "longitude": -0.57,
        "latitude": 44.83,
    }


def make_frame(*rows: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(rows), columns=COLUMNS)


def test_keep_market_sales_drops_auctions() -> None:
    df = make_frame(
        make_row("A", nature="Vente"),
        make_row("B", nature="Adjudication"),
        make_row("C", nature="Expropriation"),
    )
    assert list(keep_market_sales(df)["id_mutation"]) == ["A"]


def test_drop_missing_price() -> None:
    df = make_frame(make_row("A"), make_row("B", price=None))
    assert list(drop_missing_price(df)["id_mutation"]) == ["A"]


def test_aggregate_merges_the_lots_of_one_sale() -> None:
    """A flat sold with its parking space: two rows, one single sale."""
    df = make_frame(
        make_row("A", local_type="Appartement", area=60.0, rooms=3.0),
        make_row("A", local_type="Dependance", area=12.0, rooms=0.0),
    )
    result = aggregate_by_sale(df)

    assert len(result) == 1
    assert result.loc[0, "prix"] == 200_000.0
    assert result.loc[0, "nb_lots"] == 2
    assert result.loc[0, "nb_logements"] == 1
    assert result.loc[0, "surface_bati"] == 60.0
    assert result.loc[0, "type_bien"] == "Appartement"


def test_aggregate_does_not_count_the_price_twice() -> None:
    """The main DVF trap: the total price is repeated on every row."""
    df = make_frame(
        make_row("A", area=60.0),
        make_row("A", local_type="Dependance", area=12.0),
        make_row("A", local_type="Dependance", area=8.0),
    )
    assert aggregate_by_sale(df)["prix"].sum() == 200_000.0


def test_keep_single_dwelling_drops_bundled_sales() -> None:
    df = make_frame(
        make_row("A", area=60.0),
        make_row("B", area=50.0),
        make_row("B", area=70.0),
    )
    result = keep_single_dwelling(aggregate_by_sale(df))
    assert list(result["id_mutation"]) == ["A"]


def test_filter_price_range_drops_outliers() -> None:
    df = pd.DataFrame({"prix": [1.0, 9_999.0, 250_000.0, 9_000_000.0]})
    assert list(filter_price_range(df)["prix"]) == [250_000.0]


def test_clean_sales_runs_the_whole_pipeline() -> None:
    df = make_frame(
        make_row("A", area=60.0),
        make_row("A", local_type="Dependance", area=12.0),
        make_row("B", nature="Adjudication"),
        make_row("C", price=None),
        make_row("D", price=50.0),
        make_row("E", area=None, local_type="Local industriel"),
    )
    result = clean_sales(df)
    assert list(result["id_mutation"]) == ["A"]
    assert result.loc[0, "surface_bati"] == 60.0
