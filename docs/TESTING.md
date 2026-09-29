# Tests V6

## Lancer

```bash
python -m unittest discover -s tests -v
```

## Couverture

### test_parser.py

Normalisation et parsing.

### test_matcher.py

Regles historiques et structurelles.

### test_v6_structure.py

Comportements V6 :

- commune proche sans BAN -> `A_CONTROLER` ;
- separation `similarity_score` / `confidence_score` ;
- priorite d'un conflit de numero ;
- signatures canoniques ;
- correction de commune via BAN locale ;
- preuve `NORMALIZED_EXACT` apres resolution.

### test_ban.py

Recherche BAN, suffixes, absence de candidat, metadata et import atomique.

### test_policy_config.py

Verifie que les bornes viennent de `model_config.json`.

### test_corpus.py

Execute `tests/corpus_decisions.json`.

### test_api.py

Valide les endpoints et la version runtime.

## Corpus

Un cas peut definir `expected_decision`, `expected_reason`, `max_score` et `min_score`.

La V6 ajoute notamment une commune proche non identique plafonnee a 89.

## CI

A chaque push et pull request :

1. installation des dependances ;
2. compilation Python ;
3. tests ;
4. `docker compose config` ;
5. `docker build .`.

## Validation production

Les tests actuels sont des non-regressions. Ils ne remplacent pas un corpus reel etiquete permettant de mesurer precision, rappel, faux positifs, faux negatifs et taux de `A_CONTROLER`.
