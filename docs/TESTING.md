# Tests et non-regression

## Commande locale

Depuis la racine :

```bash
python -m unittest discover -s tests -v
```

Avec le Makefile :

```bash
make test
```

## Organisation

### test_parser.py

Teste la normalisation et le parsing :

- noms de ville presents dans le nom de voie ;
- commune extraite apres le code postal ;
- communes absentes d'un dictionnaire ferme ;
- communes multi-mots ;
- CEDEX ;
- `bis / ter / quater` ;
- abreviations.

### test_matcher.py

Teste les decisions texte :

- correspondances avec abreviations ;
- conflit de type de voie ;
- faute proche dans le nom de voie ;
- conflits de numero ;
- conflits de suffixe ;
- conflits de CP ;
- conflits de commune ;
- voies distinctes ;
- villes non pre-enumerees ;
- score brut expose pour audit.

### test_ban.py

Teste :

- recherche locale ;
- suffixes ;
- absence de candidat ;
- metadonnees ;
- maintien d'un cas ambigu en `A_CONTROLER` meme avec BAN ;
- import atomique interrompu ;
- rejet d'un CSV invalide sans perte des donnees existantes.

### test_api.py

Teste :

- `/health`
- `/score`
- taille minimale ;
- chaines d'espaces ;
- taille maximale.

### test_corpus.py

Charge le fichier :

```text
tests/corpus_decisions.json
```

et verifie :

- decision ;
- motif ;
- score minimal ;
- score maximal.

### test_policy_config.py

Verifie que le moteur lit vraiment les bornes depuis `model_config.json`.

Le test modifie temporairement une valeur de configuration et verifie que le comportement du moteur change en consequence.

## Corpus de non-regression

Structure d'un cas :

```json
{
  "id": "near_street_name_typo",
  "address_a": "12 avenue jean jaures 75019 paris",
  "address_b": "12 avenue jean jauresx 75019 paris",
  "expected_decision": "A_CONTROLER",
  "expected_reason": "NOM_VOIE_PROCHE_NON_IDENTIQUE",
  "max_score": 89
}
```

Le corpus doit contenir chaque bug metier corrige afin d'empecher sa reintroduction.

## Ajouter une regression

Procedure recommandee :

1. reproduire la paire ;
2. comprendre si le probleme vient de la normalisation, du parsing, des regles ou du modele ;
3. corriger la cause ;
4. ajouter un test cible ;
5. ajouter le cas au corpus si une decision/borne metier doit rester stable ;
6. lancer toute la suite ;
7. verifier la CI.

## CI GitHub

Workflow :

```text
.github/workflows/ci.yml
```

A chaque push sur `main` et pull request :

1. checkout ;
2. Python 3.12 ;
3. installation des dependances ;
4. `compileall` ;
5. tests ;
6. `docker compose config` ;
7. `docker build .`.

## Critere avant fusion

Un changement de regle ou de configuration ne devrait etre fusionne que si :

- tous les tests passent ;
- le corpus passe ;
- Compose est valide ;
- l'image Docker se construit ;
- les nouveaux cas metier ont une non-regression.

## Evaluation metier

La suite actuelle est une suite de non-regression, pas une evaluation statistique representative de toute la France.

Pour une validation production, constituer un corpus reel etiquete et mesurer au minimum :

- precision des `MEME_ADRESSE` ;
- rappel ;
- faux positifs ;
- faux negatifs ;
- part de `A_CONTROLER` ;
- performances avec et sans BAN ;
- performances par type de voie, commune, format et qualite de saisie.
