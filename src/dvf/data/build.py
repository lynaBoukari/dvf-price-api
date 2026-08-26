"""Construction du jeu de données propre à partir des fichiers DVF bruts."""

import logging
from pathlib import Path

import pandas as pd

from dvf.config import settings
from dvf.data.clean import nettoyer

logger = logging.getLogger(__name__)

# On ne lit que les colonnes utiles : DVF en compte plus de quarante, et en
# charger l'intégralité gaspille mémoire et temps sans rien apporter.
COLONNES_LUES = [
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


def charger_brut(chemin: Path) -> pd.DataFrame:
    """Lit un fichier DVF compressé."""
    return pd.read_csv(chemin, compression="gzip", usecols=COLONNES_LUES, low_memory=False)


def construire(departement: str, annees: tuple[int, ...]) -> pd.DataFrame:
    """Charge, concatène et nettoie plusieurs années pour un département."""

    morceaux = []

    for annee in annees:
        chemin = settings.raw_data_dir / f"dvf_{departement}_{annee}.csv.gz"
        if not chemin.exists():
            logger.warning("Fichier absent, ignoré : %s", chemin.name)
            continue
        morceaux.append(charger_brut(chemin))

    if not morceaux:
        message = "Aucun fichier brut trouvé. Lance d'abord dvf.data.download."
        raise FileNotFoundError(message)

    brut = pd.concat(morceaux, ignore_index=True)
    logger.info("Chargé %d lignes brutes", len(brut))
    return nettoyer(brut)


def main() -> None:
    """Construit le jeu propre et l'écrit en Parquet."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    propre = construire("33", (2022, 2023, 2024))

    settings.processed_data_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.processed_data_dir / "ventes_33.parquet"
    propre.to_parquet(destination, index=False)

    logger.info("Écrit %s : %d ventes", destination.name, len(propre))
    logger.info("Prix médian : %.0f EUR", propre["prix"].median())
    logger.info("Surface médiane : %.0f m2", propre["surface_bati"].median())


if __name__ == "__main__":
    main()
