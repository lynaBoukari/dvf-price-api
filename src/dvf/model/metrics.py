"""Mesure de la qualité des prédictions."""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Metriques:
    """Trois mesures complémentaires d'une erreur de prédiction."""

    mae: float
    """Erreur absolue moyenne, en euros. Facile à expliquer."""

    mape: float
    """Erreur relative moyenne, en pourcentage. Comparable entre marchés."""

    rmse: float
    """Racine de l'erreur quadratique. Pénalise fortement les grosses erreurs."""

    def resumer(self) -> str:
        return f"MAE {self.mae:,.0f} EUR | MAPE {self.mape:.1%} | RMSE {self.rmse:,.0f} EUR"


def evaluer(reel: pd.Series, predit: np.ndarray) -> Metriques:
    """Calcule les trois métriques à la main, pour comprendre ce qu'elles font."""
    valeurs = np.asarray(reel, dtype=float)
    erreurs = valeurs - predit

    return Metriques(
        mae=float(np.mean(np.abs(erreurs))),
        mape=float(np.mean(np.abs(erreurs / valeurs))),
        rmse=float(np.sqrt(np.mean(erreurs**2))),
    )
