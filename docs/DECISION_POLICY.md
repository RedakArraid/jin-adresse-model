# Politique de decision V5.4

## Source de verite

La politique est centralisee dans :

```text
app/model_config.json
```

Le moteur lit directement la section :

```json
"decision_policy": {
  "score_caps": {},
  "score_floors": {},
  "similarity": {},
  "ban": {}
}
```

L'objectif est d'eviter les constantes metier dispersees dans `matcher.py`.

## Seuils globaux du modele

```text
threshold_different = 0.05
threshold_match     = 0.95
```

Interpretation :

- score modele <= 5 % : `DIFFERENTE` avant regles ;
- score modele >= 95 % : `MEME_ADRESSE` avant regles ;
- entre les deux : `A_CONTROLER` avant regles.

Ces seuils s'appliquent au score statistique brut. Les regles metier peuvent ensuite modifier la decision et le score final.

## Score final

Le score final est une valeur de decision sur 100.

Il ne doit pas etre interprete comme une probabilite calibree de correspondance.

Deux mecanismes encadrent le score :

- un **plafond** pour les conflits/revues ;
- un **plancher** pour les correspondances structurelles ou officielles fortes.

## score_caps

| Motif | Decision | Max |
|---|---|---:|
| `CONFLIT_CODE_POSTAL` | DIFFERENTE | 4 |
| `CONFLIT_COMMUNE` | DIFFERENTE | 4 |
| `COMMUNE_AMBIGUE` | A_CONTROLER | 80 |
| `CONFLIT_NUMERO` | DIFFERENTE | 4 |
| `CONFLIT_SUFFIXE_NUMERO` | DIFFERENTE | 4 |
| `CONFLIT_TYPE_VOIE` | DIFFERENTE | 8 |
| `CONFLIT_NOM_VOIE` | DIFFERENTE | 15 |
| `NOM_VOIE_PROCHE_NON_IDENTIQUE` | A_CONTROLER | 89 |

Le plafond **89** est volontairement inferieur au seuil automatique **95**.

## score_floors

| Motif | Decision | Min |
|---|---|---:|
| `STRUCTURE_IDENTIQUE` | MEME_ADRESSE | 99 |
| `MEME_ID_BAN` | MEME_ADRESSE | 99,9 |
| `BAN_LOCALE_COHERENTE` | MEME_ADRESSE | 98,5 |

## similarity

Configuration courante :

| Parametre | Valeur | Usage |
|---|---:|---|
| `city_conflict_below` | 0,65 | commune consideree incompatible |
| `city_review_below` | 0,88 | commune consideree ambigue |
| `same_location_city_min` | 0,95 | commune suffisamment proche pour comparer fortement la voie |
| `street_conflict_below` | 0,72 | voie consideree clairement differente |

## Ordre des regles structurelles

L'ordre est important.

### 1. Code postal

Deux codes postaux explicites differents :

```text
DIFFERENTE
CONFLIT_CODE_POSTAL
score <= 4
```

### 2. Commune

Si les deux communes sont presentes :

- similarite < 0,65 -> `CONFLIT_COMMUNE` ;
- similarite < 0,88 -> `COMMUNE_AMBIGUE`.

### 3. Numero

Deux numeros explicites differents :

```text
DIFFERENTE
CONFLIT_NUMERO
score <= 4
```

### 4. Suffixe

Meme numero mais suffixe different :

```text
14
14 bis
```

donne :

```text
DIFFERENTE
CONFLIT_SUFFIXE_NUMERO
score <= 4
```

### 5. Type de voie

Deux types explicites differents :

```text
rue / boulevard
route / avenue
```

donnent :

```text
DIFFERENTE
CONFLIT_TYPE_VOIE
score <= 8
```

### 6. Nom de voie

Si le contexte numero/CP/commune est coherent :

- voie clairement differente -> `CONFLIT_NOM_VOIE`, max 15 ;
- voie proche mais tokens encore differents -> `NOM_VOIE_PROCHE_NON_IDENTIQUE`, max 89.

### 7. Structure identique

Si aucune regle precedente n'a detecte de probleme et que numero, suffixe, type de voie, nom de voie, CP et commune sont identiques :

```text
MEME_ADRESSE
STRUCTURE_IDENTIQUE
score >= 99
```

## Politique BAN

### Poids de fusion

```text
texte    = 0.72
BAN      = 0.28
```

La fusion n'est effectuee que si les deux resultats BAN sont utilisables.

### Revues protegees

```json
"guarded_review_reasons": [
  "NOM_VOIE_PROCHE_NON_IDENTIQUE",
  "COMMUNE_AMBIGUE"
]
```

Ces motifs restent en `A_CONTROLER`.

La BAN peut etre affichee comme evidence complementaire, mais ne transforme pas automatiquement ces cas en match.

### Confirmation forte BAN

Un meme `id_ban` avec deux numeros d'adresse confirmes applique :

```text
MEME_ID_BAN
score >= 99.9
```

Une coherence forte des champs BAN avec distance compatible applique :

```text
BAN_LOCALE_COHERENTE
score >= 98.5
```

### Conflits BAN

La configuration `decision_policy.ban` contient aussi :

- distance maximale de confirmation ;
- distance minimale de conflit ;
- seuil de similarite voie ;
- score texte considere fort ;
- plafond de revue en cas de conflit BAN ;
- plafond de difference ;
- seuil d'ambiguite officielle ;
- plafonds lorsque l'existence exacte n'est pas confirmee.

## Modifier une valeur

Exemple : passer le plafond de revue de 89 a 85.

Modifier uniquement :

```json
"NOM_VOIE_PROCHE_NON_IDENTIQUE": 85
```

dans `decision_policy.score_caps`.

Si la meme politique doit s'appliquer apres fusion BAN, aligner egalement :

```json
"guarded_review_max_score": 85
```

Le test `tests/test_policy_config.py` verifie que les valeurs sont reellement lues depuis le fichier de configuration.

## Corpus

Les attentes de non-regression sont dans :

```text
tests/corpus_decisions.json
```

Chaque cas peut definir :

- `expected_decision`
- `expected_reason`
- `max_score`
- `min_score`

La configuration et le corpus doivent rester coherents.
