"""
scripts/lib/utils.py
Primitives partagées : DateCtx, I/O JSON, helpers label, is_placeholder.

Aucune dépendance vers les globals de daily_briefing_workflow.py.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dataclasses import field  # noqa: F401 (used below)
from lib.platform_config import PLATFORM

# ── Calendrier FR ─────────────────────────────────────────────────────────────
JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS  = ["janvier", "février", "mars", "avril", "mai", "juin",
          "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


# ── DateCtx ───────────────────────────────────────────────────────────────────

@dataclass
class DateCtx:
    date: str
    date_longue: str
    date_hier: str


def compute_date_ctx(date_override: str | None = None) -> DateCtx:
    if date_override:
        d = datetime.strptime(date_override, "%Y-%m-%d")
    else:
        now = datetime.now(ZoneInfo("Europe/Paris"))
        d = datetime.strptime(now.strftime("%Y-%m-%d"), "%Y-%m-%d")
    date      = d.strftime("%Y-%m-%d")
    date_hier = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    date_longue = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"
    return DateCtx(date=date, date_longue=date_longue, date_hier=date_hier)


# ── I/O JSON ──────────────────────────────────────────────────────────────────

def read_json(path: Path, default):
    if not path.exists():
        return deepcopy(default)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


# ── Labels / catégories ───────────────────────────────────────────────────────

def derive_label(cat_slug: str) -> str:
    """'fun_facts' → 'Fun Facts'"""
    return cat_slug.replace("_", " ").title()


def build_label_to_cat(categories: dict[str, str]) -> dict[str, str]:
    """Reverse map : label.lower() → slug"""
    return {derive_label(slug).lower(): slug for slug in categories}


def get_label(cat_slug: str) -> str:
    return derive_label(cat_slug)


def get_default_cat(categories: dict[str, str] | None = None) -> str:
    """Premier slug des catégories, ou 'general' si vide."""
    return next(iter(categories or {}), "general")


# ── Placeholder detection ─────────────────────────────────────────────────────

# ── NewsletterConfig ──────────────────────────────────────────────────────────

FALLBACK_CATEGORIES: dict[str, str] = {
    "fonctionnel": "Vie des modèles et des outils IA",
    "use_cases":   "Déploiements concrets en entreprise",
    "fun_facts":   "L'inattendu : records, découvertes surprenantes",
    "societal":    "Réglementation, éthique, gouvernance",
    "economie":    "Marché, financements, business models",
}
FALLBACK_PERSONA: str = (
    "Tu analyses l'actualité pour des experts tech (directeurs, ingénieurs seniors, product managers)."
)


@dataclass
class NewsletterConfig:
    """Paramètres chargés depuis config.json (catégories, persona, nom affiché)."""
    categories: dict[str, str]
    persona: str
    name: str

    @classmethod
    def from_config(cls, config: dict) -> "NewsletterConfig":
        return cls(
            categories=config.get("categories") or FALLBACK_CATEGORIES,
            persona=config.get("persona") or FALLBACK_PERSONA,
            name=config.get("name") or "Newsletter",
        )


# ── Placeholder detection ─────────────────────────────────────────────────────

def is_placeholder_body(body: str) -> bool:
    """True si le body est un texte générique/placeholder."""
    if not body:
        return True
    body_lower = body.lower()
    return any(m.lower() in body_lower for m in PLATFORM.placeholder_markers)
