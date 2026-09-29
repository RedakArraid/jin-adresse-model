# Architecture V6

## Vue d'ensemble

```text
Adresse brute
   |
   v
AddressResolver
   |
   v
CanonicalAddress
   |
   v
AddressComparator
   |
   v
FieldEvidence
   |             \
   |              +--> modele logistique --> similarity_score
   v
DecisionEngine
   |
   +--> BAN locale / resolution CP-commune
   v
confidence_score + decision
```

## CanonicalAddress

Chaque adresse est canonicalisee independamment avant la comparaison.

Champs principaux :

- `raw`
- `normalized`
- `number`
- `suffix`
- `street_type`
- `street_name`
- `postcode`
- `city_input`
- `city_canonical`
- `city_code`
- `city_source`
- `locality_status`
- `locality_score`
- `ban_id`
- `longitude` / `latitude`

Signatures derivees : `house_key`, `street_key`, `locality_key`, `address_key`.

## AddressResolver

Le resolver applique d'abord le parseur local. Lorsque la BAN est disponible, il peut resoudre le couple code postal / commune et recuperer une commune canonique ainsi que le code INSEE.

Statuts de resolution : `EXACT`, `TYPO_CORRECTED`, `AMBIGUOUS`, `NOT_FOUND`, `UNAVAILABLE`.

## AddressComparator

Il produit une preuve par champ avec les statuts :

- `EXACT`
- `NORMALIZED_EXACT`
- `TYPO_LIKELY`
- `UNKNOWN`
- `MISSING`
- `CONFLICT`

Il calcule aussi `strong_location`, `exact_structure` et un resume des statuts.

## Modele statistique

Le modele logistique historique reste utilise pour produire `similarity_score`. Il ne porte plus seul la decision finale.

## DecisionEngine

Le moteur de decision applique les conflits durs, les revues pour fautes probables, les planchers de match structurel et la fusion BAN.

Un conflit fort comme un numero different reste prioritaire sur une faute probable de commune.

## BAN locale

La BAN joue deux roles :

1. resolution de localite : CP + commune saisie -> commune canonique + code INSEE ;
2. recherche d'adresse : numero/voie/CP -> identifiant BAN, libelle, coordonnees et statut d'existence.

## Compatibilite API

Nouveaux champs V6 : `canonical_A`, `canonical_B`, `field_evidence`, `similarity_score`, `confidence_score`, `score_text`, `decision_text`.

Champs historiques conserves : `parsed_A`, `parsed_B`, `score_text_v3`, `decision_text_v3`, `score_final`.

## Fichiers principaux

| Fichier | Role |
|---|---|
| `app/address_domain.py` | objets V6, resolver et comparator |
| `app/decision_engine.py` | politique de decision |
| `app/matcher.py` | orchestration |
| `app/score_address_pair_v3.py` | normalisation, parsing et features |
| `app/ban_local.py` | BAN locale et resolution de localite |
| `app/model_config.json` | modele et policy |
| `app/api.py` | FastAPI |
| `app/ui.py` | Streamlit |
