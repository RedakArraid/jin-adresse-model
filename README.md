# Comparateur d'adresses - Docker Compose + BAN locale

Projet autonome pour tester le modele de rapprochement d'adresses V3.1 dans une interface web.

## Architecture

- `ui` : interface Streamlit sur `http://localhost:8501`
- `api` : API FastAPI sur `http://localhost:8000`
- `ban-loader` : outil ponctuel pour telecharger/importer la Base Adresse Nationale dans SQLite
- `ban_data` : volume Docker persistant contenant `ban.sqlite`

Le modele fonctionne **sans Internet au moment du scoring**. Si la BAN locale n'est pas encore importee, il revient automatiquement au score texte V3.1.

## 1. Lancer l'application

Prerequis : Docker Desktop ou Docker Engine + Docker Compose.

```bash
docker compose up --build -d
```

Puis ouvrir :

- Interface : http://localhost:8501
- Documentation API : http://localhost:8000/docs

Pour voir les logs :

```bash
docker compose logs -f api ui
```

## 2. Importer la BAN localement

Les fichiers officiels BAN `CSV avec identifiants` sont publies par departement et mis a jour regulierement :
https://adresse.data.gouv.fr/data/ban/adresses/latest/csv-with-ids

Exemple pour les Bouches-du-Rhone :

```bash
docker compose run --rm ban-loader --departments 13
```

Plusieurs departements :

```bash
docker compose run --rm ban-loader --departments 13 75 69 93
```

Le service telecharge des fichiers de la forme :

```text
https://adresse.data.gouv.fr/data/ban/adresses/latest/csv-with-ids/adresses-with-ids-13.csv.gz
```

La base SQLite est stockee dans le volume Docker `ban_data`. Il n'est pas necessaire de redemarrer l'API : elle detecte la base au prochain appel.

> Pour un premier essai, importe seulement les departements dont tu as besoin. Le fichier France complet est beaucoup plus volumineux.

## 3. Essayer l'exemple Saint-Canadet

Dans l'interface, les valeurs par defaut sont :

```text
370 RTE DE ST CANADET 13100 AIX EN PROVENCE
370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE
```

Sans BAN, le modele produit le score texte. Apres import du departement `13`, le moteur cherche aussi chaque adresse dans la BAN locale et affiche :

- statut d'existence ;
- identifiant BAN ;
- libelle officiel ;
- numero et suffixe ;
- voie ;
- code postal / code INSEE / commune ;
- latitude / longitude ;
- score de rapprochement officiel.

## 4. API

Exemple :

```bash
curl -X POST http://localhost:8000/score \
  -H 'Content-Type: application/json' \
  -d '{
    "address_a": "370 RTE DE ST CANADET 13100 AIX EN PROVENCE",
    "address_b": "370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
    "use_ban": true
  }'
```

Etat de la BAN locale :

```bash
curl http://localhost:8000/ban/status
```

## 5. Fonctionnement du score

1. normalisation et expansion des abreviations ;
2. extraction numero / suffixe / voie / CP / ville ;
3. modele V3.1 de similarite ;
4. si disponible, recherche de chaque adresse dans la BAN SQLite locale ;
5. fusion prudente des signaux ;
6. sortie `MEME_ADRESSE`, `A_CONTROLER` ou `DIFFERENTE`.

Les conflits tels que `14` / `14 bis`, codes postaux differents, communes differentes ou identifiants BAN distincts sont conserves comme signaux forts de controle/difference.

## 6. Securite / donnees

Au moment de comparer des adresses, aucun appel vers une API externe n'est necessaire : les donnees BAN sont interrogees dans SQLite local. Internet n'est utilise que lorsque tu lances explicitement `ban-loader` pour telecharger/mettre a jour la base.

## 7. Mise a jour BAN

Relancer la commande d'import pour les departements voulus :

```bash
docker compose run --rm ban-loader --departments 13 75
```

Les lignes des departements concernes sont remplacees dans l'index local.

## 8. Arreter

```bash
docker compose down
```

Les donnees BAN restent dans le volume. Pour supprimer aussi le volume :

```bash
docker compose down -v
```
