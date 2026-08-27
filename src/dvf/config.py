"""Central project configuration.

Every path and setting lives here. No hard-coded path anywhere else in the
codebase: this is what will let us switch machines or move into a container
without breaking anything.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Project settings, overridable through environment variables."""

    raw_data_dir: Path = PROJECT_ROOT / "data" / "raw"
    processed_data_dir: Path = PROJECT_ROOT / "data" / "processed"
    models_dir: Path = PROJECT_ROOT / "models"
    dvf_base_url: str = "https://files.data.gouv.fr/geo-dvf/latest/csv"


settings = Settings()
