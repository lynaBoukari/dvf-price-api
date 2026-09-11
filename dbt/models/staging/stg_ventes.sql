
SELECT
  id_mutation, prix, nom_commune, nb_logements, nb_lots, surface_bati, surface_terrain, longitude, latitude, type_bien,
  PARSE_DATE('%Y-%m-%d', date_mutation) AS date_mutation,
  LPAD(CAST(CAST(code_postal AS INT64) AS STRING), 5, '0') AS code_postal,
  CAST(nb_pieces AS INT64) AS nb_pieces
FROM {{source('dvf_raw', 'ventes')}}
QUALIFY ROW_NUMBER() over (PARTITION BY id_mutation ORDER BY date_mutation DESC) = 1