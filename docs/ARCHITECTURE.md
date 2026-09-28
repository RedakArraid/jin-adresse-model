# Architecture V5.4

## Vue d'ensemble

Le projet se compose de trois briques executables :

```text
Navigateur
   |
   v
Streamlit
   |
   v
FastAPI
   |
   v
AddressMatcher
   |-- normalisation / parsing
   |-- modele logistique JSON
   |-- regles structurelles
   |-- decision_policy
   |
   +-- SQLite BAN locale
```

La BAN est optionnelle. Le moteur doit rester fonctionnel si la base SQLite n'existe pas.

## Services Docker

### api

Le service `api` execute :

```text
uvicorn api:app --host 0.0.0.0 --port 8000
```

Il expose :

- `GET /health`
- `GET /ban/status`
- `POST /score`
- la documentation Swagger sur `/docs`.

Le fichier de configuration est monte dans l'image sous :

```text
/app/model_config.json
```

La BAN est attendue sous :

```text
/data/ban/ban.sqlite
```

### ui

Le service `ui` execute Streamlit sur le port 8501.

Il ne contient pas de logique de matching propre : il appelle l'API FastAPI.

### ban-loader

Le service `ban-loader` est un outil ponctuel. Il n'est pas necessaire au scoring.

Il sert a :

1. telecharger un ou plusieurs fichiers BAN ;
2. les parser ;
3. les charger dans `ban_staging` ;
4. verifier le nombre de lignes ;
5. publier le departement dans `ban_addresses` par transaction SQLite.

## Pipeline de scoring

### 1. Normalisation

`score_address_pair_v3.py` :

- passe en minuscules ;
- retire les accents ;
- normalise la ponctuation ;
- separe chiffres et lettres ;
- normalise `bis`, `ter`, `quater` ;
- developpe les abreviations de types de voie et certains titres.

Exemples :

```text
bv   -> boulevard
bvd  -> boulevard
bld  -> boulevard
rte  -> route
st   -> saint
gal  -> general
```

### 2. Parsing

Les champs principaux sont :

- `numero`
- `suffixe`
- `type_voie`
- `nom_voie`
- `code_postal`
- `ville_norm`

Lorsque le code postal est present, la commune est extraite du segment place apres le code postal. Cette strategie evite de supprimer un token du nom de voie uniquement parce qu'il correspond aussi a un nom de ville.

### 3. Variables de similarite

Le moteur calcule notamment :

- ratio fuzzy global ;
- WRatio ;
- token set ratio ;
- token sort ratio ;
- Jaccard de tokens ;
- similarite du nom de voie ;
- similarite de commune ;
- egalite/conflit numero ;
- egalite/conflit suffixe ;
- egalite/conflit type de voie ;
- egalite/conflit code postal.

### 4. Modele logistique

Le modele n'est pas charge depuis un binaire `joblib`.

Les coefficients sont stockes dans :

```text
app/model_config.json
```

Le logit est calcule directement par le moteur.

Le `raw_model_score` est conserve pour l'audit.

### 5. Regles structurelles

Les regles structurelles sont appliquees apres le score brut.

Elles ont priorite sur le modele lorsque des champs discriminants se contredisent.

Exemples :

- numero different ;
- suffixe different ;
- type de voie different ;
- code postal different ;
- commune clairement differente ;
- voie clairement differente.

Les noms de voie tres proches mais encore differents apres normalisation sont diriges vers `A_CONTROLER`.

### 6. Match structurel exact

Si les champs suivants sont presents et identiques :

- numero ;
- suffixe ;
- type de voie ;
- nom de voie ;
- code postal ;
- commune ;

le moteur applique `STRUCTURE_IDENTIQUE` et releve le score jusqu'au plancher configure.

Cette regle n'est evaluee qu'apres les regles de conflit.

### 7. BAN locale

Si SQLite est disponible, chaque adresse est recherchee localement.

Le moteur utilise notamment :

- `id_ban`
- numero ;
- suffixe ;
- voie ;
- code postal ;
- code INSEE ;
- commune ;
- latitude / longitude.

Une couche de comparaison officielle calcule :

- egalite d'identifiant ;
- similarite de voie ;
- egalite numero/suffixe/CP/commune ;
- distance geographique ;
- score de paire BAN.

### 8. Fusion finale

La fusion texte/BAN et tous les seuils associes sont definis dans :

```text
decision_policy.ban
```

Les contradictions structurelles du texte restent prioritaires.

Les motifs de revue proteges, notamment `NOM_VOIE_PROCHE_NON_IDENTIQUE`, restent `A_CONTROLER` meme si la BAN trouve un candidat proche.

## Persistance BAN

Le volume Docker :

```text
ban_data
```

conserve `ban.sqlite` entre les redemarrages.

Le scoring ouvre SQLite en lecture seule.

## Cache

`LocalBANGeocoder` met en cache :

- l'etat disponible/non disponible ;
- les statistiques BAN.

Le cache est invalide lorsque la taille ou la date de modification du fichier SQLite change.

## Flux reseau

### Scoring

```text
Utilisateur -> Streamlit -> FastAPI -> SQLite local
```

Aucun appel de geocodage externe n'est necessaire.

### Mise a jour BAN

```text
ban-loader -> adresse.data.gouv.fr
```

Le reseau n'est utilise que pendant cette operation explicite.

## Fichiers principaux

| Fichier | Role |
|---|---|
| `app/ui.py` | interface Streamlit |
| `app/api.py` | API FastAPI |
| `app/matcher.py` | orchestration du scoring |
| `app/score_address_pair_v3.py` | normalisation, parsing, features |
| `app/ban_local.py` | recherche BAN locale |
| `app/model_config.json` | coefficients + politique de decision |
| `scripts/download_ban.py` | import atomique BAN |
| `tests/corpus_decisions.json` | corpus de non-regression |
