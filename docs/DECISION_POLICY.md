# Politique de decision V6

## Source de verite

`app/model_config.json` contient toute la politique dans `decision_policy`.

Sections :

- `score_caps`
- `score_floors`
- `similarity`
- `resolver`
- `ban`

## Deux scores

`similarity_score` est le score brut du modele logistique.

`confidence_score` est le score final apres canonicalisation, preuves par champ, regles structurelles et eventuelle BAN.

`score_final` reste un alias compatible du `confidence_score`.

## Etats de preuve

Chaque composant peut etre classe : `EXACT`, `NORMALIZED_EXACT`, `TYPO_LIKELY`, `UNKNOWN`, `MISSING`, `CONFLICT`.

## Regles prioritaires

| Evidence | Motif | Decision | Borne |
|---|---|---|---:|
| CP `CONFLICT` | `CONFLIT_CODE_POSTAL` | DIFFERENTE | max 4 |
| Numero `CONFLICT` | `CONFLIT_NUMERO` | DIFFERENTE | max 4 |
| Suffixe `CONFLICT` | `CONFLIT_SUFFIXE_NUMERO` | DIFFERENTE | max 4 |
| Type de voie `CONFLICT` | `CONFLIT_TYPE_VOIE` | DIFFERENTE | max 8 |
| Commune `CONFLICT` | `CONFLIT_COMMUNE` | DIFFERENTE | max 4 |
| Voie `CONFLICT` + localisation forte | `CONFLIT_NOM_VOIE` | DIFFERENTE | max 15 |
| Commune `TYPO_LIKELY` | `COMMUNE_PROCHE_NON_IDENTIQUE` | A_CONTROLER | max 89 |
| Voie `TYPO_LIKELY` + localisation forte | `NOM_VOIE_PROCHE_NON_IDENTIQUE` | A_CONTROLER | max 89 |
| Structure exacte/canonique | `STRUCTURE_IDENTIQUE` | MEME_ADRESSE | min 99 |

Les conflits durs sont evalues avant les fautes probables.

## Resolution de commune

Configuration courante :

```json
{
  "city_auto_correct_min": 0.90,
  "city_ambiguity_margin": 0.03,
  "max_city_candidates": 100
}
```

Une commune est `TYPO_CORRECTED` lorsque le meilleur candidat depasse le seuil et est suffisamment eloigne du deuxieme candidat.

Si les deux adresses aboutissent a la meme commune canonique alors que la saisie differait, la preuve devient `NORMALIZED_EXACT`.

Sans resolution locale fiable, une commune proche mais differente reste `A_CONTROLER`.

## BAN

Les motifs de revue proteges incluent :

- `NOM_VOIE_PROCHE_NON_IDENTIQUE`
- `COMMUNE_PROCHE_NON_IDENTIQUE`
- `COMMUNE_AMBIGUE`

Une simple correspondance BAN faible ne doit pas transformer ces cas en match automatique.

Les confirmations fortes restent `MEME_ID_BAN` et `BAN_LOCALE_COHERENTE`.

## Configuration et corpus

Toute modification de borne doit rester alignee avec `tests/corpus_decisions.json`.

`tests/test_policy_config.py` verifie que les valeurs sont reellement lues depuis la configuration.
