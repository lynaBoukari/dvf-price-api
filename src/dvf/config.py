"""Configuration centrale du projet.

Tous les chemins et réglages passent par ici. Aucun chemin en dur ailleurs
dans le code : c'est ce qui permettra plus tard de changer de machine ou de
passer en conteneur sans rien casser.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    """Réglages du projet, surchargeables par variables d'environnement."""

    raw_data_dir: Path = PROJECT_ROOT / "data" / "raw"
    processed_data_dir: Path = PROJECT_ROOT / "data" / "processed"
    dvf_base_url: str = "https://files.data.gouv.fr/geo-dvf/latest/csv"


settings =Settings()