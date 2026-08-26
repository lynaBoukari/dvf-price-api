"""Tests de la préparation des variables et des métriques."""

import numpy as np
import pandas as pd
import pytest

from dvf.model.features import preparer, separer_temporellement
from dvf.model.metrics import evaluer


def ventes() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date_mutation": ["2022-05-10", "2023-11-02", "2024-03-15", "2024-07-20"],
            "prix": [200_000.0, 250_000.0, 300_000.0, 180_000.0],
            "surface_bati": [60.0, 75.0, 90.0, 50.0],
            "nb_pieces": [3.0, 4.0, 5.0, 2.0],
            "surface_terrain": [0.0, 200.0, 0.0, 0.0],
            "longitude": [-0.57, -0.60, -0.55, -0.58],
            "latitude": [44.83, 44.85, 44.81, 44.84],
            "nb_lots": [1, 2, 1, 1],
            "type_bien": ["Appartement", "Maison", "Appartement", "Appartement"],
        }
    )


def test_preparer_extrait_le_mois() -> None:
    variables, _ = preparer(ventes())
    assert list(variables["mois"]) == [5, 11, 3, 7]


def test_preparer_exclut_l_annee() -> None:
    """Le modèle ne doit pas apprendre l'année : il ne saurait pas extrapoler."""
    variables, _ = preparer(ventes())
    assert "annee" not in variables.columns
    assert "date_mutation" not in variables.columns


def test_preparer_separe_bien_la_cible() -> None:
    variables, cible = preparer(ventes())
    assert "prix" not in variables.columns
    assert list(cible) == [200_000.0, 250_000.0, 300_000.0, 180_000.0]


def test_type_bien_devient_categoriel() -> None:
    variables, _ = preparer(ventes())
    assert str(variables["type_bien"].dtype) == "category"


def test_separation_temporelle_respecte_la_date() -> None:
    entrainement, test = separer_temporellement(ventes(), "2024-01-01")
    assert len(entrainement) == 2
    assert len(test) == 2
    assert entrainement["date_mutation"].max() < "2024-01-01"


def test_separation_temporelle_ne_perd_aucune_vente() -> None:
    df = ventes()
    entrainement, test = separer_temporellement(df, "2024-01-01")
    assert len(entrainement) + len(test) == len(df)


def test_metriques_sur_une_prediction_parfaite() -> None:
    reel = pd.Series([100.0, 200.0])
    mesures = evaluer(reel, np.array([100.0, 200.0]))
    assert mesures.mae == 0.0
    assert mesures.mape == 0.0
    assert mesures.rmse == 0.0


def test_metriques_calculent_les_bonnes_valeurs() -> None:
    reel = pd.Series([100.0, 200.0])
    mesures = evaluer(reel, np.array([90.0, 220.0]))
    assert mesures.mae == pytest.approx(15.0)
    assert mesures.mape == pytest.approx(0.10)
    assert mesures.rmse == pytest.approx(np.sqrt((100 + 400) / 2))


def test_rmse_penalise_plus_que_mae() -> None:
    """Une grosse erreur pèse davantage sur la RMSE : c'est tout son intérêt."""
    reel = pd.Series([100.0, 100.0, 100.0])
    mesures = evaluer(reel, np.array([100.0, 100.0, 160.0]))
    assert mesures.rmse > mesures.mae
