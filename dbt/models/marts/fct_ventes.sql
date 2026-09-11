SELECT
v.id_mutation,
v.date_mutation AS date_id,
c.commune_id ,
v.prix, v.surface_bati, v.surface_terrain, v.nb_pieces, v.nb_lots, v.type_bien,
SAFE_DIVIDE(v.prix, v.surface_bati) AS prix_m2,

FROM {{ ref('stg_ventes') }} AS v

LEFT JOIN {{ ref('dim_commune') }} AS c
    ON v.nom_commune = c.nom_commune

