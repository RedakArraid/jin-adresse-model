# Comparateur d'adresses - Docker Compose + BAN locale

Prototype de rapprochement d'adresses francaises avec interface Streamlit, API FastAPI, scoring local et Base Adresse Nationale (BAN) locale optionnelle.

## Architecture

- `ui` : interface Streamlit sur `http://localhost:8501`
- `api` : API FastAPI sur `http://localhost:8000`
- `ban-loader` : telechargement/import ponctuel de la BAN dans SQLite
- `ban_data` : volume Docker persistant contenant `ban.sqlite`

Le scoring reste **hors ligne**. Internet n'est necessaire que pour telecharger/mettre a jour la BAN.

## Correctifs V5.1

La V5.1 renforce la securite du prototype :

- le code postal sert de frontiere entre la voie et la commune ; `10 rue de Paris 75001 Paris` conserve bien `de paris` comme nom de voie ;
- la commune est extraite structurellement apres le code postal, donc le mode sans BAN ne depend plus d'une liste fermee de communes ;
- les conflits explicites de numero, suffixe (`14` / `14 bis`), code postal, commune et nom de voie ne peuvent plus etre compenses par le fuzzy matching ;
- `num_abs_diff` ne peut plus augmenter le score ;
- l'import BAN utilise une table de staging puis un remplacement transactionnel du departement ; un import interrompu laisse l'ancienne version intacte ;
- la recherche BAN est bornee par CP/commune + numero/voie et ordonnee de maniere deterministe, au lieu d'un `LIMIT` arbitraire sur un grand code postal ;
- `/health` lit en priorite les statistiques stockees dans `metadata` et le geocodeur met en cache l'etat tant que le fichier SQLite n'a pas change ;
- la suite de non-regression couvre le parseur, les conflits structurels, la BAN, l'import atomique et l'API.

## 1. Lancer l'application

Prerequis : Docker Desktop ou Docker Engine + Docker Compose.

```bash
docker compose up --build -d
```

Puis ouvrir :

- Interface : http://localhost:8501
- Documentation API : http://localhost:8000/docs

Logs :

```bash
docker compose logs -f api ui
```

## 2. Importer la BAN localement

Exemple pour les Bouches-du-Rhone :

```bash
docker compose run --rm ban-loader --departments 13
```

Plusieurs departements :

```bash
docker compose run --rm ban-loader --departments 13 75 69 93
```

Les fichiers officiels `CSV avec identifiants` sont telecharges depuis :

```text
https://adresse.data.gouv.fr/data/ban/adresses/latest/csv-with-ids
```

Le remplacement d'un departement est atomique : le nouveau fichier est d'abord charge et valide dans `ban_staging`, puis publie dans `ban_addresses` dans une transaction unique.

## 3. Exemple Saint-Canadet

```text
370 RTE DE ST CANADET 13100 AIX EN PROVENCE
370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE
```

En mode texte V5.1, cet exemple reste classe `MEME_ADRESSE` avec un score eleve. Apres import du departement `13`, la BAN locale ajoute l'identifiant officiel, le libelle, les coordonnees et les controles de coherence.

## 4. Regles structurelles

Le modele statistique produit toujours un score brut, expose dans `raw_model_score`, mais certaines contradictions ont priorite sur lui :

- deux numeros explicites differents -> `DIFFERENTE` ;
- meme numero mais suffixe different ou manquant (`14` / `14 bis`) -> `DIFFERENTE` ;
- codes postaux explicites differents -> `DIFFERENTE` ;
- communes clairement incompatibles -> `DIFFERENTE` ;
- noms de voie clairement differents a localisation egale -> `DIFFERENTE` ;
- noms de voie proches mais ambigus -> `A_CONTROLER`.

Cette couche empeche un fuzzy matching eleve de masquer une contradiction metier.

## 5. API

```bash
curl -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{
    "address_a": "370 RTE DE ST CANADET 13100 AIX EN PROVENCE",
    "address_b": "370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
    "use_ban": true
  }'
```

Etat BAN :

```bash
curl http://localhost:8000/ban/status
```

## 6. Tests

```bash
python -m unittest discover -s tests -v
```

La suite couvre notamment : rues `de Paris`/`de Lyon`, communes absentes de l'ancien dictionnaire, conflits de numero et suffixe, CP/communes differents, voies homonymes, recherche BAN, import interrompu et validation des endpoints FastAPI.

## 7. Securite / donnees

Lors d'une comparaison, aucune adresse n'est envoyee vers une API externe. La BAN est interrogee dans SQLite local. Le reseau n'est utilise que lorsque `ban-loader` est lance explicitement.

## 8. Arreter

```bash
docker compose down
```

Pour supprimer egalement la BAN locale :

```bash
docker compose down -v
```
