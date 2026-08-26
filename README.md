# dvf-price-api

Estimation du prix de vente d'un bien immobilier à partir des données
publiques DVF (Demandes de valeurs foncières, DGFiP).

## État du projet

En construction. Actuellement : structure du projet et acquisition
des données. À venir : nettoyage, modèle, API, conteneurisation,
déploiement continu.

## Démarrer

```powershell
uv sync
uv run python -m dvf.data.download
uv run pytest
```

## Données

Ventes immobilières déclarées, publiées par la DGFiP sur data.gouv.fr.
Périmètre actuel : Gironde (33), années 2022 à 2024.
Les données ne sont pas versionnées ; le script les retélécharge.

## Choix techniques

- `uv` pour la gestion des dépendances et de l'environnement
- disposition `src/`, séparant le code applicatif des tests
- `ruff` et `mypy --strict` sur l'intégralité du code
