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




## Décisions de nettoyage

Les données DVF brutes ne sont pas directement exploitables. Quatre
décisions, chacune implémentée dans une fonction testée de
`src/dvf/data/clean.py` :

| Décision | Raison |
|---|---|
| Agréger par `id_mutation` | Une vente peut porter sur plusieurs lots (logement, parking, cave). DVF émet une ligne par lot en recopiant le prix total sur chacune. Sans agrégation, le modèle apprend qu'un parking de 12 m² vaut 200 000 €. |
| Ne garder que `nature_mutation == "Vente"` | Adjudications, expropriations et échanges ne reflètent pas un prix de marché libre. Le critère est le sens de la transaction, pas sa fréquence. |
| Borner le prix entre 10 k€ et 5 M€ | Bornes métier plutôt que statistiques : la distribution des prix est fortement asymétrique, ce qui rend moyenne et écart-type peu fiables. En dessous de 10 k€, il s'agit de cessions symboliques ; au-dessus de 5 M€, de biens hors périmètre. |
| Supprimer les prix manquants (~0,7 %) | On n'impute jamais la variable cible : le modèle apprendrait la valeur inventée. |

Limite assumée : les ventes portant sur plusieurs logements sont
exclues, faute de prix unitaire exploitable.

