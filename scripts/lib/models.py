"""
scripts/lib/models.py
Modèles Pydantic v2 pour les frontières critiques du pipeline.

Utilisés exclusivement AUX FRONTIÈRES — lecture JSON / écriture JSON / sortie de build_today.
L'intérieur des fonctions continue d'utiliser des dict pour rester simple.

Modèles :
    SourceRef       — référence source dans un article {nom, url}
    BacklogItem     — article dans backlog.json
    NewsItem        — article produit par make_entry_from_backlog (today.news[*])
    RadarItem       — item radar (today.radar[*])
    TodayEdition    — sortie complète de build_today / today.json

Usage :
    from lib.models import BacklogItem, TodayEdition

    # Valider à l'entrée (lecture backlog)
    items = [BacklogItem.model_validate(x) for x in raw_backlog]

    # Valider à la sortie (build_today)
    edition = TodayEdition.model_validate(raw_today)
    write_json(path, edition.model_dump())
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


# ── SourceRef ─────────────────────────────────────────────────────────────────

class SourceRef(BaseModel):
    nom: str = Field(default="Source")
    url: str = Field(default="https://example.com")

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        if v and not v.startswith(("http://", "https://")):
            raise ValueError(f"URL invalide (doit commencer par http/https) : {v!r}")
        return v


# ── BacklogItem ───────────────────────────────────────────────────────────────

class BacklogItem(BaseModel):
    """
    Article dans backlog.json.
    Champs obligatoires : titre, score.
    Tous les autres sont optionnels (peuvent arriver partiellement remplis depuis fetch_backlog).
    Note : _duplicate est un champ "extra" (Pydantic v2 n'accepte pas les noms avec _).
    """
    titre:     str
    score:     float = Field(ge=0)
    url:       str   = Field(default="https://example.com")
    body:      str   = Field(default="")
    categorie: str   = Field(default="fonctionnel")
    label:     str   = Field(default="")
    sources:   list[SourceRef] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    @field_validator("score", mode="before")
    @classmethod
    def coerce_score(cls, v: Any) -> float:
        try:
            return float(v)
        except (TypeError, ValueError):
            return 0.0

    @field_validator("titre")
    @classmethod
    def titre_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("BacklogItem.titre ne peut pas être vide")
        return v.strip()


# ── NewsItem ──────────────────────────────────────────────────────────────────

class NewsItem(BaseModel):
    """
    Article publié dans today.news[*].
    Produit par make_entry_from_backlog, écrit dans today.json et data.js.
    """
    id:        str
    num:       int   = Field(ge=1)
    categorie: str
    label:     str
    confiance: str   = Field(default="✅ source primaire")
    titre:     str
    body:      str
    sources:   list[SourceRef] = Field(default_factory=list)
    rebond_de: dict | None = Field(default=None)

    model_config = {"extra": "allow"}

    @field_validator("titre", "body")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(f"Champ obligatoire vide : {v!r}")
        return v

    @model_validator(mode="after")
    def id_format(self) -> "NewsItem":
        # id doit ressembler à "2026-05-30-001"
        parts = self.id.split("-")
        if len(parts) < 4:
            raise ValueError(f"NewsItem.id format invalide : {self.id!r} (attendu YYYY-MM-DD-NNN)")
        return self


# ── RadarItem ─────────────────────────────────────────────────────────────────

class RadarItem(BaseModel):
    titre: str
    desc:  str = Field(default="")
    url:   str = Field(default="https://example.com")

    model_config = {"extra": "allow"}


# ── TodayEdition ──────────────────────────────────────────────────────────────

class TodayEdition(BaseModel):
    """
    Édition du jour — sortie de build_today / today.json / data.js TODAY.
    """
    date:       str   = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_longue: str
    chapeau:    str   = Field(default="")
    news:       list[NewsItem]  = Field(default_factory=list)
    radar:      list[RadarItem] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    @field_validator("news")
    @classmethod
    def news_ids_unique(cls, v: list[NewsItem]) -> list[NewsItem]:
        ids = [item.id for item in v]
        if len(ids) != len(set(ids)):
            dups = [i for i in ids if ids.count(i) > 1]
            raise ValueError(f"NewsItem IDs dupliqués : {list(set(dups))}")
        return v
