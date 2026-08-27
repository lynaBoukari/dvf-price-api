"""Prediction quality measurement."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Metrics:
    """Three complementary views of a prediction error."""

    mae: float
    """Mean absolute error, in euros. Easy to explain to anyone."""

    mape: float
    """Mean absolute percentage error. Comparable across price ranges."""

    rmse: float
    """Root mean squared error. Heavily penalises large errors."""

    def summary(self) -> str:
        return f"MAE {self.mae:,.0f} EUR | MAPE {self.mape:.1%} | RMSE {self.rmse:,.0f} EUR"


def evaluate(actual: pd.Series, predicted: np.ndarray) -> Metrics:
    """Compute the three metrics by hand, to understand what they do."""
    values = np.asarray(actual, dtype=float)
    errors = values - predicted

    return Metrics(
        mae=float(np.mean(np.abs(errors))),
        mape=float(np.mean(np.abs(errors / values))),
        rmse=float(np.sqrt(np.mean(errors**2))),
    )
