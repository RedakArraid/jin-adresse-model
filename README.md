# Comparateur d'adresses francaises - V5.4

Prototype autonome de rapprochement d'adresses francaises avec :

- une interface **Streamlit** ;
- une API **FastAPI** ;
- un moteur de normalisation et de parsing ;
- un modele logistique local ;
- des regles metier structurelles prioritaires ;
- une **Base Adresse Nationale (BAN) locale SQLite** optionnelle ;
- une politique de decision centralisee dans `app/model_config.json`.

Le scoring peut fonctionner entierement hors ligne. Internet n'est utilise que lorsqu'un import ou une mise a jour de la BAN est lance explicitement.

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
   |-- normalisation / parsing
   |-- modele logistique local
   |-- regles structurelles
   |-- politique de decision JSON
   |
   +-- BAN SQLite locale (optionnelle)
```

Le moteur retourne trois decisions :

- `MEME_ADRESSE` : correspondance suffisamment forte ;
- `A_CONTROLER` : cas ambigu a verifier ;
- `DIFFERENTE` : contradiction structurelle ou evidence insuffisante.

Le **score final n'est pas une probabilite statistique calibree**. C'est un score de decision combine au modele, aux regles metier et, si elle est disponible, a la BAN locale.

## Demarrage rapide

Prerequis :

- Docker Desktop, ou Docker Engine ;
- Docker Compose v2.

Cloner puis demarrer :

```bash
git clone https://github.com/RedakArraid/jin-adresse-model.git
cd jin-adresse-model
docker compose up --build -d
```

Ouvrir ensuite :

- interface : http://localhost:8501
- API Swagger : http://localhost:8000/docs
- healthcheck : http://localhost:8000/health

Arreter :

```bash
docker compose down
```

Le guide minimal est egalement disponible dans [QUICKSTART.txt](QUICKSTART.txt).

## Fonctionnement du scoring

Le traitement suit cet ordre :

1. normalisation des accents, ponctuations et abreviations ;
2. extraction du numero, suffixe, type de voie, nom de voie, code postal et commune ;
3. calcul des variables de similarite ;
4. calcul du score brut du modele logistique ;
5. application des regles structurelles prioritaires ;
6. si disponible, interrogation de la BAN locale ;
7. fusion prudente du signal texte et du signal BAN ;
8. application des plafonds/planchers configures ;
9. production de la decision finale.

### Normalisation

Quelques exemples d'aliases reconnus :

```text
r / r.           -> rue
av / ave         -> avenue
bd / boul        -> boulevard
bv / bvd / bld   -> boulevard
rte / rt         -> route
st / ste         -> saint / sainte
gal / gen        -> general
```

Les variantes de suffixes sont egalement normalisees :

```text
14B -> 14 bis
14T -> 14 ter
14Q -> 14 quater
```

Le code postal sert de frontiere structurelle entre la voie et la commune. Ainsi, un nom de ville present dans le nom de voie n'est pas supprime par erreur.

## Regles structurelles principales

Les contradictions explicites ont priorite sur le score statistique.

| Cas | Decision | Borne V5.4 |
|---|---|---:|
| Code postal different | `DIFFERENTE` | max 4 |
| Commune clairement differente | `DIFFERENTE` | max 4 |
| Numero different | `DIFFERENTE` | max 4 |
| Suffixe different pour un meme numero | `DIFFERENTE` | max 4 |
| Type de voie different | `DIFFERENTE` | max 8 |
| Nom de voie clairement different | `DIFFERENTE` | max 15 |
| Nom de voie proche mais non identique | `A_CONTROLER` | max 89 |
| Structure complete identique | `MEME_ADRESSE` | min 99 |
| Meme identifiant BAN confirme | `MEME_ADRESSE` | min 99,9 |

Le seuil du modele pour un match automatique est actuellement **95**. Le plafond de revue a donc ete fixe a **89**, ce qui empeche un cas `A_CONTROLER` d'atteindre le seuil automatique.

Toutes ces valeurs sont centralisees dans :

```text
app/model_config.json
└── decision_policy
    ├── score_caps
    ├── score_floors
    ├── similarity
    └── ban
```

Voir [docs/DECISION_POLICY.md](docs/DECISION_POLICY.md).

## BAN locale

Sans BAN, le moteur reste utilisable en mode texte V5.4.

Pour importer un departement :

```bash
docker compose run --rm ban-loader --departments 13
```

Pour plusieurs departements :

```bash
docker compose run --rm ban-loader --departments 13 75 69 93
```

Les donnees sont stockees dans le volume Docker `ban_data`.

L'import est atomique :

```text
telechargement
    |
    v
ban_staging
    |
    v
validation
    |
    v
transaction SQLite
    |
    v
remplacement du departement
```

Si le chargement ou la validation echoue avant la publication, la version precedemment chargee du departement reste disponible.

Voir [docs/BAN.md](docs/BAN.md).

## API

### `GET /health`

Retourne l'etat de l'API, la version du moteur et l'etat de la BAN locale.

### `GET /ban/status`

Retourne les informations disponibles sur la base locale : disponibilite, nombre de lignes, departements charges et metadonnees.

### `POST /score`

Corps :

```json
{
  "address_a": "187 bld de pontoise 75015 paris",
  "address_b": "187 boulevard de pontoise 75015 paris",
  "use_ban": true
}
```

Exemple `curl` :

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "address_a": "187 bld de pontoise 75015 paris",
    "address_b": "187 boulevard de pontoise 75015 paris",
    "use_ban": true
  }'
```

Les champs principaux de sortie sont :

- `score_final`
- `decision`
- `decision_reason`
- `score_text_v3`
- `raw_model_score`
- `parsed_A`, `parsed_B`
- `ban_used`
- `official_pair`
- `address_a_ban`, `address_b_ban`
- `model_version`

Voir [docs/API.md](docs/API.md).

## Tests et corpus

Lancer toute la suite :

```bash
python -m unittest discover -s tests -v
```

Le corpus de non-regression est dans :

```text
tests/corpus_decisions.json
```

Il contient les decisions attendues ainsi que les bornes de score `min_score` / `max_score`.

La CI GitHub execute automatiquement :

1. installation des dependances ;
2. compilation Python ;
3. tests unitaires et corpus ;
4. validation de `docker compose config` ;
5. construction de l'image Docker.

Voir [docs/TESTING.md](docs/TESTING.md).

## Structure du depot

```text
.
├── app/
│   ├── api.py
│   ├── ban_local.py
│   ├── matcher.py
│   ├── model_config.json
│   ├── score_address_pair_v3.py
│   └── ui.py
├── data/
│   └── ban/
├── docs/
│   ├── API.md
│   ├── ARCHITECTURE.md
│   ├── BAN.md
│   ├── DECISION_POLICY.md
│   ├── OPERATIONS.md
│   └── TESTING.md
├── scripts/
│   └── download_ban.py
├── tests/
│   ├── corpus_decisions.json
│   ├── test_api.py
│   ├── test_ban.py
│   ├── test_corpus.py
│   ├── test_matcher.py
│   ├── test_parser.py
│   └── test_policy_config.py
├── .github/workflows/ci.yml
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── QUICKSTART.txt
└── requirements.txt
```

## Documentation detaillee

- [Architecture](docs/ARCHITECTURE.md)
- [Politique de decision](docs/DECISION_POLICY.md)
- [API](docs/API.md)
- [BAN locale](docs/BAN.md)
- [Tests et non-regression](docs/TESTING.md)
- [Exploitation / Docker](docs/OPERATIONS.md)

## Securite et confidentialite

Pendant un scoring standard, aucune adresse n'a besoin d'etre envoyee a un service de geocodage externe. Lorsque la BAN locale est chargee, la recherche se fait dans SQLite en lecture seule.

Le chargeur BAN est le seul composant qui effectue volontairement une connexion Internet pour recuperer les fichiers officiels.

Le conteneur applicatif s'execute avec un utilisateur non privilegie.

## Limites actuelles

Ce projet reste un prototype avance, pas une preuve de performance metier en production.

En particulier :

- les coefficients du modele ne doivent pas etre interpretes comme une probabilite de correspondance ;
- les performances globales precision/rappel doivent encore etre mesurees sur un corpus reel, etiquete et representatif ;
- les seuils de `decision_policy` sont des choix metier/configuration et doivent etre recalibres sur ce corpus avant une industrialisation ;
- la BAN ameliore la verification d'existence et d'identite, mais ne remplace pas un jeu d'evaluation metier.

## Version

Version runtime courante :

```text
V5.4-local-BAN
```

La version exposee par `/health` est lue depuis `app/model_config.json`, qui constitue la source de verite pour la version et la politique de decision.
