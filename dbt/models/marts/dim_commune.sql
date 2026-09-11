SELECT
{{ dbt_utils.generate_surrogate_key(['nom_commune']) }} AS commune_id,
nom_commune,
MIN(code_postal) AS code_postal
FROM {{ref('stg_ventes')}}
GROUP BY nom_commune