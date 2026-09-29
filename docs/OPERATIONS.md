# Exploitation V6

## Demarrage

```bash
docker compose up --build -d
```

## Services

- Streamlit : 8501
- FastAPI : 8000

## Healthcheck

```bash
curl http://localhost:8000/health
```

Version attendue : `V6.0-local-BAN`.

## Import BAN

```bash
docker compose run --rm ban-loader --departments 13
```

## Test API

```bash
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "address_a": "187 bld de pontoise 75015 paris",
    "address_b": "187 boulevard de pontoise 75015 paris",
    "use_ban": true
  }'
```

Verifier notamment : `similarity_score`, `confidence_score`, `decision`, `field_evidence`, `canonical_A`, `canonical_B`.

## Logs

```bash
docker compose logs -f api ui
```

## Mise a jour

```bash
git pull
docker compose up --build -d
```

Le volume BAN reste conserve tant que `docker compose down -v` n'est pas utilise.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Diagnostic

### Commune proche reste A_CONTROLER

Verifier que le departement correspondant au code postal est charge dans la BAN locale. Sans referentiel local, ce comportement est volontaire.

### Similarite haute mais confiance faible

Consulter `field_evidence` et `decision_reason`. Une contradiction structurelle peut plafonner la confiance meme avec un score statistique eleve.

### BAN indisponible

```bash
curl http://localhost:8000/ban/status
```

## Configuration

Le modele et la policy sont dans `app/model_config.json`.

Un changement de configuration necessite un rebuild Docker.
