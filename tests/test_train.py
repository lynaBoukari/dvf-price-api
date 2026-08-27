"""Tests for the baseline and the training routine.

We do not test main(): it is orchestration (reading and writing files,
logging). That will be the job of CI. Here we test the logic that could go
wrong silently.
"""

import numpy as np
import pandas as pd
import pytest

from dvf.model.features import build_features
from dvf.model.train import predict_baseline, train_model


def test_baseline_uses_the_training_median_not_the_test_one() -> None:
    """The price per sqm must come from the training set, never the test set.

    The test price here is deliberately absurd: if it influenced the
    prediction, this test would fail. It is a leakage guardrail.
    """
    train = pd.DataFrame(
        {
            "prix": [200_000.0, 300_000.0, 400_000.0],
            "surface_bati": [100.0, 150.0, 200.0],  # all at 2000 EUR/sqm
        }
    )
    test = pd.DataFrame({"prix": [99_999_999.0], "surface_bati": [50.0]})

    prediction = predict_baseline(train, test)

    assert prediction[0] == pytest.approx(100_000.0)  # 50 sqm x 2000 EUR


def test_baseline_is_proportional_to_the_area() -> None:
    train = pd.DataFrame({"prix": [200_000.0], "surface_bati": [100.0]})
    test = pd.DataFrame({"prix": [0.0, 0.0], "surface_bati": [50.0, 100.0]})

    prediction = predict_baseline(train, test)

    assert prediction[1] == pytest.approx(2 * prediction[0])


def test_baseline_returns_one_value_per_sale() -> None:
    train = pd.DataFrame({"prix": [200_000.0], "surface_bati": [100.0]})
    test = pd.DataFrame({"prix": [0.0] * 5, "surface_bati": [60.0] * 5})

    assert len(predict_baseline(train, test)) == 5


def small_dataset(size: int = 60) -> pd.DataFrame:
    """A tiny dataset with the right schema, for a fast training run."""
    index = np.arange(size, dtype=float)
    return pd.DataFrame(
        {
            "date_mutation": ["2023-06-15"] * size,
            "prix": 3000.0 * (40.0 + index),
            "surface_bati": 40.0 + index,
            "nb_pieces": 1.0 + index % 5,
            "surface_terrain": index % 3 * 100.0,
            "longitude": -0.57 + index % 7 * 0.01,
            "latitude": 44.83 + index % 5 * 0.01,
            "nb_lots": 1 + (index % 2).astype(int),
            "type_bien": ["Appartement", "Maison"] * (size // 2),
        }
    )


@pytest.mark.slow
def test_train_model_produces_a_usable_model() -> None:
    model = train_model(small_dataset())
    features, _ = build_features(small_dataset())
    predictions = model.predict(features)

    assert len(predictions) == 60
    assert np.all(predictions > 0)


@pytest.mark.slow
def test_training_is_reproducible() -> None:
    """Fixed random_state: two identical runs give the same model."""
    features, _ = build_features(small_dataset())

    first = train_model(small_dataset()).predict(features)
    second = train_model(small_dataset()).predict(features)

    np.testing.assert_allclose(first, second)
