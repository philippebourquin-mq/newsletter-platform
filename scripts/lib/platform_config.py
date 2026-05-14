"""
scripts/lib/platform_config.py
Charge scripts/platform.json et expose les paramètres globaux de la plateforme.

Usage :
    from lib.platform_config import PLATFORM

    score = PLATFORM.freshness_score(age_hours=4)   # → 30
    max_per_cat = PLATFORM.max_per_cat(nb_main=6)   # → 2
"""
from __future__ import annotations

import json
from pathlib import Path

_PLATFORM_JSON = Path(__file__).resolve().parents[1] / "platform.json"


class PlatformConfig:
    """Accès structuré aux paramètres de platform.json."""

    def __init__(self, path: Path = _PLATFORM_JSON) -> None:
        self._data = json.loads(path.read_text(encoding="utf-8"))

    # ── Freshness scoring ────────────────────────────────────────────────────

    @property
    def freshness_thresholds(self) -> list[dict]:
        return self._data["freshness_scoring"]["thresholds"]

    @property
    def score_unknown_date(self) -> int:
        return self._data["freshness_scoring"]["score_unknown_date"]

    @property
    def score_stale(self) -> int:
        return self._data["freshness_scoring"]["score_stale"]

    def freshness_score(self, age_hours: float) -> int:
        """Retourne le score de fraîcheur pour un âge donné (en heures)."""
        for t in self.freshness_thresholds:
            if age_hours < t["max_hours"]:
                return t["score"]
        return self.score_stale

    # ── Article selection ────────────────────────────────────────────────────

    @property
    def inspect_pool_multiplier(self) -> int:
        return self._data["article_selection"]["inspect_pool_multiplier"]

    @property
    def fiabilite_weight(self) -> int:
        return self._data["article_selection"]["fiabilite_weight"]

    def max_per_cat(self, nb_main: int) -> int:
        """Quota max d'articles par catégorie selon le nombre total d'articles principaux."""
        cfg = self._data["article_selection"]
        return max(cfg["max_per_cat_min"], nb_main // cfg["max_per_cat_divisor"])

    # ── Rebond detection ─────────────────────────────────────────────────────

    @property
    def min_overlap_rebond(self) -> int:
        return self._data["rebond_detection"]["min_overlap_rebond"]

    @property
    def max_overlap_duplicate(self) -> int:
        return self._data["rebond_detection"]["max_overlap_duplicate"]

    # ── Backlog ──────────────────────────────────────────────────────────────

    @property
    def score_minimum_default(self) -> int:
        return self._data["backlog"]["score_minimum_default"]

    @property
    def decroissance_quotidienne_pct_default(self) -> int:
        return self._data["backlog"]["decroissance_quotidienne_pct_default"]

    @property
    def bonus_feedback_pts_default(self) -> int:
        return self._data["backlog"]["bonus_feedback_pts_default"]

    @property
    def source_score_bonus_multi(self) -> float:
        return self._data["backlog"]["source_score_bonus_multi"]

    @property
    def source_score_malus_ignored(self) -> float:
        return self._data["backlog"]["source_score_malus_ignored"]

    @property
    def source_score_bonus_click(self) -> float:
        return self._data["backlog"]["source_score_bonus_click"]

    @property
    def source_score_min(self) -> float:
        return self._data["backlog"]["source_score_min"]

    @property
    def source_score_max(self) -> float:
        return self._data["backlog"]["source_score_max"]

    def clamp_score_minimum(self, value: int) -> int:
        b = self._data["backlog"]
        return max(b["score_minimum_min"], min(b["score_minimum_max"], int(value)))

    # ── Fetch ────────────────────────────────────────────────────────────────

    @property
    def window_heures_default(self) -> int:
        return self._data["fetch"]["window_heures_default"]

    @property
    def max_articles_corps_default(self) -> int:
        return self._data["fetch"]["max_articles_corps_default"]

    # ── Placeholder markers ──────────────────────────────────────────────────

    @property
    def placeholder_markers(self) -> list[str]:
        return self._data["placeholder_markers"]


# Singleton — importé directement par les scripts
PLATFORM = PlatformConfig()
