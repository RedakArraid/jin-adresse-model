# API V5.4

## Adresse locale

Par defaut :

```text
http://localhost:8000
```

Documentation interactive :

```text
http://localhost:8000/docs
```

## GET /health

Retourne l'etat de l'application.

Exemple :

```json
{
  "status": "ok",
  "model_version": "V5.4-local-BAN",
  "ban": {
    "available": false,
    "path": "/data/ban/ban.sqlite",
    "rows": 0,
    "departments": []
  }
}
```

La version vient de `app/model_config.json`.

## GET /ban/status

Retourne les statistiques BAN.

Lorsque la BAN n'est pas presente :

```json
{
  "available": false,
  "path": "/data/ban/ban.sqlite",
  "rows": 0,
  "departments": []
}
```

Lorsque la BAN est chargee, la reponse peut aussi contenir :

- `rows`
- `departments`
- `metadata`
- `last_update`.

## POST /score

### Requete

```json
{
  "address_a": "187 bld de pontoise 75015 paris",
  "address_b": "187 boulevard de pontoise 75015 paris",
  "use_ban": true
}
```

Contraintes :

- `address_a` : chaine de 3 a 500 caracteres ;
- `address_b` : chaine de 3 a 500 caracteres ;
- les espaces en debut/fin sont retires ;
- `use_ban` : booleen, valeur par defaut `true`.

### Reponse principale

Exemple simplifie :

```json
{
  "score_final": 99.66,
  "decision": "MEME_ADRESSE",
  "decision_reason": "STRUCTURE_IDENTIQUE",
  "score_text_v3": 99.66,
  "raw_model_score": 99.66,
  "parsed_A": {},
  "parsed_B": {},
  "ban_used": false,
  "ban_available": false,
  "model_version": "V5.4-local-BAN"
}
```

Selon le contexte, le score exact peut varier si la configuration evolue.

### Champs

#### score_final

Score final apres regles et eventuelle fusion BAN.

Echelle :

```text
0 .. 100
```

Ce n'est pas une probabilite calibree.

#### decision

Valeurs :

```text
MEME_ADRESSE
A_CONTROLER
DIFFERENTE
```

#### decision_reason

Motif principal de la decision.

Motifs possibles cote texte :

- `MODELE_V3`
- `STRUCTURE_IDENTIQUE`
- `CONFLIT_CODE_POSTAL`
- `CONFLIT_COMMUNE`
- `COMMUNE_AMBIGUE`
- `CONFLIT_NUMERO`
- `CONFLIT_SUFFIXE_NUMERO`
- `CONFLIT_TYPE_VOIE`
- `CONFLIT_NOM_VOIE`
- `NOM_VOIE_PROCHE_NON_IDENTIQUE`.

Motifs possibles avec BAN :

- `MEME_ID_BAN`
- `BAN_LOCALE_COHERENTE`
- `TEXTE_FORT_MAIS_CONFLIT_BAN`
- `CONFLIT_BAN_LOCALE`
- `PREUVE_BAN_AMBIGUE`
- `DEUX_ADRESSES_NON_TROUVEES_DANS_BAN`
- `EXISTENCE_EXACTE_NON_CONFIRMEE`
- `V3_PLUS_BAN_LOCALE`.

Lorsque la BAN n'est pas disponible/desactivee :

- `BAN_LOCALE_ABSENTE_FALLBACK_V3`
- `BAN_LOCALE_DESACTIVEE`

si aucune autre regle metier plus importante n'a deja fourni un motif.

#### raw_model_score

Score brut produit par le modele logistique avant les plafonds/planchers metier.

#### score_text_v3

Score texte apres application des regles structurelles, avant eventuelle fusion BAN.

Le nom est conserve pour compatibilite avec l'API actuelle.

#### parsed_A / parsed_B

Structure extraite :

```json
{
  "norm": "...",
  "numero": "187",
  "suffixe": "",
  "type_voie": "boulevard",
  "nom_voie": "de pontoise",
  "code_postal": "75015",
  "ville_norm": "paris",
  "ville_source": "postal_segment"
}
```

#### ban_used

`true` si la couche BAN a effectivement ete utilisee pour la paire.

#### ban_available

Indique si le fichier BAN local est disponible.

#### official_pair

Present lorsque la BAN est utilisee.

Exemples de champs :

- `usable_both`
- `same_official_id`
- `official_street_similarity`
- `official_number_same`
- `official_suffix_same`
- `official_postcode_same`
- `official_city_same`
- `official_distance_m`
- `official_pair_score`.

#### address_a_ban / address_b_ban

Resultat detaille de recherche locale.

Voir [BAN.md](BAN.md).

## Codes HTTP

### 200

Requete valide.

### 422

Erreur de validation Pydantic, par exemple :

- adresse trop courte ;
- adresse trop longue ;
- champ obligatoire manquant.

### 500

Erreur interne de scoring.

La reponse contient un detail d'erreur technique.

## Exemples curl

### Sans BAN

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "address_a": "12 avenue jean jaures 75019 paris",
    "address_b": "12 avenue jean jauresx 75019 paris",
    "use_ban": false
  }'
```

### Avec BAN

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "address_a": "187 bld de pontoise 75015 paris",
    "address_b": "187 boulevard de pontoise 75015 paris",
    "use_ban": true
  }'
```
