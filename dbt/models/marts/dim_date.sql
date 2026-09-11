WITH bornes AS (
    -- On arrondit aux années complètes : le calendrier couvre
    -- du 1er janvier de la première année au 31 décembre de la dernière.
    SELECT
        DATE_TRUNC(MIN(date_mutation), YEAR) AS date_min,
        LAST_DAY(MAX(date_mutation), YEAR)   AS date_max
    FROM {{ ref('stg_ventes') }}
),

calendrier AS (
    SELECT jour AS date_id
    FROM bornes, UNNEST(GENERATE_DATE_ARRAY(date_min, date_max)) AS jour
)

SELECT
    date_id,
    EXTRACT(YEAR      FROM date_id) AS annee,
    EXTRACT(QUARTER   FROM date_id) AS trimestre,
    EXTRACT(MONTH     FROM date_id) AS mois,

    CASE EXTRACT(MONTH FROM date_id)  WHEN 1 THEN 'janvier'
    WHEN 2 THEN 'février'
    WHEN 3 THEN 'mars'
    WHEN 4 THEN 'avril'
    WHEN 5 THEN 'mai'
    WHEN 6 THEN 'juin'
    WHEN 7 THEN 'juillet'
    WHEN 8 THEN 'août'
    WHEN 9 THEN 'septembre'
    WHEN 10 THEN 'octobre'
    WHEN 11 THEN 'novembre'
    WHEN 12 THEN 'décembre'
    END AS nom_mois,
    EXTRACT(DAYOFWEEK FROM date_id) AS jour_semaine
FROM calendrier