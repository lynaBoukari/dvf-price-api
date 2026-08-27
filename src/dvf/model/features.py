"""Feature building and train / test split.

Column names stay in French: they come from the DVF dataset. Everything the
code defines is in English.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

NUMERIC_FEATURES = [
    "surface_bati",
    "nb_pieces",
    "surface_terrain",
    "longitude",
    "latitude",
    "nb_lots",
]

CATEGORICAL_FEATURES = ["type_bien"]

TARGET = "prix"


def time_based_split(
    df: pd.DataFrame,
    split_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split the dataset by date, not at random.

    A random split would let the model see 2024 sales in order to predict
    2023 ones: impossible in production, and the resulting score would be
    optimistic. We train on the past and evaluate on the future.
    """
    dates = pd.to_datetime(df["date_mutation"])
    split_point = pd.Timestamp(split_date)

    train = df[dates < split_point]
    test = df[dates >= split_point]

    logger.info(
        "Split at %s: %d training sales, %d test sales",
        split_date,
        len(train),
        len(test),
    )
    return train, test


def build_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Split the dataframe into features and target.

    We deliberately do NOT keep the year: tree-based models cannot
    extrapolate, so an unseen year would be treated as the closest known one.
    The month is kept, because it captures a seasonality that repeats.
    """
    work = df.copy()
    work["mois"] = pd.to_datetime(work["date_mutation"]).dt.month

    columns = [*NUMERIC_FEATURES, "mois", *CATEGORICAL_FEATURES]
    features = work[columns].copy()

    for column in CATEGORICAL_FEATURES:
        features[column] = features[column].astype("category")

    return features, work[TARGET]
