# Exploitation et Docker

## Demarrage

```bash
docker compose up --build -d
```

Equivalent Makefile :

```bash
make up
```

## Etat des conteneurs

```bash
docker compose ps
```

## Logs

```bash
docker compose logs -f api ui
```

ou :

```bash
make logs
```

## Healthcheck

```bash
curl http://localhost:8000/health
```

Verifier :

- `status = ok`
- `model_version = V5.4-local-BAN`
- etat BAN attendu.

## Test rapide du scoring

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "address_a": "187 bld de pontoise 75015 paris",
    "address_b": "187 boulevard de pontoise 75015 paris",
    "use_ban": false
  }'
```

## Import BAN

```bash
docker compose run --rm ban-loader --departments 13
```

ou :

```bash
make ban DEPS="13 75 69"
```

## Persistance

La base est stockee dans :

```text
volume Docker ban_data
└── /data/ban/ban.sqlite
```

`docker compose down` conserve le volume.

`docker compose down -v` le supprime.

## Mise a jour du code

```bash
git pull
docker compose up --build -d
```

Le volume BAN est conserve tant que `-v` n'est pas utilise.

## Mise a jour de la politique

Modifier :

```text
app/model_config.json
```

Puis reconstruire l'image :

```bash
docker compose up --build -d
```

Lancer ensuite les tests :

```bash
python -m unittest discover -s tests -v
```

## Sauvegarde BAN

Identifier le volume :

```bash
docker volume ls
```

La strategie de sauvegarde doit etre adaptee a l'environnement d'exploitation.

Comme les donnees BAN peuvent etre retelechargees, le principal besoin de sauvegarde concerne surtout :

- la configuration ;
- les versions de code ;
- les eventuelles donnees locales non reproductibles.

## Reinitialiser la BAN

```bash
docker compose down -v
docker compose up --build -d
```

Puis reimporter les departements necessaires.

## Diagnostic

### API indisponible

```bash
docker compose logs api
docker compose ps
```

### Interface indisponible

```bash
docker compose logs ui
```

### BAN non detectee

```bash
curl http://localhost:8000/ban/status
```

Puis verifier le loader :

```bash
docker compose run --rm ban-loader --departments 13
```

### Echec d'import

L'import etant atomique, l'ancienne version du departement doit rester disponible.

Consulter la sortie du `ban-loader`.

## CI

Avant une mise en production interne, verifier que le workflow GitHub Actions du dernier commit est vert.

La CI couvre :

- compilation ;
- tests ;
- Compose ;
- build Docker.

## Ports

| Service | Port hote |
|---|---:|
| Streamlit | 8501 |
| FastAPI | 8000 |

## Variables d'environnement

### API

```text
MODEL_PATH=/app/model_config.json
BAN_DB_PATH=/data/ban/ban.sqlite
```

### UI

```text
API_URL=http://api:8000
```

## Utilisateur Docker

L'image cree un utilisateur non privilegie :

```text
appuser
```

Le processus applicatif ne tourne pas en root.
