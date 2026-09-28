from __future__ import annotations

import os
from typing import Any, Dict

import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(page_title="Comparateur d'adresses", page_icon="📍", layout="wide")
st.title("📍 Comparateur d'adresses")
st.caption("Modele V3.1 + verification optionnelle dans une Base Adresse Nationale locale")


def api_get(path: str) -> Dict[str, Any]:
    r = requests.get(f"{API_URL}{path}", timeout=10)
    r.raise_for_status()
    return r.json()


def api_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    r = requests.post(f"{API_URL}{path}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

try:
    status = api_get("/health")
    ban = status.get("ban", {})
    if ban.get("available"):
        deps = ", ".join(ban.get("departments", [])) or "n/a"
        st.success(f"BAN locale disponible : {ban.get('rows', 0):,} adresses | departements : {deps}".replace(",", " "))
    else:
        st.warning("BAN locale non importee : le moteur fonctionne en mode texte V3. Utilise la commande ban-loader pour l'ajouter.")
except Exception as exc:
    st.error(f"API indisponible : {exc}")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    address_a = st.text_area(
        "Adresse A",
        value="370 RTE DE ST CANADET 13100 AIX EN PROVENCE",
        height=110,
    )
with col2:
    address_b = st.text_area(
        "Adresse B",
        value="370 ROUTE DE SAINT-CANADET 13100 AIX-EN-PROVENCE",
        height=110,
    )

use_ban = st.checkbox("Utiliser la BAN locale si elle est disponible", value=True)

if st.button("Comparer", type="primary", use_container_width=True):
    with st.spinner("Comparaison en cours..."):
        try:
            result = api_post("/score", {"address_a": address_a, "address_b": address_b, "use_ban": use_ban})
        except Exception as exc:
            st.error(f"Erreur : {exc}")
            st.stop()

    decision = result.get("decision", "")
    score = result.get("score_final", 0.0)
    c1, c2, c3 = st.columns(3)
    c1.metric("Score final", f"{score:.2f} / 100")
    c2.metric("Decision", decision)
    c3.metric("Score texte V3", f"{float(result.get('score_text_v3', 0)):.2f} / 100")

    if decision == "MEME_ADRESSE":
        st.success("Les deux adresses sont considerees comme la meme adresse.")
    elif decision == "DIFFERENTE":
        st.error("Les deux adresses sont considerees comme differentes.")
    else:
        st.warning("La paire doit etre controlee.")

    st.caption(f"Raison : {result.get('decision_reason', '')}")

    with st.expander("Normalisation / parsing"):
        p1, p2 = st.columns(2)
        with p1:
            st.subheader("Adresse A")
            st.json(result.get("parsed_A", {}))
        with p2:
            st.subheader("Adresse B")
            st.json(result.get("parsed_B", {}))

    if result.get("ban_used"):
        st.subheader("Verification BAN locale")
        b1, b2 = st.columns(2)
        with b1:
            ga = result.get("address_a_ban", {})
            st.markdown("**Adresse A**")
            st.write(ga.get("existence_status", ""))
            st.write(ga.get("label", ""))
            st.json(ga)
        with b2:
            gb = result.get("address_b_ban", {})
            st.markdown("**Adresse B**")
            st.write(gb.get("existence_status", ""))
            st.write(gb.get("label", ""))
            st.json(gb)
        with st.expander("Comparaison des resultats BAN"):
            st.json(result.get("official_pair", {}))
    else:
        st.info("Le score affiche est produit uniquement par le modele local de similarite.")

    with st.expander("JSON complet"):
        st.json(result)

st.divider()
st.markdown(
    """
**Demarrage rapide**  
`docker compose up --build -d` puis ouvre `http://localhost:8501`.

**Importer la BAN d'un departement**  
`docker compose run --rm ban-loader --departments 13`  
Tu peux en importer plusieurs : `--departments 13 75 69`.
"""
)
