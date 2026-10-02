# API V6

Base locale : `http://localhost:8001`

Swagger : `http://localhost:8001/docs`

## GET /health

Retourne `status`, `model_version` et l'etat de la BAN locale.

Version attendue : `V6.0-local-BAN`.

## GET /ban/status

Retourne les statistiques et metadonnees de la base SQLite locale.

## POST /score

Exemple de requete :

```json
{
  "address_a": "187 bld de pontoise 75015 paris",
  "address_b": "187 boulevard de pontoise 75015 paris",
  "use_ban": true
}
```

## Champs V6

### similarity_score

Score brut du modele statistique.

### confidence_score

Score final apres canonicalisation, preuves par champ, regles de decision et eventuelle BAN.

### score_final

Alias compatible de `confidence_score`.

### canonical_A / canonical_B

Representations canoniques des deux adresses, avec signatures et informations de resolution locale.

### field_evidence

Preuves champ par champ. Statuts possibles : `EXACT`, `NORMALIZED_EXACT`, `TYPO_LIKELY`, `UNKNOWN`, `MISSING`, `CONFLICT`.

### decision

Valeurs : `MEME_ADRESSE`, `A_CONTROLER`, `DIFFERENTE`.

### decision_reason

Motifs V6 importants :

- `MODELE_SIMILARITE`
- `STRUCTURE_IDENTIQUE`
- `COMMUNE_PROCHE_NON_IDENTIQUE`
- `NOM_VOIE_PROCHE_NON_IDENTIQUE`
- `CONFLIT_NUMERO`
- `CONFLIT_SUFFIXE_NUMERO`
- `CONFLIT_TYPE_VOIE`
- `CONFLIT_CODE_POSTAL`
- `CONFLIT_COMMUNE`
- `CONFLIT_NOM_VOIE`
- `MEME_ID_BAN`
- `BAN_LOCALE_COHERENTE`

### score_text / decision_text

Resultat structurel avant fusion BAN.

### score_text_v3 / decision_text_v3

Aliases historiques conserves pour compatibilite.

### parsed_A / parsed_B

Representation historique du parsing d'entree.

### address_a_ban / address_b_ban

Resultats detailes de recherche locale si la BAN est utilisee.

### official_pair

Preuves officielles combinees entre les deux resultats BAN.

## Validation

- longueur minimale d'une adresse : 3 caracteres
- longueur maximale : 500 caracteres
- espaces externes supprimes

Codes HTTP : 200, 422, 500.
