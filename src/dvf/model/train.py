"""Entraînement du modèle d'estimation de prix."""

import json
import logging
from dataclasses import asdict

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from dvf.config import settings
from dvf.model.features import preparer, separer_temporellement
from dvf.model.metrics import evaluer

logger = logging.getLogger(__name__)

DATE_BASCULE = "2024-01-01"
GRAINE = 42


def predire_reference(entrainement: pd.DataFrame, test: pd.DataFrame) -> np.ndarray:
    """Modèle de référence : prix médian au m2 du jeu d'entraînement.

    Tout modèle doit battre cette référence. S'il ne la bat pas, il n'apporte
    rien et il vaut mieux le savoir avant de le mettre en production.
    """

    prix_m2 = (entrainement["prix"] / entrainement["surface_bati"]).median()
    logger.info("Reference : %.0f EUR/m2 median", prix_m2)
    return np.asarray(test["surface_bati"] * prix_m2, dtype=float)


def entrainer(entrainement: pd.DataFrame) -> HistGradientBoostingRegressor:
    """Entraîne le modèle sur le jeu d'entraînement."""
    variables, cible = preparer(entrainement)

    modele = HistGradientBoostingRegressor(
        max_iter=300,
        learning_rate=0.08,
        max_depth=8,
        categorical_features="from_dtype",
        random_state=GRAINE,
    )
    modele.fit(variables, cible)
    return modele


def main() -> None:
    """Entraîne, évalue contre une référence, et sauvegarde le modèle."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    source = settings.processed_data_dir / "ventes_33.parquet"
    ventes = pd.read_parquet(source)
    logger.info("Charge %d ventes", len(ventes))

    entrainement, test = separer_temporellement(ventes, DATE_BASCULE)

    reference = evaluer(test["prix"], predire_reference(entrainement, test))
    logger.info("Reference  : %s", reference.resumer())

    modele = entrainer(entrainement)
    variables_test, cible_test = preparer(test)
    mesures = evaluer(cible_test, modele.predict(variables_test))
    logger.info("Modele     : %s", mesures.resumer())

    gain = 1 - mesures.mae / reference.mae
    logger.info("Gain sur la reference : %.1f%%", gain * 100)

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(modele, settings.models_dir / "modele.joblib")

    carte = {
        "date_bascule": DATE_BASCULE,
        "ventes_entrainement": len(entrainement),
        "ventes_test": len(test),
        "colonnes": list(variables_test.columns),
        "metriques": asdict(mesures),
        "reference": asdict(reference),
    }
    (settings.models_dir / "modele.json").write_text(
        json.dumps(carte, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Modele et carte d'identite ecrits dans %s", settings.models_dir.name)


if __name__ == "__main__":
    main()
