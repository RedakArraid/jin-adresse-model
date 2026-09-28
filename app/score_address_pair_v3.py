from __future__ import annotations

import re
import unicodedata
from rapidfuzz import fuzz

STREET_TYPES = [
    'rue','avenue','boulevard','route','chemin','impasse','place','allee',
    'passage','faubourg','square','quai','cours','voie','sentier','promenade',
    'montee','parvis','esplanade','chaussee','corniche','rotonde','rocade',
    'traverse','ruelle','venelle','hameau','lotissement','residence','domaine',
    'cite','clos','parc','rondpoint','lieudit','autoroute'
]
TYPE_ALIAS_MAP = {
    'r':'rue','av':'avenue','ave':'avenue','avn':'avenue','bd':'boulevard','boul':'boulevard',
    'rte':'route','rt':'route','chem':'chemin','ch':'chemin','chm':'chemin','imp':'impasse',
    'pl':'place','all':'allee','pass':'passage','pge':'passage','faub':'faubourg','fg':'faubourg',
    'sq':'square','qai':'quai','crs':'cours','cour':'cours','voi':'voie','sente':'sentier','sent':'sentier',
    'prom':'promenade','mont':'montee','parv':'parvis','espl':'esplanade','chau':'chaussee',
    'corn':'corniche','roto':'rotonde','roca':'rocade','trav':'traverse','ruel':'ruelle','vene':'venelle',
    'hame':'hameau','loti':'lotissement','lotis':'lotissement','resi':'residence','res':'residence',
    'doma':'domaine','rpt':'rondpoint','ld':'lieudit','auto':'autoroute'
}
WORD_ALIAS_MAP = {
    'gal':'general','gle':'general','gen':'general','st':'saint','ste':'sainte','sts':'saints','stes':'saintes',
    'dr':'docteur','cdt':'commandant','cnl':'colonel','mal':'marechal','pdt':'president',
    'bat':'batiment','app':'appartement','appt':'appartement','etg':'etage','ent':'entree','imm':'immeuble'
}
MULTIWORD_NORMALIZATIONS = [
    (r'\brond\s+point\b','rondpoint'),(r'\blieu\s+dit\b','lieudit'),
    (r'\bzone\s+d\s+activite\b','zoneactivite'),(r'\bzone\s+industrielle\b','zoneindustrielle'),
    (r'\bzone\s+d\s+amenagement\s+concerte\b','zoneamenagement'),
    (r'\bcentre\s+commercial\b','centrecommercial'),(r'\bboite\s+postale\b','bp')
]


def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFD', str(s)) if unicodedata.category(c) != 'Mn')


def normalize_text(s: str) -> str:
    s = strip_accents(str(s).lower()).replace('\u2019', "'").replace("'", ' ')
    s = re.sub(r'[-,.;:/()\[\]{}]', ' ', s)
    s = re.sub(r'(?<=\d)(?=[a-z])', ' ', s)
    s = re.sub(r'(?<=[a-z])(?=\d)', ' ', s)
    s = re.sub(r'\b(\d{1,4})\s+b\b', r'\1 bis', s)
    s = re.sub(r'\b(\d{1,4})\s+t\b', r'\1 ter', s)
    s = re.sub(r'\b(\d{1,4})\s+q\b', r'\1 quater', s)
    s = re.sub(r'\bhuit\s+mai\b', '8 mai', s)
    s = re.sub(r'\bonze\s+novembre\b', '11 novembre', s)
    s = re.sub(r'\bquatorze\s+juillet\b', '14 juillet', s)
    for pat, repl in MULTIWORD_NORMALIZATIONS:
        s = re.sub(pat, repl, s)
    out = []
    for tok in re.sub(r'\s+', ' ', s).strip().split():
        out.append(TYPE_ALIAS_MAP.get(WORD_ALIAS_MAP.get(tok, tok), WORD_ALIAS_MAP.get(tok, tok)))
    return ' '.join(out)


def make_city_map(city_names):
    return {normalize_text(c): c for c in city_names}


def parse_address(raw: str, city_map):
    n = normalize_text(raw)
    tokens = n.split()
    cp_m = re.search(r'(?<!\d)(\d{5})(?!\d)', n)
    cp = cp_m.group(1) if cp_m else ''
    city_norm = ''
    for cn in sorted(city_map, key=len, reverse=True):
        if re.search(r'(?<!\w)' + re.escape(cn) + r'(?!\w)', n):
            city_norm = cn
            break
    type_idx, stype = None, ''
    for i, tok in enumerate(tokens):
        if tok in STREET_TYPES:
            type_idx, stype = i, tok
            break
    num, suffix = '', ''
    digits = [(i, t) for i, t in enumerate(tokens) if re.fullmatch(r'\d{1,4}', t)]
    if type_idx is not None:
        before = [(i, t) for i, t in digits if i < type_idx]
        if before:
            pos, num = before[-1]
        elif digits:
            pos, num = digits[0]
        else:
            pos = None
    elif digits:
        pos, num = digits[0]
    else:
        pos = None
    if pos is not None and pos + 1 < len(tokens) and tokens[pos + 1] in ('bis', 'ter', 'quater'):
        suffix = tokens[pos + 1]
    city_toks = set(city_norm.split()) if city_norm else set()
    street_tokens = []
    stop_words = {'batiment','appartement','etage','entree','immeuble','zoneactivite','zoneindustrielle','zoneamenagement','centrecommercial','bp','cedex'}
    if type_idx is not None:
        for tok in tokens[type_idx + 1:]:
            if tok == cp or re.fullmatch(r'\d{5}', tok) or tok in stop_words:
                break
            if tok in city_toks:
                continue
            street_tokens.append(tok)
    street = ' '.join(street_tokens).strip()
    if city_norm and street.endswith(city_norm):
        street = street[:-len(city_norm)].strip()
    return {'norm': n, 'numero': num, 'suffixe': suffix, 'type_voie': stype, 'nom_voie': street, 'code_postal': cp, 'ville_norm': city_norm}


def jaccard_tokens(a, b):
    A, B = set(normalize_text(a).split()), set(normalize_text(b).split())
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def safe_ratio(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return fuzz.ratio(str(a), str(b)) / 100.0


def safe_token_set(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(str(a), str(b)) / 100.0


def make_features(raw_a, raw_b, city_map, ext_a=None, ext_b=None):
    pa, pb = parse_address(raw_a, city_map), parse_address(raw_b, city_map)
    na, nb = pa['norm'], pb['norm']
    numa, numb = pa['numero'], pb['numero']
    numa_i = int(numa) if numa.isdigit() else None
    numb_i = int(numb) if numb.isdigit() else None
    num_diff = abs(numa_i - numb_i) if numa_i is not None and numb_i is not None else 999.0
    cpa, cpb = pa['code_postal'], pb['code_postal']
    citya, cityb = pa['ville_norm'], pb['ville_norm']
    sa, sb = pa['suffixe'], pb['suffixe']
    f = {
        'norm_exact': int(na == nb),
        'sim_full_ratio': fuzz.ratio(na, nb) / 100.0,
        'sim_full_wratio': fuzz.WRatio(na, nb) / 100.0,
        'sim_token_set': fuzz.token_set_ratio(na, nb) / 100.0,
        'sim_token_sort': fuzz.token_sort_ratio(na, nb) / 100.0,
        'token_jaccard': jaccard_tokens(na, nb),
        'length_ratio': min(len(na), len(nb)) / max(len(na), len(nb), 1),
        'token_count_diff': abs(len(na.split()) - len(nb.split())),
        'one_contains_other': int((na in nb or nb in na) and min(len(na), len(nb)) >= 8),
        'sim_street': safe_token_set(pa['nom_voie'], pb['nom_voie']),
        'street_jaccard': jaccard_tokens(pa['nom_voie'], pb['nom_voie']),
        'sim_city': safe_ratio(citya, cityb),
        'num_present_both': int(bool(numa) and bool(numb)),
        'num_exact': int(bool(numa) and bool(numb) and numa == numb),
        'num_abs_diff': min(num_diff, 999.0),
        'num_near_1': int(num_diff == 1),
        'num_conflict': int(bool(numa) and bool(numb) and numa != numb),
        'suffix_present_any': int(bool(sa) or bool(sb)),
        'suffix_exact': int(sa == sb),
        'suffix_conflict': int(bool(sa) and bool(sb) and sa != sb),
        'suffix_missing_one': int(bool(sa) != bool(sb)),
        'type_present_both': int(bool(pa['type_voie']) and bool(pb['type_voie'])),
        'type_exact': int(bool(pa['type_voie']) and bool(pb['type_voie']) and pa['type_voie'] == pb['type_voie']),
        'cp_present_both': int(bool(cpa) and bool(cpb)),
        'cp_exact': int(bool(cpa) and bool(cpb) and cpa == cpb),
        'cp_conflict': int(bool(cpa) and bool(cpb) and cpa != cpb),
        'cp_dept_exact': int(len(cpa) >= 2 and len(cpb) >= 2 and cpa[:2] == cpb[:2]),
        'city_present_both': int(bool(citya) and bool(cityb)),
        'city_exact': int(bool(citya) and bool(cityb) and citya == cityb),
        'city_conflict': int(bool(citya) and bool(cityb) and citya != cityb),
    }
    return f, pa, pb
