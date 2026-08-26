"""Tests du contrôle de qualité."""

import pytest

from dvf.data.qualite import (
    QualiteInsuffisante,
    RapportNettoyage,
    verifier,
)


def test_taux_de_survie_est_un_ratio() -> None:
    rapport = RapportNettoyage(lignes_brutes=1000, ventes_retenues=250)
    assert rapport.taux_survie == 0.25


def test_taux_de_survie_ne_divise_pas_par_zero() -> None:
    rapport = RapportNettoyage(lignes_brutes=0, ventes_retenues=0)
    assert rapport.taux_survie == 0.0


def test_resume_est_lisible() -> None:
    rapport = RapportNettoyage(lignes_brutes=1000, ventes_retenues=250)
    assert rapport.resumer() == "1000 lignes brutes -> 250 ventes (25.0% conservees)"


def test_verifier_accepte_un_taux_normal() -> None:
    verifier(RapportNettoyage(lignes_brutes=1000, ventes_retenues=207))


def test_verifier_refuse_un_taux_trop_bas() -> None:
    rapport = RapportNettoyage(lignes_brutes=1000, ventes_retenues=50)
    with pytest.raises(QualiteInsuffisante, match="5.0%"):
        verifier(rapport)


def test_verifier_refuse_un_jeu_vide() -> None:
    rapport = RapportNettoyage(lignes_brutes=0, ventes_retenues=0)
    with pytest.raises(QualiteInsuffisante, match="vides ou absents"):
        verifier(rapport)


def test_le_seuil_est_reglable() -> None:
    rapport = RapportNettoyage(lignes_brutes=1000, ventes_retenues=150)
    verifier(rapport, taux_minimal=0.10)
    with pytest.raises(QualiteInsuffisante):
        verifier(rapport, taux_minimal=0.20)


def test_le_rapport_est_immuable() -> None:
    """frozen=True empêche toute modification après construction."""
    rapport = RapportNettoyage(lignes_brutes=1000, ventes_retenues=250)
    with pytest.raises(AttributeError):
        rapport.ventes_retenues = 999  # type: ignore[misc]
