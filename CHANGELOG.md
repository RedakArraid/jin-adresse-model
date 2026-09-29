# Changelog

## V6.0

### Architecture

- ajout de `CanonicalAddress`, `FieldEvidence` et `AddressEvidence` ;
- ajout de `AddressResolver`, `AddressComparator` et `DecisionEngine` ;
- `AddressMatcher` devient principalement un orchestrateur.

### Resolution locale

- resolution code postal / commune depuis la BAN locale ;
- recuperation du code INSEE ;
- statuts `EXACT`, `TYPO_CORRECTED`, `AMBIGUOUS`, `NOT_FOUND`, `UNAVAILABLE`.

### Decision

- separation `similarity_score` / `confidence_score` ;
- preuves par champ ;
- commune proche non identique -> `A_CONTROLER` sans canonicalisation ;
- conflits durs prioritaires sur les fautes probables ;
- structure canonique exacte -> match haute confiance.

### API et UI

- ajout de `canonical_A`, `canonical_B`, `field_evidence` ;
- ajout de `score_text`, `decision_text` ;
- champs V3 historiques conserves pour compatibilite ;
- interface V6 affiche similarite, confiance et preuves par champ.

### Tests

- ajout de `test_v6_structure.py` ;
- corpus enrichi avec un cas de commune proche ;
- test de correction locale via mini-BAN.

## V5.4

### Configuration

- centralisation des plafonds, planchers et seuils dans `app/model_config.json` ;
- ajout de `decision_policy.score_caps` ;
- ajout de `decision_policy.score_floors` ;
- ajout de `decision_policy.similarity` ;
- ajout de `decision_policy.ban` ;
- version runtime lue depuis la configuration.

### Non-regression

- ajout de `tests/corpus_decisions.json` ;
- plafond `NOM_VOIE_PROCHE_NON_IDENTIQUE = 89` aligne entre moteur et corpus ;
- ajout de tests prouvant que les valeurs sont reellement chargees depuis la configuration.

### Documentation

- documentation complete V5.4 ;
- guides architecture, politique de decision, API, BAN, tests et exploitation ;
- interface Streamlit alignee sur V5.4.

## V5.3

- ajout de `bld -> boulevard` ;
- conflit explicite de type de voie traite comme `DIFFERENTE` ;
- noms de voie proches mais non identiques diriges vers `A_CONTROLER` ;
- protection de ces revues lorsque la BAN est active ;
- ajout des regressions correspondantes.

## V5.2

- ajout des aliases `bv`, `bvd`, `blvd` pour `boulevard` ;
- ajout de la regle de haute confiance `STRUCTURE_IDENTIQUE` ;
- la structure exacte exige numero, suffixe, voie, code postal et commune coherents.

## V5.1

- correction du parsing voie/commune avec le code postal comme frontiere ;
- suppression de la dependance a une liste fermee de communes lorsque le code postal est present ;
- ajout de regles prioritaires pour numero, suffixe, code postal, commune et voie ;
- correction de l'effet de `num_abs_diff` ;
- import BAN atomique avec staging ;
- recherche BAN mieux bornee et deterministe ;
- optimisation des statistiques `/health` ;
- extension importante de la suite de tests.

## V5.0

- Docker Compose ;
- FastAPI ;
- Streamlit ;
- moteur local de rapprochement ;
- BAN SQLite optionnelle ;
- fonctionnement degrade sans BAN.
