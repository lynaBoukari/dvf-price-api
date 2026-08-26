"""Tests du nettoyage.

On fabrique de petits tableaux à la main plutôt que de lire le vrai fichier :
un test doit être rapide, reproductible, et ne dépendre d'aucun fichier externe.
Chaque test vérifie UNE décision de nettoyage.
"""

import pandas as pd

from dvf.data.clean import (
    agreger_par_mutation,
    filtrer_prix,
    filtrer_ventes,
    garder_logement_unique,
    nettoyer,
    supprimer_prix_manquants,
)

COLONNES = [
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

# la "ligne" est le patron une fabrique de données de test
# je l'utilise pour eviter de recopier 12  colonnes à chaque test


def ligne(
    id_mutation: str,
    nature: str = "Vente",
    prix: float | None = 200_000.0,
    type_local: str | None = "Appartement",
    surface: float | None = 60.0,
    pieces: float | None = 3.0,
) -> dict[str, object]:
    """Fabrique une ligne DVF plausible, avec des valeurs par défaut saines."""
    return {
        "id_mutation": id_mutation,
        "date_mutation": "2024-03-15",
        "nature_mutation": nature,
        "valeur_fonciere": prix,
        "nom_commune": "Bordeaux",
        "code_postal": 33000.0,
        "type_local": type_local,
        "surface_reelle_bati": surface,
        "nombre_pieces_principales": pieces,
        "surface_terrain": 0.0,
        "longitude": -0.57,
        "latitude": 44.83,
    }


def tableau(*lignes: dict[str, object]) -> pd.DataFrame:
    return pd.DataFrame(list(lignes), columns=COLONNES)


def test_filtrer_ventes_ecarte_les_adjudications() -> None:
    df = tableau(
        ligne("A", nature="Vente"),
        ligne("B", nature="Adjudication"),
        ligne("C", nature="Expropriation"),
    )
    resultat = filtrer_ventes(df)
    assert list(resultat["id_mutation"]) == ["A"]


def test_supprimer_prix_manquants() -> None:
    df = tableau(ligne("A"), ligne("B", prix=None))
    assert list(supprimer_prix_manquants(df)["id_mutation"]) == ["A"]


def test_agreger_fusionne_les_lots_d_une_meme_vente() -> None:
    """Un appartement vendu avec son parking : deux lignes, une seule vente."""
    df = tableau(
        ligne("A", type_local="Appartement", surface=60.0, pieces=3.0),
        ligne("A", type_local="Dependance", surface=12.0, pieces=0.0),
    )
    resultat = agreger_par_mutation(df)

    assert len(resultat) == 1
    assert resultat.loc[0, "prix"] == 200_000.0
    assert resultat.loc[0, "nb_lots"] == 2
    assert resultat.loc[0, "nb_logements"] == 1
    assert resultat.loc[0, "surface_bati"] == 60.0
    assert resultat.loc[0, "type_bien"] == "Appartement"


def test_agreger_ne_compte_pas_le_prix_deux_fois() -> None:
    """Le piège principal de DVF : le prix total est recopié sur chaque ligne."""
    df = tableau(
        ligne("A", surface=60.0),
        ligne("A", type_local="Dependance", surface=12.0),
        ligne("A", type_local="Dependance", surface=8.0),
    )
    resultat = agreger_par_mutation(df)
    assert resultat["prix"].sum() == 200_000.0


def test_garder_logement_unique_ecarte_les_ventes_groupees() -> None:
    df = tableau(
        ligne("A", surface=60.0),
        ligne("B", surface=50.0),
        ligne("B", surface=70.0),
    )
    resultat = garder_logement_unique(agreger_par_mutation(df))
    assert list(resultat["id_mutation"]) == ["A"]


def test_filtrer_prix_ecarte_les_extremes() -> None:
    df = pd.DataFrame({"prix": [1.0, 9_999.0, 250_000.0, 9_000_000.0]})
    assert list(filtrer_prix(df)["prix"]) == [250_000.0]


def test_nettoyer_enchaine_tout_sans_erreur() -> None:
    df = tableau(
        ligne("A", surface=60.0),
        ligne("A", type_local="Dependance", surface=12.0),
        ligne("B", nature="Adjudication"),
        ligne("C", prix=None),
        ligne("D", prix=50.0),
        ligne("E", surface=None, type_local="Local industriel"),
    )

    resultat = nettoyer(df)

    assert list(resultat["id_mutation"]) == ["A"]
    # on vérifie d'abord la forme du résultat (combien de lignes, quelles colonnes)
    assert resultat.loc[0, "surface_bati"] == 60  # ensuite son contenu


# uv run pytest -v (pour afficher les noms de tests)
