"""Nettoyage des données DVF brutes.

Chaque fonction applique UNE décision de nettoyage et une seule. C'est ce qui
permet de les tester séparément, et d'expliquer chaque choix en entretien.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# Les seuls types de bien que ce modèle traite.
LOGEMENTS = frozenset({"Maison", "Appartement"})

# Seules les ventes de gré à gré reflètent un prix de marché.
NATURES_CONSERVEES = frozenset({"Vente"})

# Bornes métier : en dessous, ce n'est pas une transaction réelle ;
# au-dessus, c'est un bien exceptionnel hors du périmètre du modèle.
PRIX_MIN = 10_000.0
PRIX_MAX = 5_000_000.0


def filtrer_ventes(df: pd.DataFrame) -> pd.DataFrame:
    """Ne garde que les mutations qui sont de vraies ventes de marché."""

    avant = len(df)
    resultat = df[df["nature_mutation"].isin(NATURES_CONSERVEES)]
    logger.info("filtrer_ventes : %d -> %d lignes", avant, len(resultat))
    return resultat


def supprimer_prix_manquants(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime les lignes sans prix."""

    avant = len(df)
    resultat = df.dropna(subset=["valeur_fonciere"])

    logger.info("supprimer_prix_manquants : %d -> %d ", avant, len(resultat))

    return resultat


def agreger_par_mutation(df: pd.DataFrame) -> pd.DataFrame:
    """Réduit chaque mutation à une seule ligne.

    Une vente peut porter sur plusieurs lots (logement, parking, cave), et DVF
    recopie le prix total sur chacun. On additionne donc les surfaces des
    logements et on ne garde qu'une fois le prix.
    """

    travail = df.copy()
    travail["est_logement"] = travail["type_local"].isin(LOGEMENTS)
    travail["surface_logement"] = travail["surface_reelle_bati"].where(travail["est_logement"])
    travail["pieces_logement"] = travail["nombre_pieces_principales"].where(travail["est_logement"])

    agrege = travail.groupby("id_mutation").agg(
        date_mutation=("date_mutation", "first"),
        prix=("valeur_fonciere", "first"),
        nom_commune=("nom_commune", "first"),
        code_postal=("code_postal", "first"),
        nb_logements=("est_logement", "sum"),
        nb_lots=("id_mutation", "size"),
        surface_bati=("surface_logement", "sum"),
        nb_pieces=("pieces_logement", "sum"),
        surface_terrain=("surface_terrain", "sum"),
        longitude=("longitude", "first"),
        latitude=("latitude", "first"),
    )

    logements = travail[travail["est_logement"]]
    agrege["type_bien"] = logements.groupby("id_mutation")["type_local"].first()

    logger.info("agreger_par_mutation : %d -> %d mutations", len(df), len(agrege))

    return agrege.reset_index()


def garder_logement_unique(df: pd.DataFrame) -> pd.DataFrame:
    """Ne garde que les ventes portant sur exactement un logement.

    Une vente groupant deux appartements n'a pas de prix unitaire exploitable.
    """
    avant = len(df)
    resultat = df[df["nb_logements"] == 1]
    logger.info("garder_logements_unique : %d -> %d mutations ", avant, len(resultat))

    return resultat


def filtrer_prix(
    df: pd.DataFrame,
    prix_min: float = PRIX_MIN,
    prix_max: float = PRIX_MAX,
) -> pd.DataFrame:
    """Écarte les prix hors du périmètre du modèle."""
    avant = len(df)
    resultat = df[df["prix"].between(prix_min, prix_max)]
    logger.info("filtrer_prix : %d -> %d mutations", avant, len(resultat))
    return resultat


def filtrer_surfaces(df: pd.DataFrame) -> pd.DataFrame:
    """Écarte les surfaces nulles ou absurdes."""

    avant = len(df)
    resultat = df[df["surface_bati"].between(9, 1000)]
    logger.info("filtrer_surfaces : %d -> %d mutations", avant, len(resultat))
    return resultat


def nettoyer(df: pd.DataFrame) -> pd.DataFrame:
    """Enchaîne toutes les étapes de nettoyage, dans l'ordre."""

    return (
        df.pipe(filtrer_ventes)
        .pipe(supprimer_prix_manquants)
        .pipe(agreger_par_mutation)
        .pipe(garder_logement_unique)
        .pipe(filtrer_prix)
        .pipe(filtrer_surfaces)
        .reset_index(drop=True)
    )
