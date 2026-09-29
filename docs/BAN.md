# BAN locale - V6

## Deux usages

La BAN locale sert maintenant a deux choses :

1. rechercher une adresse ;
2. resoudre un couple code postal / commune.

Aucun appel distant n'est requis pendant le scoring.

## Import

```bash
docker compose run --rm ban-loader --departments 13
```

Plusieurs departements :

```bash
docker compose run --rm ban-loader --departments 13 75 69
```

## Import atomique

```text
CSV
 |
 v
ban_staging
 |
 v
validation
 |
 v
BEGIN IMMEDIATE
 |
 +-- suppression ancien departement
 +-- insertion nouveau departement
 +-- mise a jour metadata
 |
 v
COMMIT
```

En cas d'erreur, la transaction est annulee et l'ancienne version reste disponible.

## Tables

`ban_addresses` contient notamment : id_ban, numero, rep, nom_voie, nom_voie_norm, code_postal, code_insee, nom_commune, nom_commune_norm, lon, lat, departement.

`ban_staging` sert de zone temporaire.

`metadata` contient le nombre total de lignes, les departements charges et les dates de mise a jour.

## Resolution de localite

Methode V6 : `resolve_locality(postcode, city_input)`.

Le moteur charge les communes distinctes du code postal et les classe par similarite.

Statuts :

- `EXACT`
- `TYPO_CORRECTED`
- `AMBIGUOUS`
- `NOT_FOUND`
- `UNAVAILABLE`

Champs de sortie : postcode, city_input, city_norm, city_label, city_code, similarity, candidate_count.

Cette resolution alimente `CanonicalAddress.city_canonical`, `city_code`, `locality_status` et `locality_score`.

## Recherche d'adresse

Reduction des candidats :

1. CP + numero
2. CP + voie
3. commune + numero
4. commune + voie

Le classement prend en compte voie, libelle, numero, suffixe, CP et commune.

## Statuts d'existence

- `CONFIRMED_HOUSENUMBER`
- `PLAUSIBLE_HOUSENUMBER`
- `CONFIRMED_STREET`
- `PLAUSIBLE_STREET`
- `WEAK`
- `NOT_FOUND`
- `INSUFFICIENT_QUERY`
- `UNAVAILABLE`

## Lecture seule

Pendant le scoring, SQLite est ouvert en lecture seule.

La base est conservee dans le volume Docker `ban_data`.
