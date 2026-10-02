# Comparateur d'adresses francaises - V6.0

Moteur local de rapprochement d'adresses francaises avec interface Streamlit, API FastAPI et BAN locale SQLite optionnelle.

La V6 separe clairement :

```text
Adresse brute
   |
   v
CanonicalAddress
   |
   v
FieldEvidence
   |
   +--> similarity_score (modele statistique)
   |
   +--> DecisionEngine
   |
   +--> BAN locale / resolution CP-commune
   |
   v
confidence_score + decision
```

Le scoring peut fonctionner hors ligne. Internet n'est utilise que pour telecharger ou mettre a jour la BAN.

## Architecture

```text
Navigateur
   |
   v
Streamlit :8501
   |
   v
FastAPI :8000
   |
   v
AddressMatcher
   |-- AddressResolver
   |-- CanonicalAddress
   |-- AddressComparator
   |-- FieldEvidence
   |-- modele logistique local
   |-- DecisionEngine
   |
   +-- LocalBANGeocoder
       |-- recherche d'adresse
       +-- resolution code postal / commune / code INSEE
```

Les decisions possibles sont :

- `MEME_ADRESSE`
- `A_CONTROLER`
- `DIFFERENTE`

## Demarrage

```bash
git clone https://github.com/RedakArraid/jin-adresse-model.git
cd jin-adresse-model
docker compose up --build -d
```

Puis ouvrir :

- interface : http://localhost:8501
- API Swagger : http://localhost:8001/docs
- healthcheck : http://localhost:8001/health

## V6 : adresse canonique

Chaque adresse est transformee independamment en structure canonique :

```json
{
  "number": "370",
  "suffix": "",
  "street_type": "route",
  "street_name": "de saint canadet",
  "postcode": "13100",
  "city_input": "aix en provence",
  "city_canonical": "aix en provence",
  "city_code": "13001"
}
```

Le moteur expose egalement :

- `house_key`
- `street_key`
- `locality_key`
- `address_key`

La BAN locale peut corriger une commune saisie avec une faute lorsque le couple code postal / commune est suffisamment non ambigu.

## V6 : preuves par champ

Chaque composant est compare separement.

Etats possibles :

- `EXACT`
- `NORMALIZED_EXACT`
- `TYPO_LIKELY`
- `UNKNOWN`
- `MISSING`
- `CONFLICT`

Exemple :

```json
{
  "number": {"status": "EXACT"},
  "street_type": {"status": "EXACT"},
  "street_name": {"status": "EXACT"},
  "postcode": {"status": "EXACT"},
  "city": {
    "status": "TYPO_LIKELY",
    "similarity": 0.9375
  }
}
```

Une commune proche mais non identique reste `A_CONTROLER` sans referentiel local capable de la canonicaliser.

## Similarite et confiance

La V6 expose deux scores distincts.

### similarity_score

Score brut du modele statistique.

Il mesure surtout la proximite textuelle/statistique.

### confidence_score

Score final apres :

- canonicalisation ;
- preuves par champ ;
- regles de conflit ;
- eventuelle resolution locale ;
- eventuelle fusion BAN.

`score_final` reste un alias du score de confiance pour compatibilite.

Le score n'est pas une probabilite calibree.

## Regles structurelles

Les conflits durs sont prioritaires sur les fautes probables.

Ordre general :

1. code postal ;
2. numero ;
3. suffixe ;
4. type de voie ;
5. commune clairement incompatible ;
6. nom de voie clairement incompatible ;
7. commune proche mais non identique ;
8. nom de voie proche mais non identique ;
9. structure canonique identique.

Exemples de bornes :

| Motif | Decision | Borne |
|---|---|---:|
| `CONFLIT_CODE_POSTAL` | DIFFERENTE | max 4 |
| `CONFLIT_NUMERO` | DIFFERENTE | max 4 |
| `CONFLIT_SUFFIXE_NUMERO` | DIFFERENTE | max 4 |
| `CONFLIT_TYPE_VOIE` | DIFFERENTE | max 8 |
| `CONFLIT_COMMUNE` | DIFFERENTE | max 4 |
| `CONFLIT_NOM_VOIE` | DIFFERENTE | max 15 |
| `COMMUNE_PROCHE_NON_IDENTIQUE` | A_CONTROLER | max 89 |
| `NOM_VOIE_PROCHE_NON_IDENTIQUE` | A_CONTROLER | max 89 |
| `STRUCTURE_IDENTIQUE` | MEME_ADRESSE | min 99 |

Les valeurs sont centralisees dans :

```text
app/model_config.json
└── decision_policy
    ├── score_caps
    ├── score_floors
    ├── similarity
    ├── resolver
    └── ban
```

## Resolution locale code postal / commune

Avec la BAN chargee, la V6 peut resoudre independamment une commune a partir du code postal.

Etats :

- `EXACT`
- `TYPO_CORRECTED`
- `AMBIGUOUS`
- `NOT_FOUND`
- `UNAVAILABLE`

Configuration :

```json
"resolver": {
  "city_auto_correct_min": 0.90,
  "city_ambiguity_margin": 0.03,
  "max_city_candidates": 100
}
```

Une faute de commune peut donc devenir `NORMALIZED_EXACT` si le referentiel local identifie une seule commune canonique avec suffisamment de confiance.

## BAN locale

Importer un departement :

```bash
docker compose run --rm ban-loader --departments 13
```

Plusieurs departements :

```bash
docker compose run --rm ban-loader --departments 13 75 69 93
```

La BAN est stockee dans le volume Docker `ban_data`.

L'import reste atomique via `ban_staging`.

Voir [docs/BAN.md](docs/BAN.md).

## API

### GET /health

Retourne la version et l'etat BAN.

### GET /ban/status

Retourne les statistiques de la base locale.

### POST /score

Exemple :

```json
{
  "address_a": "187 bld de pontoise 75015 paris",
  "address_b": "187 boulevard de pontoise 75015 paris",
  "use_ban": true
}
```

Champs V6 principaux :

- `similarity_score`
- `confidence_score`
- `score_final`
- `decision`
- `decision_reason`
- `canonical_A`
- `canonical_B`
- `field_evidence`
- `official_pair`
- `model_version`

Pour compatibilite, les champs `score_text_v3` et `decision_text_v3` sont encore exposes. Les nouveaux alias sont `score_text` et `decision_text`.

Voir [docs/API.md](docs/API.md).

## Tests

```bash
python -m unittest discover -s tests -v
```

La V6 ajoute des regressions pour :

- commune proche sans BAN -> `A_CONTROLER` ;
- correction de commune via BAN locale ;
- separation similarite / confiance ;
- priorite des conflits durs ;
- adresses canoniques et signatures ;
- evidence par champ.

Un corpus fictif plus large est disponible dans `tests/fixtures/fictional_address_cases.json`. Il separe les matchs certains, les differences certaines et les cas ambigus, avec des attentes sur la decision et, lorsque cela a du sens, une plage de score.

```bash
make eval
```

La commande affiche les ecarts sans echouer. Pour l'utiliser comme garde qualite stricte :

```bash
make eval-strict
```

Corpus :

```text
tests/corpus_decisions.json
```

Voir [docs/TESTING.md](docs/TESTING.md).

## Structure

```text
app/
├── address_domain.py
├── api.py
├── ban_local.py
├── decision_engine.py
├── matcher.py
├── model_config.json
├── score_address_pair_v3.py
└── ui.py
```

Le fichier `score_address_pair_v3.py` conserve son nom pour compatibilite historique ; il fournit toujours la normalisation, le parsing et les features du modele.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Politique de decision](docs/DECISION_POLICY.md)
- [API](docs/API.md)
- [BAN locale](docs/BAN.md)
- [Tests](docs/TESTING.md)
- [Exploitation](docs/OPERATIONS.md)
- [Changelog](CHANGELOG.md)

## Limites

La V6 est structurellement plus robuste, mais une validation production exige encore un corpus reel etiquete et representatif.

A mesurer avant industrialisation :

- precision ;
- rappel ;
- faux positifs ;
- faux negatifs ;
- taux de `A_CONTROLER` ;
- performance avec/sans BAN ;
- performance par type de saisie et region.

## Version

```text
V6.0-local-BAN
```

La version runtime et la politique de decision viennent de `app/model_config.json`.
