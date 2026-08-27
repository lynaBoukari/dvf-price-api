"""Tests for feature building and metrics."""

import numpy as np
import pandas as pd
import pytest

from dvf.model.features import build_features, time_based_split
from dvf.model.metrics import evaluate


def sample_sales() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date_mutation": ["2022-05-10", "2023-11-02", "2024-03-15", "2024-07-20"],
            "prix": [200_000.0, 250_000.0, 300_000.0, 180_000.0],
            "surface_bati": [60.0, 75.0, 90.0, 50.0],
            "nb_pieces": [3.0, 4.0, 5.0, 2.0],
            "surface_terrain": [0.0, 200.0, 0.0, 0.0],
            "longitude": [-0.57, -0.60, -0.55, -0.58],
            "latitude": [44.83, 44.85, 44.81, 44.84],
            "nb_lots": [1, 2, 1, 1],
            "type_bien": ["Appartement", "Maison", "Appartement", "Appartement"],
        }
    )


def test_build_features_extracts_the_month() -> None:
    features, _ = build_features(sample_sales())
    assert list(features["mois"]) == [5, 11, 3, 7]


def test_build_features_excludes_the_year() -> None:
    """The model must not learn the year: it could not extrapolate."""
    features, _ = build_features(sample_sales())
    assert "annee" not in features.columns
    assert "date_mutation" not in features.columns


def test_build_features_separates_the_target() -> None:
    features, target = build_features(sample_sales())
    assert "prix" not in features.columns
    assert list(target) == [200_000.0, 250_000.0, 300_000.0, 180_000.0]


def test_property_type_becomes_categorical() -> None:
    features, _ = build_features(sample_sales())
    assert str(features["type_bien"].dtype) == "category"


def test_time_based_split_respects_the_date() -> None:
    train, test = time_based_split(sample_sales(), "2024-01-01")
    assert len(train) == 2
    assert len(test) == 2
    assert train["date_mutation"].max() < "2024-01-01"


def test_time_based_split_loses_no_sale() -> None:
    df = sample_sales()
    train, test = time_based_split(df, "2024-01-01")
    assert len(train) + len(test) == len(df)


def test_metrics_on_a_perfect_prediction() -> None:
    actual = pd.Series([100.0, 200.0])
    result = evaluate(actual, np.array([100.0, 200.0]))
    assert result.mae == 0.0
    assert result.mape == 0.0
    assert result.rmse == 0.0


def test_metrics_compute_the_right_values() -> None:
    actual = pd.Series([100.0, 200.0])
    result = evaluate(actual, np.array([90.0, 220.0]))
    assert result.mae == pytest.approx(15.0)
    assert result.mape == pytest.approx(0.10)
    assert result.rmse == pytest.approx(np.sqrt((100 + 400) / 2))


def test_rmse_penalises_more_than_mae() -> None:
    """One large error weighs more on RMSE: that is exactly its purpose."""
    actual = pd.Series([100.0, 100.0, 100.0])
    result = evaluate(actual, np.array([100.0, 100.0, 160.0]))
    assert result.rmse > result.mae
