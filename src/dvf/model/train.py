"""Training of the price estimation model."""

import json
import logging
from dataclasses import asdict

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor

from dvf.config import settings
from dvf.model.features import build_features, time_based_split
from dvf.model.metrics import evaluate

logger = logging.getLogger(__name__)

SPLIT_DATE = "2024-01-01"
RANDOM_SEED = 42


def predict_baseline(train: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Baseline model: median price per square metre of the training set.

    Any real model must beat this baseline. If it does not, it adds nothing,
    and it is better to find out before shipping it.

    The price per square metre is computed on the training set only. Using the
    whole dataset would leak test information into the baseline.
    """
    price_per_sqm = (train["prix"] / train["surface_bati"]).median()
    logger.info("Baseline: %.0f EUR/sqm median", price_per_sqm)
    return np.asarray(test["surface_bati"] * price_per_sqm, dtype=float)


def train_model(train: pd.DataFrame) -> TransformedTargetRegressor:
    """Train the model on the logarithm of the price.

    Trained on the raw price, the model minimises the error in euros: a
    100,000 EUR error on an 800,000 EUR property weighs a hundred times more
    than a 10,000 EUR error on a 60,000 EUR one. It therefore neglects the
    lower end of the market. Minimising the error on the logarithm is roughly
    equivalent to minimising the RELATIVE error, which is what MAPE measures.

    TransformedTargetRegressor applies log() when fitting and exp() when
    predicting: the caller still receives euros and knows nothing about it.
    """
    features, target = build_features(train)

    model = TransformedTargetRegressor(
        regressor=HistGradientBoostingRegressor(
            max_iter=300,
            learning_rate=0.08,
            max_depth=8,
            categorical_features="from_dtype",
            random_state=RANDOM_SEED,
        ),
        func=np.log,
        inverse_func=np.exp,
    )
    model.fit(features, target)
    return model


def main() -> None:
    """Train, evaluate against a baseline, and save the model."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    source = settings.processed_data_dir / "ventes_33.parquet"
    sales = pd.read_parquet(source)
    logger.info("Loaded %d sales", len(sales))

    train, test = time_based_split(sales, SPLIT_DATE)

    baseline = evaluate(test["prix"], predict_baseline(train, test))
    logger.info("Baseline : %s", baseline.summary())

    model = train_model(train)
    test_features, test_target = build_features(test)
    model_metrics = evaluate(test_target, model.predict(test_features))
    logger.info("Model    : %s", model_metrics.summary())

    improvement = 1 - model_metrics.mae / baseline.mae
    logger.info("Improvement over baseline: %.1f%%", improvement * 100)

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, settings.models_dir / "modele.joblib")

    model_card = {
        "split_date": SPLIT_DATE,
        "training_sales": len(train),
        "test_sales": len(test),
        "columns": list(test_features.columns),
        "metrics": asdict(model_metrics),
        "baseline": asdict(baseline),
    }
    (settings.models_dir / "modele.json").write_text(
        json.dumps(model_card, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Model and model card written to %s", settings.models_dir.name)


if __name__ == "__main__":
    main()
