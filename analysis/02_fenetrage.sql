-- =============================================================================
-- Session 6 - Window functions and CTEs on the DVF sales
-- =============================================================================
--
-- Warehouse : BigQuery, dataset dvf_raw, table ventes (61 027 rows)
-- Date      : 2026-09-05
--
-- THE ONE IDEA OF THIS FILE
--
--   GROUP BY : 61 027 rows -> 83 rows. The detail DISAPPEARS.
--   OVER     : 61 027 rows -> 61 027 rows. The detail STAYS.
--
-- A window function answers questions of the shape "this sale, compared to the
-- other sales in its commune" - questions GROUP BY cannot answer, because it
-- destroyed the sale being asked about.
--
-- Inside OVER():
--   PARTITION BY  the slicing - which rows the computation covers.
--   ORDER BY      the ordering INSIDE the window - required for ranks, LAG,
--                 running totals. Useless for a plain average.
--
-- THE THREE FILTERING CLAUSES
--   WHERE   filters ROWS      (before grouping)
--   HAVING  filters GROUPS    (after grouping)
--   QUALIFY filters WINDOWS   (after the window is computed)
--
-- Execution order:
--   FROM -> WHERE -> GROUP BY -> HAVING -> WINDOW -> QUALIFY -> SELECT -> ORDER BY
--
-- Careful: execution order and ALIAS VISIBILITY are two different rules.
-- Execution order says what EXISTS (WHERE cannot see an aggregate that has not
-- been computed - a semantic impossibility). Alias visibility says what may be
-- NAMED, and it is a syntactic convenience: BigQuery substitutes aliases in
-- GROUP BY, HAVING, QUALIFY and ORDER BY - but never inside SELECT itself.
--
-- AGGREGATE OR WINDOW? The distinction that cost an hour:
--   APPROX_QUANTILES(x, 2)[OFFSET(1)]   is an AGGREGATE -> goes with GROUP BY
--   PERCENTILE_CONT(x, 0.5) OVER (...)  is WINDOW-ONLY  -> no GROUP BY possible
-- There is no aggregate form of PERCENTILE_CONT in BigQuery.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- F1. The same query, more readable
--
-- Question: rewrite session 5's E6 using a CTE.
-- Expected: 83 rows, identical to E6.
-- -----------------------------------------------------------------------------

WITH stats_commune AS (
    SELECT
        nom_commune,
        COUNT(*) AS nb_ventes,
        ROUND(APPROX_QUANTILES(SAFE_DIVIDE(prix, surface_bati), 2)[OFFSET(1)], 0) AS prix_m2_median
    FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
    GROUP BY nom_commune
)

SELECT nom_commune, nb_ventes, prix_m2_median
FROM stats_commune
WHERE nb_ventes >= 100
ORDER BY prix_m2_median DESC;

-- WHY A PLAIN WHERE WORKS HERE, WHERE HAVING WAS NEEDED YESTERDAY
--
-- A CTE runs COMPLETELY, as a full query, before the outer query starts. It
-- goes through its own cycle FROM -> WHERE -> GROUP BY -> HAVING -> SELECT.
-- When it finishes, its result is an ORDINARY TABLE. So by the time the outer
-- query runs, nb_ventes is no longer an aggregate being computed: it is a
-- plain filled column. Filtering it with WHERE is filtering normal rows.
--
-- Each level has its own execution order. Stacking CTEs stacks complete cycles.
-- That is why a dbt project reads so well - each model finishes before the next
-- one reads it.
--
-- MISTAKE MADE: splitting the work in the wrong place. The first attempt put
-- only the median in the CTE and left COUNT(*) and GROUP BY outside. A CTE must
-- produce a COMPLETE TABLE THAT DESERVES ITS NAME: "stats_commune" means one
-- row per commune with ALL its statistics.
--
-- SECOND MISTAKE, the dangerous kind: WHERE prix_m2_median >= 100 instead of
-- WHERE nb_ventes >= 100. No commune has a median under 100 EUR/sqm, so the
-- filter removed nothing - and returned a wrong result WITHOUT ANY ERROR.
-- A syntax error stops you; a wrong-column error hands you a plausible lie.


-- -----------------------------------------------------------------------------
-- F2. The click: computing on a group without losing the rows
--
-- Question: for EACH sale, its price per sqm, its commune's median price per
-- sqm, and the ratio between the two.
-- Expected: 61 027 rows. Getting 83 means a GROUP BY slipped in.
-- -----------------------------------------------------------------------------

WITH ventes_m2 AS (
    -- Level 1: the price per sqm of each sale.
    SELECT
        nom_commune,
        SAFE_DIVIDE(prix, surface_bati) AS prix_m2
    FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
),

avec_mediane AS (
    -- Level 2: prix_m2 is now an ordinary column, so the window can use it
    -- without recomputing it.
    SELECT
        nom_commune,
        prix_m2,
        PERCENTILE_CONT(prix_m2, 0.5) OVER (PARTITION BY nom_commune) AS prix_m2_commune
    FROM ventes_m2
)

-- Level 3: both columns exist, the ratio is a plain division.
SELECT
    nom_commune,
    prix_m2,
    prix_m2_commune,
    SAFE_DIVIDE(prix_m2, prix_m2_commune) AS rapport
FROM avec_mediane;

-- A ratio of 1.4 means "this sale went 40% above its own commune's median".
-- That column existed in no source data, and not one row was lost creating it.
--
-- SYNTAX, three traps for beginners:
--   - WITH is written ONCE. Following CTEs are chained with a comma.
--   - No comma before the final SELECT.
--   - Each level only sees the previous one. A column dropped at one level is
--     lost for every level after it.
--
-- MISTAKE MADE: treating a CTE like a variable - writing FROM the original
-- table in the outer query and reaching for `prix.prix_m2` as if the CTE were
-- an object with attributes. That is a Python reflex. A CTE IS A TABLE: you
-- read FROM it, and it must carry every column the next level needs.
--
-- WHY THE ALIAS COULD NOT BE REUSED: PERCENTILE_CONT(prix_m2, ...) inside the
-- same SELECT that defines prix_m2 fails. All SELECT expressions are evaluated
-- at the same stage; none can see another's alias. The CTE exists to solve
-- exactly this.


-- -----------------------------------------------------------------------------
-- F3. Top N per group - the classic SQL interview question
--
-- Question: for the five communes with the most sales, the three most
-- expensive sales of each.
-- Expected: 15 rows.
-- -----------------------------------------------------------------------------

WITH top_5_communes AS (
    SELECT nom_commune
    FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
    GROUP BY nom_commune
    ORDER BY COUNT(*) DESC, nom_commune
    LIMIT 5
)

SELECT
    nom_commune,
    prix,
    surface_bati,
    ROW_NUMBER() OVER (PARTITION BY nom_commune ORDER BY prix DESC, id_mutation) AS rang
FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
WHERE nom_commune IN (SELECT nom_commune FROM top_5_communes)
QUALIFY rang <= 3;

-- Computing the five communes instead of hard-coding them keeps the query
-- correct when the data changes. A hard-coded list becomes silently wrong the
-- day the ranking moves.
--
-- DETERMINISM - the serious point. Without a TIE-BREAKER, two sales at exactly
-- the same price get ranked arbitrarily, and possibly differently between runs
-- (parallel execution, physical data order, engine version). In a nightly
-- pipeline that is poison: you can no longer tell a real data change from
-- randomness. It is the direct enemy of idempotence.
--
--   Rule: a window ORDER BY used for ranking always ends with a column that
--   breaks ties. Here, id_mutation.
--
-- The rule generalises: ANY "ORDER BY ... LIMIT n" without a total order is a
-- disguised coin flip. The top_5_communes CTE above therefore ends with
-- ", nom_commune".
--
-- A tie-breaker must VARY INSIDE the partition. Adding id_mutation to a window
-- partitioned BY id_mutation breaks nothing at all - it is constant there.
--
-- THE RANKING FAMILY, on prices 500k, 400k, 400k:
--   ROW_NUMBER  -> 1, 2, 3   never ties, one rank per row
--   RANK        -> 1, 2, 2, 4  ties share, next rank skips
--   DENSE_RANK  -> 1, 2, 2, 3  ties share, no skip
-- For deduplication it is always ROW_NUMBER: only it guarantees exactly one
-- row per group.
--
-- QUALIFY accepts the alias `rang` while SELECT cannot see its own aliases -
-- and writing the window once means the tie-breaker applies everywhere.
--
-- DATA QUALITY NOTE: the top Bordeaux sale is 4 200 000 EUR for 120 sqm, i.e.
-- 35 000 EUR/sqm against a commune median of 4 660. Possible for a mansion, but
-- more likely an UNDER-REPORTED AREA - a building sold whole with only part
-- declared as living space. Extreme values are where dirty data hides; always
-- look at the top and bottom of a ranking before trusting a table.


-- -----------------------------------------------------------------------------
-- F4. Deduplication - the real use of ROW_NUMBER
--
-- Question: keep exactly one row per id_mutation and count the result.
-- Expected: 61 027 - the table is already clean, so the guard must be neutral.
-- -----------------------------------------------------------------------------

WITH ligne_unique AS (
    SELECT *
    FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
    QUALIFY ROW_NUMBER() OVER (PARTITION BY id_mutation ORDER BY date_mutation DESC) = 1
)

SELECT COUNT(*) AS nb_ventes
FROM ligne_unique;

-- Writing a guard and PROVING IT IS NEUTRAL on healthy data is a data
-- engineering move, and it is literally what a staging model does.
--
-- MISTAKE MADE: computing `rang` and never filtering on it. The query then
-- counts every row, exactly like a plain COUNT(*) - and returns 61 027, which
-- looks right. On a table with 500 duplicates it would have answered 61 527 in
-- perfect serenity. A deduplication query that does not filter is a query that
-- lies.
--
-- THE DIAGNOSTIC that reveals it: SELECT MAX(rang) on the CTE. If it equals 1,
-- no id_mutation appears twice. Anything above 1 is the SIZE OF THE LARGEST
-- duplicate group - not a count of duplicates.
--
-- THE CANONICAL DUPLICATE FINDER, a first reflex on any unknown table:
--
--   SELECT id_mutation, COUNT(*) AS n
--   FROM `...ventes`
--   GROUP BY id_mutation
--   HAVING COUNT(*) > 1
--   ORDER BY n DESC
--
-- Zero rows = the key really is a key. This proves id_mutation is unique in
-- our table - exactly the `unique` test dbt automates in session 9.
--
-- NOT DISTINCT: DISTINCT cannot choose WHICH row to keep. ROW_NUMBER can.
--
-- PORTABILITY: QUALIFY does not exist in PostgreSQL. There, the same thing is
-- written with a CTE and an outer WHERE rang = 1. Worth saying out loud in an
-- interview.


-- -----------------------------------------------------------------------------
-- F5. Year-on-year change, per commune
--
-- Question: for the ten busiest communes, the median price per sqm per year,
-- the previous year's value, and the percentage change.
-- Expected: 30 rows.
-- -----------------------------------------------------------------------------

WITH communes_actives AS (
    SELECT nom_commune
    FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
    GROUP BY nom_commune
    ORDER BY COUNT(*) DESC, nom_commune
    LIMIT 10
),

par_annee AS (
    SELECT
        nom_commune,
        EXTRACT(YEAR FROM PARSE_DATE('%Y-%m-%d', date_mutation)) AS annee,
        ROUND(APPROX_QUANTILES(SAFE_DIVIDE(prix, surface_bati), 2)[OFFSET(1)], 0) AS prix_m2_median
    FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
    WHERE nom_commune IN (SELECT nom_commune FROM communes_actives)
    GROUP BY nom_commune, annee
),

avec_precedent AS (
    SELECT
        nom_commune,
        annee,
        prix_m2_median,
        LAG(prix_m2_median) OVER (PARTITION BY nom_commune ORDER BY annee) AS prix_m2_precedent
    FROM par_annee
)

SELECT
    nom_commune,
    annee,
    prix_m2_median,
    prix_m2_precedent,
    ROUND(100 * SAFE_DIVIDE(prix_m2_median - prix_m2_precedent, prix_m2_precedent), 1) AS variation_pct
FROM avec_precedent
ORDER BY nom_commune, annee;

-- Four levels, each adding exactly ONE thing: the selected communes, the yearly
-- aggregate, the previous value, the change.
--
-- THE MISTAKE THAT COST AN HOUR - two of them, actually.
--
-- 1. GRANULARITY. The first attempt did GROUP BY nom_commune, annee then
--    LIMIT 30, expecting "10 communes x 3 years". A LIMIT on commune-year pairs
--    is NOT the ten busiest communes: Cenon and Gradignan appeared (their 2022
--    beats a top-10 commune's 2024) while Le Bouscat only kept 2022.
--
--    THE GRANULARITY OF THE FILTER IS NOT THE GRANULARITY OF THE RESULT.
--    "Which communes?" answers over the whole period, one row per commune.
--    "How did each year go?" answers per commune AND year. Two questions, two
--    levels. Merging them destroys the first.
--
-- 2. PERCENTILE_CONT with GROUP BY. Structurally impossible - it is window-only.
--    No amount of effort could have fixed that query. When an error survives
--    three serious attempts, the likely hypothesis is no longer "I am doing it
--    wrong" but "something I believe to be true is not".
--
-- LAG must be PARTITIONED BY commune, otherwise it compares the first year of
-- Merignac to the last year of Bordeaux.
--
-- The first year of each commune has a NULL previous value. That is correct -
-- there is no previous row. SAFE_DIVIDE propagates the NULL cleanly.
--
-- RESULT - richer than the session 5 aggregate:
--
--   2024 IS THE TURNING POINT, NOT 2022. In 2023 half the communes were still
--   rising: Arcachon +4.5%, Le Bouscat +2.3%, Libourne +1.1%, Begles +0.7%,
--   Pessac +0.4%. In 2024 ALL TEN fall, from -2.6% to -10.0%.
--
--   The session 5 aggregate ("-7% over three years") suggested a steady slope.
--   The truth is a flat year followed by a drop. Same lesson as before - "broken
--   down by what?" - except this time it was TIME that had been flattened.
--
--   THE COAST RESISTS, THE CITY CENTRE CORRECTS. Bordeaux loses 9.2% over the
--   period and starts falling in 2023. La Teste-de-Buch loses 3%. Arcachon rises
--   then falls back to roughly its 2022 level. Second homes and primary homes
--   are two different markets inside the same dataset.
--
-- WHAT IT MEANS FOR THE MODEL: it learns on 2022-2023, where several communes
-- were still rising, and predicts 2024, where everything falls. It has no notion
-- of market regime and cannot extrapolate one - trees never extrapolate. A good
-- part of the 15.5% median error comes from there, and it can now be said with
-- per-commune, per-year numbers.


-- -----------------------------------------------------------------------------
-- F6. Quintiles in one function
--
-- Question: split the sales into five price quintiles; per quintile, the number
-- of sales, the minimum and maximum price, and the median area.
-- Expected: 5 rows.
-- -----------------------------------------------------------------------------

WITH quintiles AS (
    SELECT
        prix,
        surface_bati,
        NTILE(5) OVER (ORDER BY prix) AS quintile
    FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
)

SELECT
    quintile,
    COUNT(*)                                     AS nb_ventes,
    MIN(prix)                                    AS prix_min,
    MAX(prix)                                    AS prix_max,
    APPROX_QUANTILES(surface_bati, 2)[OFFSET(1)] AS surface_mediane
FROM quintiles
GROUP BY quintile
ORDER BY quintile;

-- Result:
--   Q1  12 206   10 000 -   147 000 EUR    45 sqm
--   Q2  12 206  147 000 -   207 900 EUR    57 sqm
--   Q3  12 205  207 900 -   284 000 EUR    71 sqm
--   Q4  12 205  284 000 -   407 110 EUR    86 sqm
--   Q5  12 205  407 280 - 5 000 000 EUR   110 sqm
--
-- EQUAL COUNTS, VERY UNEQUAL WIDTHS. Q1 spans 137k EUR, Q5 spans 4.6M - 33
-- times wider. That is the definition of a quantile: equal-sized buckets of
-- ROWS, not equal ranges of value. 61 027 / 5 = 12 205.4, so NTILE gives the
-- remainder to the first buckets.
--
-- TIES STRADDLE BOUNDARIES: Q1's max is 147 000 and Q2's min is also 147 000.
-- Not a bug - many sales happen at round prices, and NTILE prioritises equal
-- counts over clean boundaries, so identical values can land in different
-- quintiles. A real trap if a quantile ever becomes a business rule.
--
-- A PERCENTILE HAS NO MEANING WITHOUT ITS POPULATION. Session 4's error
-- analysis put the first quintile boundary at 137 921 EUR - computed on the
-- TEST SET, i.e. 2024 only. Here it is 147 000 EUR, computed on all three
-- years, which include the more expensive 2022-2023. All four boundaries shift
-- up consistently (196 000 -> 207 900, 266 500 -> 284 000, 375 500 -> 407 110).
-- "The first quintile stops at 138k" is an incomplete sentence; "...on 2024
-- sales" is a true one.
--
-- WHY THE MODEL FAILS MOST ON Q1: median area 45 sqm - studios and small flats.
-- A 20 000 EUR error is 15% on a 45 sqm flat and 4% on a 500 000 EUR house.
-- The percentage error mechanically explodes at the bottom of the distribution.


-- =============================================================================
-- THE INTERVIEW SENTENCE FOR THIS SESSION
-- =============================================================================
--
--   "A GROUP BY collapses rows: after grouping by commune I have 83 rows and
--    the individual sales are gone. A window function computes over the same
--    slice but keeps every row - PARTITION BY says which rows the computation
--    covers. That is how I compared each sale to the median of its own commune
--    on 61 027 rows without losing one. And I use ROW_NUMBER partitioned by the
--    key to deduplicate, because unlike DISTINCT it lets me choose which row
--    survives."
-- =============================================================================
