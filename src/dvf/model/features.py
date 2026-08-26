"""Préparation des variables explicatives et séparation train / test."""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

COLONNES_NUMERIQUES = [
    "surface_bati",
    "nb_pieces",
    "surface_terrain",
    "longitude",
    "latitude",
    "nb_lots",
]

COLONNES_CATEGORIELLES = ["type_bien"]

CIBLE = "prix"


def separer_temporellement(
    df: pd.DataFrame,
    date_bascule: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Coupe le jeu en deux selon la date, pas au hasard.

    Une séparation aléatoire laisserait le modèle voir des ventes de 2024
    pour en prédire de 2023 : impossible en production, et le score obtenu
    serait trop optimiste. On entraîne sur le passé, on teste sur le futur.
    """
    dates = pd.to_datetime(df["date_mutation"])
    bascule = pd.Timestamp(date_bascule)

    entrainement = df[dates < bascule]
    test = df[dates >= bascule]

    logger.info(
        "Separation au %s : %d ventes d'entrainement, %d de test",
        date_bascule,
        len(entrainement),
        len(test),
    )
    return entrainement, test


def preparer(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Sépare les variables explicatives de la cible.

    On ne garde volontairement PAS l'année : le modèle serait incapable
    d'extrapoler sur une année qu'il n'a jamais vue. Le mois, lui, capture
    une saisonnalité qui se répète.
    """

    travail = df.copy()
    # feature engineering creation de la variable mois
    travail["mois"] = pd.to_datetime(travail["date_mutation"]).dt.month
    colonnes = [*COLONNES_NUMERIQUES, "mois", *COLONNES_CATEGORIELLES]
    variables = travail[colonnes].copy()

    for colonne in COLONNES_CATEGORIELLES:
        variables[colonne] = variables[colonne].astype("category")

    return variables, travail[CIBLE]
