from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from matcher import AddressMatcher


class ScoreRequest(BaseModel):
    address_a: str = Field(min_length=3, max_length=500)
    address_b: str = Field(min_length=3, max_length=500)
    use_ban: bool = True


@lru_cache(maxsize=1)
def get_matcher() -> AddressMatcher:
    return AddressMatcher()


app = FastAPI(
    title="Address Matcher",
    version="5.0",
    description="Comparaison d'adresses francaises avec modele V3 + BAN locale optionnelle.",
)


@app.get("/health")
def health() -> Dict[str, Any]:
    matcher = get_matcher()
    return {
        "status": "ok",
        "model_version": "V5-local-BAN",
        "ban": matcher.ban.stats(),
    }


@app.get("/ban/status")
def ban_status() -> Dict[str, Any]:
    return get_matcher().ban.stats()


@app.post("/score")
def score(req: ScoreRequest) -> Dict[str, Any]:
    try:
        return get_matcher().score(req.address_a, req.address_b, use_ban=req.use_ban)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur de scoring: {type(exc).__name__}: {exc}") from exc
