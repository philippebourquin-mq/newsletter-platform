"""
tests/test_models.py
Tests unitaires pour les modèles Pydantic (lib/models.py).

Vérifie :
  - Validation des champs obligatoires
  - Coercition des types (score str → float)
  - Détection de corruptions (ids dupliqués, urls invalides, titres vides)
  - Compatibilité avec les fixtures réelles de backlog et today
  - model_dump() → JSON sérialisable
"""
from __future__ import annotations

import json
import pytest
from pydantic import ValidationError

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.models import BacklogItem, NewsItem, RadarItem, SourceRef, TodayEdition


# ══════════════════════════════════════════════════════════════════════════════
# SourceRef
# ══════════════════════════════════════════════════════════════════════════════

class TestSourceRef:
    def test_valid(self):
        s = SourceRef(nom="TechCrunch", url="https://techcrunch.com/article")
        assert s.nom == "TechCrunch"
        assert s.url.startswith("https://")

    def test_default_nom(self):
        s = SourceRef(url="https://example.com")
        assert s.nom == "Source"

    def test_invalid_url(self):
        with pytest.raises(ValidationError, match="http"):
            SourceRef(nom="Bad", url="ftp://invalid.com")

    def test_empty_url_allowed(self):
        # URL vide → passe (on ne force pas http si vide)
        s = SourceRef(nom="Test", url="")
        assert s.url == ""


# ══════════════════════════════════════════════════════════════════════════════
# BacklogItem
# ══════════════════════════════════════════════════════════════════════════════

class TestBacklogItem:
    def _make(self, **kwargs) -> dict:
        base = {
            "titre": "OpenAI lance un nouveau modèle",
            "score": 85,
            "url": "https://openai.com/blog",
            "body": "OpenAI a annoncé...",
            "categorie": "fonctionnel",
        }
        base.update(kwargs)
        return base

    def test_valid_minimal(self):
        item = BacklogItem.model_validate({"titre": "Test", "score": 50})
        assert item.titre == "Test"
        assert item.score == 50.0

    def test_valid_full(self):
        item = BacklogItem.model_validate(self._make(
            sources=[{"nom": "OpenAI", "url": "https://openai.com"}]
        ))
        assert len(item.sources) == 1
        assert item.sources[0].nom == "OpenAI"

    def test_score_coerced_from_string(self):
        item = BacklogItem.model_validate({"titre": "Test", "score": "72.5"})
        assert item.score == 72.5

    def test_score_coerced_from_invalid_string(self):
        # Score non parseable → 0.0 (dégradé, pas d'erreur)
        item = BacklogItem.model_validate({"titre": "Test", "score": "invalid"})
        assert item.score == 0.0

    def test_negative_score_rejected(self):
        with pytest.raises(ValidationError):
            BacklogItem.model_validate({"titre": "Test", "score": -1})

    def test_empty_titre_rejected(self):
        with pytest.raises(ValidationError, match="vide"):
            BacklogItem.model_validate({"titre": "", "score": 50})

    def test_whitespace_titre_rejected(self):
        with pytest.raises(ValidationError, match="vide"):
            BacklogItem.model_validate({"titre": "   ", "score": 50})

    def test_extra_fields_allowed(self):
        # Le backlog peut contenir des champs supplémentaires (ex: _duplicate)
        item = BacklogItem.model_validate({
            "titre": "Test", "score": 30, "_duplicate": True, "custom_field": "x"
        })
        assert item.titre == "Test"

    def test_serializable_to_json(self):
        item = BacklogItem.model_validate(self._make())
        dumped = item.model_dump()
        json.dumps(dumped)  # ne doit pas lever d'exception


# ══════════════════════════════════════════════════════════════════════════════
# NewsItem
# ══════════════════════════════════════════════════════════════════════════════

class TestNewsItem:
    def _make(self, **kwargs) -> dict:
        base = {
            "id":        "2026-05-30-001",
            "num":       1,
            "categorie": "fonctionnel",
            "label":     "Fonctionnel",
            "titre":     "OpenAI lance GPT-5",
            "body":      "OpenAI a annoncé ce modèle révolutionnaire.",
            "sources":   [{"nom": "OpenAI", "url": "https://openai.com"}],
        }
        base.update(kwargs)
        return base

    def test_valid(self):
        item = NewsItem.model_validate(self._make())
        assert item.id == "2026-05-30-001"
        assert item.num == 1

    def test_empty_titre_rejected(self):
        with pytest.raises(ValidationError):
            NewsItem.model_validate(self._make(titre=""))

    def test_empty_body_rejected(self):
        with pytest.raises(ValidationError):
            NewsItem.model_validate(self._make(body=""))

    def test_invalid_id_format(self):
        with pytest.raises(ValidationError, match="format"):
            NewsItem.model_validate(self._make(id="bad-id"))

    def test_num_must_be_positive(self):
        with pytest.raises(ValidationError):
            NewsItem.model_validate(self._make(num=0))

    def test_no_sources_allowed(self):
        # sources vide → valide (le pipeline peut produire des items sans sources)
        item = NewsItem.model_validate(self._make(sources=[]))
        assert item.sources == []

    def test_rebond_de_optional(self):
        item = NewsItem.model_validate(self._make(rebond_de={"titre": "Article lié", "date": "2026-05-29"}))
        assert item.rebond_de is not None

    def test_extra_fields_allowed(self):
        item = NewsItem.model_validate(self._make(extra_field="test"))
        assert item.titre == "OpenAI lance GPT-5"


# ══════════════════════════════════════════════════════════════════════════════
# TodayEdition
# ══════════════════════════════════════════════════════════════════════════════

class TestTodayEdition:
    def _make_news(self, n: int = 2) -> list[dict]:
        return [
            {
                "id": f"2026-05-30-{i+1:03d}",
                "num": i + 1,
                "categorie": "fonctionnel",
                "label": "Fonctionnel",
                "titre": f"Article {i+1}",
                "body": f"Contenu de l'article {i+1}.",
                "sources": [],
            }
            for i in range(n)
        ]

    def test_valid(self):
        edition = TodayEdition.model_validate({
            "date": "2026-05-30",
            "date_longue": "Samedi 30 mai 2026",
            "chapeau": "Édition test.",
            "news": self._make_news(3),
            "radar": [{"titre": "Signal", "desc": "À surveiller.", "url": "https://example.com"}],
        })
        assert edition.date == "2026-05-30"
        assert len(edition.news) == 3
        assert len(edition.radar) == 1

    def test_invalid_date_format(self):
        with pytest.raises(ValidationError):
            TodayEdition.model_validate({
                "date": "30-05-2026",  # mauvais format
                "date_longue": "Samedi 30 mai 2026",
                "news": [],
            })

    def test_duplicate_news_ids_rejected(self):
        news = self._make_news(2)
        news[1]["id"] = news[0]["id"]  # duplication volontaire
        with pytest.raises(ValidationError, match="dupliqués"):
            TodayEdition.model_validate({
                "date": "2026-05-30",
                "date_longue": "Samedi 30 mai 2026",
                "news": news,
            })

    def test_empty_news_allowed(self):
        # today vide est valide (premier run, backlog vide)
        edition = TodayEdition.model_validate({
            "date": "2026-05-30",
            "date_longue": "Samedi 30 mai 2026",
            "news": [],
        })
        assert edition.news == []

    def test_serializable_round_trip(self):
        """model_dump() doit produire un dict JSON-serialisable et re-validable."""
        original = {
            "date": "2026-05-30",
            "date_longue": "Samedi 30 mai 2026",
            "chapeau": "Chapeau test.",
            "news": self._make_news(2),
            "radar": [],
        }
        edition = TodayEdition.model_validate(original)
        dumped = edition.model_dump()
        raw_json = json.dumps(dumped)  # sérialisable
        reloaded = TodayEdition.model_validate(json.loads(raw_json))
        assert reloaded.date == edition.date
        assert len(reloaded.news) == len(edition.news)

    def test_extra_fields_preserved(self):
        edition = TodayEdition.model_validate({
            "date": "2026-05-30",
            "date_longue": "Samedi 30 mai 2026",
            "news": [],
            "custom_key": "preserved",
        })
        assert edition.model_dump().get("custom_key") == "preserved"
