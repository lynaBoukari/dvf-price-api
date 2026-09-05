-- =============================================================================
-- Session 5 - First exploration of the DVF sales in BigQuery
-- =============================================================================
--
-- Warehouse : BigQuery (sandbox), region europe-west1
-- Dataset   : dvf_raw
-- Table     : ventes  (61 027 rows, loaded from data/processed/ventes_33.parquet)
-- Date      : 2026-09-04
--
-- Goal of this file: prove that SQL and pandas agree on the same dataset,
-- and keep the queries that are worth re-running.
--
-- Naming note: the dataset is called `dvf_raw` but it holds ALREADY CLEANED
-- data, which is a known inconsistency. Session 7 fixes it: the raw DVF CSV
-- files will land in `dvf_raw`, and the cleaning will be rebuilt as dbt models
-- in `dvf_staging` and `dvf_marts`.
--
-- The fully qualified table name below is hard-coded on purpose. From session 7
-- on, dbt replaces it with ref('ventes'), which is what makes the project
-- portable between environments.
-- =============================================================================


-- -----------------------------------------------------------------------------
-- E1. Control count
--
-- Question: how many rows are in the table?
-- Expected: 61 027, the exact number written by build.py.
-- -----------------------------------------------------------------------------

SELECT COUNT(*) AS nb_ventes
FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`;

-- Result: 61 027. The load is intact.
--
-- COUNT(*) vs COUNT(column): COUNT(*) counts ROWS, COUNT(column) counts
-- NON-NULL VALUES of that column. Every column of this table is NULLABLE, so
-- COUNT(id_mutation) could silently under-count and make a healthy load look
-- broken. For a volume check, always COUNT(*).


-- -----------------------------------------------------------------------------
-- E1b. Turning that remark into a data test
--
-- Question: is any id_mutation null?
-- Expected: 0. This is a hand-written version of the dbt `not_null` test
-- that session 9 will automate.
-- -----------------------------------------------------------------------------

SELECT COUNT(*) - COUNT(id_mutation) AS ids_manquants
FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`;


-- -----------------------------------------------------------------------------
-- E2. Median price and median living area
--
-- Question: the median price and the median built area over the whole table.
-- Expected: the two values logged by build.py ("Median price", "Median
-- living area"). This is the pandas / SQL equivalence check.
-- -----------------------------------------------------------------------------

SELECT
    APPROX_QUANTILES(prix, 2)[OFFSET(1)]         AS prix_median,
    APPROX_QUANTILES(surface_bati, 2)[OFFSET(1)] AS surface_mediane
FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`;

-- Result: 242 500 EUR for 75 sqm.
--
-- Three things to remember here.
--
-- 1. BigQuery has no MEDIAN(). APPROX_QUANTILES(x, 2) splits the distribution
--    into 2 parts, which produces 3 boundaries: it returns the ARRAY
--    [min, median, max], not a scalar.
--
-- 2. Array indexing has two forms: OFFSET starts at 0, ORDINAL starts at 1.
--    The median is [OFFSET(1)] or [ORDINAL(2)]. Mixing them silently returns
--    the minimum or the maximum. Pick one convention and keep it.
--
-- 3. Why "APPROX"? An exact quantile requires sorting the whole dataset, which
--    does not scale to billions of rows, so BigQuery uses a sketch algorithm.
--    The exact function exists (PERCENTILE_CONT) but it is a window function.
--    Trading a little accuracy for a lot of speed, knowingly, is a very
--    data-engineering decision.


-- -----------------------------------------------------------------------------
-- E3. Houses versus flats
--
-- Question: per property type, the number of sales, the median price, and the
-- median price per square metre.
-- Expected: 2 rows.
-- -----------------------------------------------------------------------------

SELECT
    type_bien,
    COUNT(*)                                             AS nb_ventes,
    APPROX_QUANTILES(prix, 2)[OFFSET(1)]                 AS prix_median,
    ROUND(APPROX_QUANTILES(prix / surface_bati, 2)[OFFSET(1)], 0) AS prix_m2_median
FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
GROUP BY type_bien;

-- Result:
--   Maison       34 099   309 750 EUR   3 466 EUR/sqm
--   Appartement  26 928   188 500 EUR   3 830 EUR/sqm
--
-- Reading the result. A house costs MORE in total but LESS per square metre.
-- This is a composition effect, not a contradiction: flats are downtown, where
-- the square metre is scarce and expensive; houses are on the outskirts, where
-- land is cheaper but you buy 120 sqm instead of 55. Total price follows area,
-- price per sqm follows location.
--
-- The aggregation trap: an aggregate over a heterogeneous group hides the
-- variable that actually explains the result - here, geography. Whenever an
-- aggregate figure is put in front of you, the reflex is "broken down by what?".
--
-- It also validates the model after the fact: if type_bien carried no signal,
-- the two rows would be identical. They differ, and in opposite directions.
--
-- The median of ratios is NOT the ratio of medians. The division must happen
-- row by row, INSIDE the aggregate function - which works because an aggregate
-- accepts an expression, not just a column name.
--
-- 34 099 + 26 928 = 61 027. Sub-totals adding up to the total proves no sale
-- has a null type_bien. Free check, worth doing every time.
--
-- Defensive note: this division never fails because filter_area_range (written
-- back in session 2) guarantees an area between 9 and 1000 sqm. BigQuery RAISES
-- AN ERROR on division by zero, it does not return NULL. In production, where
-- the source can change without warning, write SAFE_DIVIDE(prix, surface_bati)
-- instead: it returns NULL rather than bringing the job down.


-- -----------------------------------------------------------------------------
-- E4. The ten busiest communes
--
-- Question: the ten communes with the most sales, with their median price
-- per square metre.
-- -----------------------------------------------------------------------------

SELECT
    nom_commune,
    COUNT(*) AS nb_ventes,
    ROUND(APPROX_QUANTILES(SAFE_DIVIDE(prix, surface_bati), 2)[OFFSET(1)], 0) AS prix_m2_median
FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
GROUP BY nom_commune
ORDER BY nb_ventes DESC
LIMIT 10;

-- Result (top 3): Bordeaux 13 620 sales at 4 660 EUR/sqm, Merignac 3 120 at
-- 3 801, Pessac 1 947 at 3 924. Arcachon appears 7th at 8 000 EUR/sqm.
--
-- Bordeaux alone is 13 620 / 61 027 = 22% of the dataset. One commune out of
-- hundreds holds a fifth of the transactions. Honest consequence: the model is
-- largely a Bordeaux model and will be weakest in rural communes. Better to
-- state that limit in an interview than to have it found for you.
--
-- Note: ORDER BY can use an alias defined in the SELECT, because ORDER BY runs
-- AFTER SELECT. See the execution order in E6.
--
-- Reflex: a suspiciously round median (Arcachon at exactly 8000.0) deserves
-- thirty seconds of checking. Here it is legitimate - with an odd number of
-- sales the median is a real transaction of the dataset - but the instinct
-- "this number is too clean to be true" will one day save a delivery.


-- -----------------------------------------------------------------------------
-- E5. Yearly evolution
--
-- Question: per year, the number of sales and the median price per sqm.
-- -----------------------------------------------------------------------------

SELECT
    EXTRACT(YEAR FROM PARSE_DATE('%Y-%m-%d', date_mutation)) AS annee,
    COUNT(*) AS nb_ventes,
    ROUND(APPROX_QUANTILES(SAFE_DIVIDE(prix, surface_bati), 2)[OFFSET(1)], 0) AS prix_m2_median
FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
GROUP BY annee
ORDER BY annee;

-- Result:
--   2022   25 133 sales   3 750 EUR/sqm
--   2023   19 165 sales   3 687 EUR/sqm
--   2024   16 729 sales   3 476 EUR/sqm
--
-- THIS IS THE MOST IMPORTANT RESULT OF THE SESSION.
--
-- Volume dropped by a THIRD in two years while the price per sqm only fell 7%.
-- That is the real signature of the French property market after interest rates
-- rose: sellers refuse to cut prices, so transactions stop instead. Volume
-- adjusts before prices do.
--
-- This is the real justification for the temporal split, and it beats the
-- textbook answer by a mile:
--
--   "My model learns on 2022-2023 and predicts 2024. Between the two, the
--    median price per sqm dropped 7% and volume fell by a third. A random
--    split would have mixed the two regimes and flattered my metrics; the
--    temporal split measures what actually matters - performance on a market
--    the model has not seen."
--
-- That is concept drift, measured on my own data, with numbers.
--
-- TO VERIFY before telling this story in an interview: check that the 2024 file
-- covers the full year. DVF publishes per semester, and a truncated year would
-- mechanically explain part of the volume drop.
--
-- TYPE DEBT: PARSE_DATE is needed here only because date_mutation is a STRING.
-- The staging layer (session 7) makes it a real DATE, after which this becomes
-- EXTRACT(YEAR FROM date_mutation). The before/after is the demonstration of
-- what a staging layer is for.


-- -----------------------------------------------------------------------------
-- E6. A ranking you can trust
--
-- Question: communes with at least 100 sales, ranked by median price per sqm.
-- -----------------------------------------------------------------------------

SELECT
    nom_commune,
    COUNT(*) AS nb_ventes,
    ROUND(APPROX_QUANTILES(SAFE_DIVIDE(prix, surface_bati), 2)[OFFSET(1)], 0) AS prix_m2_median
FROM `project-119b887b-87ca-43ee-bf0.dvf_raw.ventes`
GROUP BY nom_commune
HAVING COUNT(*) >= 100
ORDER BY prix_m2_median DESC;

-- Result: 83 communes.
--   Top:    Lege-Cap-Ferret 10 602 EUR/sqm (517 sales), Arcachon 8 000 (1 329),
--           Andernos 5 619 (678), La Teste 5 259 (1 294), Lacanau 5 256 (694)
--   Bordeaux only ranks 8th, at 4 660.
--   Bottom: Sainte-Foy-la-Grande 896 EUR/sqm (126 sales)
--
-- Three readings.
--
-- 1. The coast beats the metropolis. The whole top of the ranking is the
--    Arcachon basin and the ocean. Geography is not simply "city vs
--    countryside": there is a third pole, the seaside.
--
-- 2. The ratio is 1 to 12, from 896 to 10 602 EUR/sqm. Far larger than the
--    house/flat gap (1 to 1.1) or the year-on-year gap (1 to 1.08). LOCATION IS
--    BY FAR THE STRONGEST PREDICTOR - which validates keeping longitude and
--    latitude as features: a tree can split the plane on them and rebuild this
--    map on its own.
--
-- 3. How I would improve the model: add the commune's median price per sqm as a
--    feature instead of making the tree rediscover it from raw coordinates.
--    THE TRAP TO MENTION UNPROMPTED: that median must be computed on the
--    TRAINING SET ONLY. Computing it over the whole dataset leaks 2024
--    information into training - target leakage, classic and discreet. That
--    table of medians per commune is exactly the dim_commune of session 8.
--
-- WHY HAVING EXISTS - the logical execution order of a query:
--
--     FROM -> WHERE -> GROUP BY -> HAVING -> SELECT -> ORDER BY
--
-- WHERE runs BEFORE the grouping: at that point the groups do not exist yet, so
-- COUNT(*) is meaningless and the engine refuses it. HAVING runs AFTER: the
-- groups are formed and their aggregates computed.
--
--   WHERE filters ROWS. HAVING filters GROUPS.
--
-- The same order explains why aliases work in ORDER BY (it runs after SELECT).
--
-- THE SMALL SAMPLE PROBLEM, seen by running the query with <= 100 by mistake:
-- Daubeze, 1 sale, "median" 246 EUR/sqm. A median over one sale is that sale -
-- an anecdote with a statistical name. The 100 threshold is arbitrary, and that
-- is fine: what matters is being able to say why a threshold exists and what
-- happens below it.


-- =============================================================================
-- OLTP vs OLAP - the culture question, asked in almost every DE interview
-- =============================================================================
--
-- OLTP - OnLine Transaction Processing. The database that runs an application.
--   Many tiny operations per second, each touching very few rows, answering in
--   milliseconds. ROW storage, NORMALIZED schema, INDEXES on keys.
--   PostgreSQL, MySQL, Oracle.
--
-- OLAP - OnLine Analytical Processing. The warehouse.
--   Few queries, each scanning millions of rows over a handful of columns, in
--   seconds. COLUMNAR storage, DENORMALIZED schema, PARTITIONING and CLUSTERING
--   instead of indexes. BigQuery, Snowflake, Redshift, DuckDB.
--
-- Felt directly today: query E2 read 2 columns out of 13. In columnar storage
-- the other 11 were never touched. In row storage every byte of every row would
-- have been read. And nom_commune is repeated on 13 620 Bordeaux rows - a sin
-- in OLTP design, deliberate in OLAP.
--
-- Why not run analytics on production? Two reasons, both needed:
--   - LOAD: one query scanning millions of rows saturates the memory and disks
--     of a database whose job is to answer in 5 ms. You do not slow down your
--     report, you slow down the product, for every user.
--   - STRUCTURE: even if it survived it would be slow - row storage, normalized
--     schema full of joins, no partitioning. Wrong tool for the question.
--
-- And that is the job: a data engineer is the bridge between the two worlds -
-- extract from OLTP, transform, load into OLAP. Here the source is a public
-- file rather than a production database, but the shape is identical.
-- =============================================================================

