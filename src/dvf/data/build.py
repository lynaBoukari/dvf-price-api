"""Build the clean dataset from the raw DVF files."""

import logging
from pathlib import Path

import pandas as pd

from dvf.config import settings
from dvf.data.clean import clean_sales
from dvf.data.quality import CleaningReport, check_quality

logger = logging.getLogger(__name__)

# We only read the columns we need: DVF has more than forty, and loading all
# of them wastes memory and time for no benefit.
RAW_COLUMNS = [
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


def read_raw_file(path: Path) -> pd.DataFrame:
    """Read one compressed DVF file."""
    return pd.read_csv(path, compression="gzip", usecols=RAW_COLUMNS, low_memory=False)


def load_years(department: str, years: tuple[int, ...]) -> pd.DataFrame:
    """Load and concatenate several years for one department.

    This function only loads. Cleaning is called separately, which is what
    lets us measure how many rows each step drops.
    """
    chunks = []
    for year in years:
        path = settings.raw_data_dir / f"dvf_{department}_{year}.csv.gz"
        if not path.exists():
            logger.warning("Missing file, skipped: %s", path.name)
            continue
        chunks.append(read_raw_file(path))

    if not chunks:
        message = "No raw file found. Run dvf.data.download first."
        raise FileNotFoundError(message)

    return pd.concat(chunks, ignore_index=True)


def main() -> None:
    """Build the clean dataset, check its quality, write it as Parquet."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    raw = load_years("33", (2022, 2023, 2024))
    cleaned = clean_sales(raw)

    report = CleaningReport(raw_rows=len(raw), kept_sales=len(cleaned))
    check_quality(report)
    logger.info(report.summary())

    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.processed_data_dir / "ventes_33.parquet"
    cleaned.to_parquet(destination, index=False)

    logger.info("Wrote %s", destination.name)
    logger.info("Median price: %.0f EUR", cleaned["prix"].median())
    logger.info("Median living area: %.0f sqm", cleaned["surface_bati"].median())


if __name__ == "__main__":
    main()
