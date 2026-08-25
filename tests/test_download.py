"""Tests du module de téléchargement.

On ne teste pas le téléchargement réel : un test ne doit jamais dépendre du
réseau. On teste la logique pure, ici la construction de l'URL.
"""

from dvf.data.download import build_url


def test_build_url_compose_une_url_valide() -> None:

    url= build_url(2024,"33")
    assert url.startswith("https://")
    assert url.endswith("/2024/departements/33.csv.gz")

def test_build_url_gere_les_departements_corses()-> None:
    assert build_url(2024,"2A").endswith("/2A.csv.gz")

def test_build_url_change_avec_l_annee() -> None:
    assert build_url(2022,"33") != build_url(2024,"33")

    