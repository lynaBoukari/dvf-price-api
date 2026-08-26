"""Contrôle de qualité du nettoyage.

Une mesure faite une fois dans un notebook est une curiosité. La même mesure
vérifiée à chaque exécution est un garde-fou : si la source change de format
un jour, le pipeline s'arrête au lieu de produire des données silencieusement
fausses.
"""

from dataclasses import dataclass

# En dessous de ce taux, quelque chose a changé chez la source.
TAUX_SURVIE_MINIMAL = 0.10


class QualiteInsuffisante(Exception):
    """Le nettoyage a écarté beaucoup plus de données que prévu."""


@dataclass(frozen=True)
class RapportNettoyage:
    """Résumé chiffré d'une exécution du nettoyage."""

    lignes_brutes: int
    ventes_retenues: int

    @property
    def taux_survie(self) -> float:
        """Part des lignes brutes qui deviennent des ventes exploitables."""
        if self.lignes_brutes == 0:
            return 0.0
        return self.ventes_retenues / self.lignes_brutes

    def resumer(self) -> str:
        """Une ligne lisible, destinée aux journaux."""
        return (
            f"{self.lignes_brutes} lignes brutes -> {self.ventes_retenues} ventes "
            f"({self.taux_survie:.1%} conservees)"
        )


def verifier(rapport: RapportNettoyage, taux_minimal: float = TAUX_SURVIE_MINIMAL) -> None:
    """Lève une exception si le nettoyage a écarté trop de données.

    On échoue bruyamment plutôt que de laisser passer un jeu de données
    suspect : une erreur visible coûte beaucoup moins cher qu'un modèle
    entraîné sur des données tronquées.
    """
    if rapport.lignes_brutes == 0:
        message = "Aucune ligne brute : les fichiers sources sont vides ou absents."
        raise QualiteInsuffisante(message)

    if rapport.taux_survie < taux_minimal:
        message = (
            f"Taux de survie de {rapport.taux_survie:.1%}, "
            f"en dessous du seuil de {taux_minimal:.0%}. "
            f"Le format de la source a peut-etre change."
        )
        raise QualiteInsuffisante(message)
