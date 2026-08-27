"""Download the geolocated DVF files published on data.gouv.fr."""

import logging
from pathlib import Path

import requests

from dvf.config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024  # 1 MB
TIMEOUT_SECONDS = 120


def build_url(year: int, department: str) -> str:
    """Build the DVF file URL for one year and one department."""
    return f"{settings.dvf_base_url}/{year}/departements/{department}.csv.gz"


def download_department(year: int, department: str, *, force: bool = False) -> Path:
    """Download one DVF file and return its local path.

    An existing file is not downloaded again unless force is True.
    """
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.raw_data_dir / f"dvf_{department}_{year}.csv.gz"

    if destination.exists() and not force:
        logger.info("Already present, skipping download: %s", destination.name)
        return destination

    url = build_url(year, department)
    logger.info("Downloading %s", url)

    with requests.get(url, stream=True, timeout=TIMEOUT_SECONDS) as response:
        response.raise_for_status()
        with destination.open("wb") as file:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                file.write(chunk)

    size_mb = destination.stat().st_size / 1_000_000
    logger.info("Wrote %s (%.1f MB)", destination.name, size_mb)
    return destination


def main() -> None:
    """Entry point: download three years for one department."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    for year in (2022, 2023, 2024):
        download_department(year, "33")


if __name__ == "__main__":
    main()
