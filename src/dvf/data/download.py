"""Téléchargement des fichiers DVF géolocalisés publiés sur data.gouv.fr."""

import logging
from pathlib import Path

import requests

from dvf.config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 1024 * 1024 # 1 Mo
TIMEOUT_SECONDS =120

def build_url(year: int, departement: str) -> str:

     """Construit l'URL du fichier DVF pour une année et un département."""
     return f"{settings.dvf_base_url}/{year}/departements/{departement}.csv.gz"

def download_departement(year:int, departement: str, *, force: bool=False) -> Path :
      """Télécharge un fichier DVF et renvoie son chemin local.

    Le fichier n'est pas retéléchargé s'il existe déjà, sauf si force vaut True.
    """
      settings.raw_data_dir.mkdir(parents=True, exist_ok=True) 
      destination = settings.raw_data_dir / f"dvf_{departement}_{year}.csv.gz"

      if destination.exists() and not force:
            logger.info("Deja present, telechargement ignore : %s", destination.name)
            return destination

      url = build_url(year, departement)
      logger.info("Telechargement de %s", url)

      with requests.get(url, stream=True, timeout=TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            with destination.open("wb") as file:
                  for chunk in response.iter_content(chunk_size=CHUNK_SIZE) :
                        file.write(chunk)

            size_mo = destination.stat().st_size / 1_000_000
            logger.info("Ecrit %s (%.1f Mo)", destination.name, size_mo)
            return destination

def main()-> None:
      
     """Point d'entrée : télécharge trois années pour un département."""
     logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
     for year in (2022, 2023,2024) :
           download_departement(year,"33")

if __name__ == "__main__":
    main()

                
    