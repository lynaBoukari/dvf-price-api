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

### Périmètre et limites

Sur 27 085 mutations (année 2024), après agrégation par vente :

| `nb_logements` | Mutations | Part | Traitement |
|---|---|---|---|
| 0 | 7 753 | 28,6 % | Hors périmètre : terrains, garages, locaux commerciaux |
| 1 | 16 781 | 62,0 % | Conservées |
| ≥ 2 | 2 551 | 9,4 % | Écartées : pas de prix unitaire exploitable |

Les ventes sans logement ne relèvent pas de ce modèle, qui estime le
prix d'un bien d'habitation. La limite réelle porte sur les 9,4 % de
ventes groupées : DVF ne publie qu'un prix global, dont on ne peut
pas déduire la valeur de chaque logement.

Piste d'amélioration : pour les ventes groupées de biens homogènes,
répartir le prix au prorata des surfaces. Non retenu ici, l'hypothèse
d'homogénéité étant invérifiable.

## Modèle

`HistGradientBoostingRegressor` entraîné sur le **logarithme du prix**,
sur les ventes 2022–2023 (44 298), évalué sur 2024 (16 729).

| | MAE | MAPE moyen | RMSE |
|---|---|---|---|
| Référence (3 738 €/m² médian × surface) | 114 128 € | 60,7 % | 201 467 € |
| Modèle | 63 966 € | 30,8 % | 124 292 € |

**Gain de 44,0 % sur la référence.**

### Lire ces chiffres correctement

Le MAPE moyen est trompeur : la distribution des erreurs est très
asymétrique.

| | erreur relative |
|---|---|
| médiane | 15,5 % |
| 90e centile | 54,5 % |
| 99e centile | 261,2 % |

**La prédiction typique se trompe de 15,5 %.** Une minorité de
prédictions très mauvaises tire la moyenne vers le haut.

Erreur médiane par quintile de prix :

| Quintile | Prix médian | Erreur médiane |
|---|---|---|
| très bas | 105 000 € | 26,2 % |
| bas | 165 000 € | 14,4 % |
| moyen | 230 000 € | 13,2 % |
| haut | 311 050 € | 13,5 % |
| très haut | 505 000 € | 15,2 % |

## Choix de modélisation

**Séparation temporelle, pas aléatoire.** En production le modèle
estimera des ventes futures sans jamais accéder à des transactions
postérieures. Un découpage aléatoire produirait un score optimiste et
non représentatif.

**L'année n'est pas une variable.** Les modèles à base d'arbres
n'extrapolent pas : une année inconnue serait traitée comme la plus
proche année connue. Seul le mois est conservé, pour la saisonnalité.

**Entraînement sur `log(prix)`.** Entraîné sur le prix brut, le modèle
minimisait l'erreur en euros et négligeait donc le bas du marché, où
l'erreur médiane atteignait 33,9 %. Le passage au logarithme, qui revient
à minimiser l'erreur relative, l'a ramenée à 26,2 % — avec un léger coût
sur le haut du marché (15,0 % → 15,2 %), conforme au mécanisme attendu.
La transformation est encapsulée dans un `TransformedTargetRegressor` :
`.predict()` renvoie des euros.

**Une référence systématique.** Prix médian au m² du jeu d'entraînement
× surface. Sans point de comparaison, une erreur en euros n'est pas
interprétable.

## Limites connues

- Le quintile de prix le plus bas reste le moins bien prédit (26,2 %).
  DVF ne publie ni l'état du bien, ni l'étage, ni la présence de travaux.
- Les ventes portant sur plusieurs logements sont exclues, faute de prix
  unitaire exploitable (9,4 % des mutations).
- Périmètre limité à la Gironde.

Le modèle est accompagné d'un `models/modele.json` décrivant les données
d'entraînement, les colonnes attendues et les métriques obtenues

## Entrepôt

Les données nettoyées sont chargées dans BigQuery (`dvf_raw.ventes`,
région `europe-west1`). Les requêtes d'analyse sont versionnées dans `analyses/`.

| Fichier | Contenu |
|---|---|
| `01_exploration.sql` | Chargement, contrôle d'équivalence pandas/SQL, premiers agrégats |
| `02_fenetrage.sql` | Fonctions de fenêtrage, dédoublonnage, évolution annuelle |

### Ce que l'exploration a montré

- **Retournement du marché en 2024.** Le volume chute d'un tiers entre 2022 et
  2024 pendant que le prix au m² ne cède que 7 %. Sur les dix communes les plus
  actives, cinq montaient encore en 2023 ; les dix baissent en 2024.
- **La localisation domine.** Facteur 12 entre la commune la plus chère
  (Lège-Cap-Ferret, 10 602 €/m²) et la moins chère (Sainte-Foy-la-Grande, 896 €).
  Bordeaux concentre 22 % des ventes.
- **Le modèle apprend un régime de marché et est évalué sur un autre**, ce qui
  justifie la séparation temporelle par la mesure et non par principe.

### Dettes assumées

| Dette | Symptôme | Réparation prévue |
|---|---|---|
| Typage | `date_mutation` en `STRING`, `code_postal` en `FLOAT` | réparée — couche de staging dbt |
| Nommage des couches | `dvf_raw` contient de la donnée déjà transformée | Passage en ELT : charger le CSV brut, transformer en SQL |