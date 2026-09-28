# BAN locale

## Objectif

La Base Adresse Nationale est utilisee comme couche locale de verification et de rapprochement.

Le scoring ne fait pas d'appel vers une API BAN distante.

## Source des donnees

Le chargeur utilise les fichiers officiels BAN `CSV avec identifiants` :

```text
https://adresse.data.gouv.fr/data/ban/adresses/latest/csv-with-ids
```

Pour un departement, le script construit une URL de la forme :

```text
.../adresses-with-ids-13.csv.gz
```

## Import Docker

Un departement :

```bash
docker compose run --rm ban-loader --departments 13
```

Plusieurs departements :

```bash
docker compose run --rm ban-loader --departments 13 75 69
```

Conserver le fichier telecharge :

```bash
docker compose run --rm ban-loader --departments 13 --keep-raw
```

## Import d'un fichier local

Le script accepte aussi :

```bash
python scripts/download_ban.py \
  --db /tmp/ban.sqlite \
  --from-file /chemin/adresses-with-ids-13.csv
```

Les formats `.csv` et `.csv.gz` sont supportes.

## Schema SQLite

### ban_addresses

Colonnes principales :

- `id_ban`
- `numero`
- `rep`
- `nom_voie`
- `nom_voie_norm`
- `code_postal`
- `code_insee`
- `nom_commune`
- `nom_commune_norm`
- `lon`
- `lat`
- `label`
- `departement`
- `source_file`.

### ban_staging

Meme structure que `ban_addresses`.

Elle sert a charger un nouveau departement avant publication.

### metadata

Contient notamment :

- `rows_total`
- `departments_json`
- `last_update`
- `department_<DEP>_loaded_at`.

Ces valeurs permettent a `/health` d'eviter un `COUNT(*)` complet a chaque appel.

## Index SQLite

Le chargeur cree des index sur :

- `code_postal, numero`
- `nom_commune_norm, numero`
- `code_postal, nom_voie_norm`
- `nom_commune_norm, nom_voie_norm`
- `departement`.

## Import atomique

Le cycle est :

```text
fichier
  |
  v
validation des colonnes
  |
  v
ban_staging
  |
  v
validation du nombre de lignes
  |
  v
BEGIN IMMEDIATE
  |
  +-- suppression ancien departement
  +-- insertion nouveau departement
  +-- controle nombre de lignes
  +-- mise a jour metadata
  |
  v
COMMIT
```

En cas d'erreur pendant la publication :

```text
ROLLBACK
```

L'ancienne version du departement reste alors en place.

En cas d'erreur pendant le staging, la table de staging du departement est nettoyee.

## Recherche locale

Le moteur essaie de reduire le jeu de candidats avant fuzzy matching.

Ordre general :

1. code postal + numero ;
2. code postal + voie ;
3. commune + numero ;
4. commune + voie.

Pour les recherches par voie :

- correspondance exacte ;
- prefixe ;
- recherche par token d'ancrage.

Le nombre de candidats est limite par defaut a 250.

Le resultat est ensuite classe avec un score local combinant notamment :

- similarite de voie ;
- similarite du libelle ;
- numero ;
- suffixe ;
- code postal ;
- commune.

## existence_status

Valeurs principales :

### CONFIRMED_HOUSENUMBER

Numero, suffixe et voie suffisamment coherents.

### PLAUSIBLE_HOUSENUMBER

Numero et voie plausibles, mais evidence plus faible.

### CONFIRMED_STREET

Recherche sans numero, voie fortement confirmee.

### PLAUSIBLE_STREET

Voie plausible.

### WEAK

Candidat trouve mais trop faible.

### NOT_FOUND

Aucun candidat dans le sous-ensemble recherche.

### INSUFFICIENT_QUERY

Informations insuffisantes pour une recherche bornee.

### UNAVAILABLE

Base locale indisponible.

## Champs de resultat

`LocalBanResult` contient notamment :

- `database_status`
- `existence_status`
- `quality_score`
- `id_ban`
- `label`
- `numero`
- `suffixe`
- `nom_voie`
- `code_postal`
- `code_insee`
- `nom_commune`
- `longitude`
- `latitude`
- `candidate_count`
- `street_similarity`
- `number_match`
- `suffix_match`
- `postcode_match`
- `city_similarity`.

## Comparaison d'une paire BAN

Le moteur calcule :

- meme identifiant officiel ;
- similarite de voie ;
- egalite numero ;
- egalite suffixe ;
- egalite CP ;
- egalite commune/code INSEE ;
- distance geographique ;
- qualite minimale des deux recherches.

Le resultat est expose dans `official_pair`.

## Securite

Pendant le scoring, SQLite est ouvert en lecture seule :

```text
file:<db>?mode=ro
```

La BAN est persistee dans un volume Docker et n'est pas versionnee dans Git.

## Mise a jour

Relancer simplement :

```bash
docker compose run --rm ban-loader --departments 13
```

Le departement est remplace atomiquement.
