"""Tests de la référence et de l'entraînement.

On ne teste pas main() : c'est de l'orchestration (lecture et écriture de
fichiers, journalisation). Ce sera le rôle de la CI. On teste ici la logique
qui peut se tromper silencieusement.
"""

import numpy as np
import pandas as pd
import pytest

from dvf.model.features import preparer
from dvf.model.train import entrainer, predire_reference


def test_reference_utilise_la_mediane_du_train_pas_du_test() -> None:
    """Le prix au m2 doit venir du jeu d'entraînement, jamais du test.

    Le prix du jeu de test est ici volontairement absurde : s'il influençait
    la prédiction, ce test échouerait. C'est un garde-fou anti-fuite.
    """
    entrainement = pd.DataFrame(
        {
            "prix": [200_000.0, 300_000.0, 400_000.0],
            "surface_bati": [100.0, 150.0, 200.0],  # tous à 2000 EUR/m2
        }
    )
    test = pd.DataFrame({"prix": [99_999_999.0], "surface_bati": [50.0]})

    prediction = predire_reference(entrainement, test)

    assert prediction[0] == pytest.approx(100_000.0)  # 50 m2 x 2000 EUR


def test_reference_est_proportionnelle_a_la_surface() -> None:
    entrainement = pd.DataFrame({"prix": [200_000.0], "surface_bati": [100.0]})
    test = pd.DataFrame({"prix": [0.0, 0.0], "surface_bati": [50.0, 100.0]})

    prediction = predire_reference(entrainement, test)

    assert prediction[1] == pytest.approx(2 * prediction[0])


def test_reference_renvoie_autant_de_valeurs_que_de_ventes() -> None:
    entrainement = pd.DataFrame({"prix": [200_000.0], "surface_bati": [100.0]})
    test = pd.DataFrame({"prix": [0.0] * 5, "surface_bati": [60.0] * 5})

    assert len(predire_reference(entrainement, test)) == 5


def petit_jeu(taille: int = 60) -> pd.DataFrame:
    """Un jeu minuscule mais au bon schéma, pour un entraînement rapide."""
    indices = np.arange(taille, dtype=float)
    return pd.DataFrame(
        {
            "date_mutation": ["2023-06-15"] * taille,
            "prix": 3000.0 * (40.0 + indices),
            "surface_bati": 40.0 + indices,
            "nb_pieces": 1.0 + indices % 5,
            "surface_terrain": indices % 3 * 100.0,
            "longitude": -0.57 + indices % 7 * 0.01,
            "latitude": 44.83 + indices % 5 * 0.01,
            "nb_lots": 1 + (indices % 2).astype(int),
            "type_bien": ["Appartement", "Maison"] * (taille // 2),
        }
    )


@pytest.mark.lent
def test_entrainer_produit_un_modele_qui_predit() -> None:
    modele = entrainer(petit_jeu())
    variables, _ = preparer(petit_jeu())
    predictions = modele.predict(variables)

    assert len(predictions) == 60
    assert np.all(predictions > 0)


@pytest.mark.lent
def test_entrainement_est_reproductible() -> None:
    """random_state fixé : deux entraînements identiques donnent le même modèle."""
    variables, _ = preparer(petit_jeu())

    premier = entrainer(petit_jeu()).predict(variables)
    second = entrainer(petit_jeu()).predict(variables)

    np.testing.assert_allclose(premier, second)
