"""
tests/test_fetch_backlog.py
Tests unitaires sur scripts/fetch_backlog.py.

Couvre les fonctions pures et le budget Tavily — sans appels réseau réels.
Chaque test mocke feedparser ou Tavily selon le besoin.
"""
from __future__ import annotations

import sys
import importlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── sys.path ──────────────────────────────────────────────────────────────────
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

# On importe le module entier pour pouvoir réinitialiser les globals entre tests
import fetch_backlog as fb


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def reset_tavily_budget(budget: int = 20) -> None:
    """Réinitialise le compteur Tavily entre les tests (state global du module)."""
    fb._TAVILY_CALLS  = 0
    fb._TAVILY_BUDGET = budget


# ═══════════════════════════════════════════════════════════════════════════════
# Budget Tavily — _can_use_tavily()
# ═══════════════════════════════════════════════════════════════════════════════

class TestCanUseTavily:
    def setup_method(self):
        reset_tavily_budget(budget=3)

    def test_allows_first_call(self):
        assert fb._can_use_tavily() is True

    def test_increments_counter(self):
        fb._can_use_tavily()
        assert fb._TAVILY_CALLS == 1

    def test_blocks_after_budget_exhausted(self):
        # Épuiser le budget
        fb._can_use_tavily()
        fb._can_use_tavily()
        fb._can_use_tavily()
        # 4ème appel → budget épuisé
        result = fb._can_use_tavily()
        assert result is False

    def test_counter_continues_past_budget(self):
        """Le compteur continue d'incrémenter même après le budget (pour le log)."""
        reset_tavily_budget(budget=1)
        fb._can_use_tavily()   # consomme le budget
        fb._can_use_tavily()   # premier appel bloqué
        fb._can_use_tavily()   # deuxième appel bloqué
        assert fb._TAVILY_CALLS == 3

    def test_budget_zero_blocks_immediately(self):
        reset_tavily_budget(budget=0)
        assert fb._can_use_tavily() is False

    def test_allows_exactly_budget_calls(self):
        reset_tavily_budget(budget=5)
        results = [fb._can_use_tavily() for _ in range(5)]
        assert all(results), "Les 5 premiers appels doivent être autorisés"
        assert fb._can_use_tavily() is False, "Le 6ème appel doit être bloqué"


# ═══════════════════════════════════════════════════════════════════════════════
# Filtres URL — is_non_source_platform()
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsNonSourcePlatform:
    def test_youtube_detected(self):
        assert fb.is_non_source_platform("https://www.youtube.com/watch?v=abc") is True
        assert fb.is_non_source_platform("https://youtu.be/abc123") is True

    def test_twitter_detected(self):
        assert fb.is_non_source_platform("https://x.com/openai/status/123") is True
        assert fb.is_non_source_platform("https://twitter.com/anthropic") is True

    def test_legitimate_source_not_detected(self):
        assert fb.is_non_source_platform("https://techcrunch.com/article") is False
        assert fb.is_non_source_platform("https://openai.com/blog/post") is False
        assert fb.is_non_source_platform("https://anthropic.com/research") is False

    def test_malformed_url(self):
        # Ne doit pas lever d'exception
        assert fb.is_non_source_platform("not-a-url") is False
        assert fb.is_non_source_platform("") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Filtres URL — is_homepage_or_generic()
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsHomepageOrGeneric:
    def test_homepage_detected(self):
        assert fb.is_homepage_or_generic("https://openai.com", "OpenAI") is True
        assert fb.is_homepage_or_generic("https://openai.com/", "OpenAI") is True

    def test_blog_root_detected(self):
        assert fb.is_homepage_or_generic("https://anthropic.com/blog", "Anthropic Blog") is True

    def test_article_url_passes(self):
        assert fb.is_homepage_or_generic(
            "https://techcrunch.com/2026/05/14/openai-launches-new-model",
            "OpenAI Launches Revolutionary New Model for Enterprise"
        ) is False

    def test_generic_title_separator(self):
        assert fb.is_homepage_or_generic("https://openai.com/blog/post", "OpenAI | Home") is True

    def test_short_title_filtered(self):
        # ≤3 mots → générique
        assert fb.is_homepage_or_generic("https://example.com/article", "AI news") is True

    def test_normal_title_passes(self):
        assert fb.is_homepage_or_generic(
            "https://example.com/article/123",
            "Google DeepMind publie une étude majeure sur l'alignement des LLMs"
        ) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Filtre sources relais — is_relay_self_ref()
# ═══════════════════════════════════════════════════════════════════════════════

class TestIsRelaySelfRef:
    def test_detects_self_reference(self):
        # La source "TechCrunch" est mentionnée dans le titre → auto-référence
        assert fb.is_relay_self_ref("TechCrunch annonce son nouveau format", "TechCrunch") is True

    def test_allows_unrelated_article(self):
        assert fb.is_relay_self_ref("OpenAI lance GPT-5 avec des capacités inédites", "TechCrunch") is False

    def test_handles_social_handle(self):
        # @unefille.ia → extrait "fille" comme token
        result = fb.is_relay_self_ref("une fille ia partage son analyse", "@unefille.ia")
        assert result is True

    def test_case_insensitive(self):
        assert fb.is_relay_self_ref("TECHCRUNCH révèle ses chiffres", "TechCrunch") is True

    def test_short_stop_words_not_matched(self):
        # "le" et "la" sont des stop words → pas de match
        assert fb.is_relay_self_ref("Le modèle est arrivé", "le") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Clean HTML — clean_html()
# ═══════════════════════════════════════════════════════════════════════════════

class TestCleanHtml:
    def test_removes_tags(self):
        result = fb.clean_html("<p>Hello <strong>World</strong></p>")
        assert "Hello" in result
        assert "World" in result
        assert "<" not in result

    def test_removes_script_content(self):
        result = fb.clean_html("<script>alert('xss')</script><p>Safe content</p>")
        assert "alert" not in result
        assert "Safe content" in result

    def test_removes_style_content(self):
        result = fb.clean_html("<style>.foo{color:red}</style><p>Visible</p>")
        assert "color" not in result
        assert "Visible" in result

    def test_normalizes_whitespace(self):
        result = fb.clean_html("<p>Word1   \n\n   Word2</p>")
        assert "  " not in result  # pas de double espace

    def test_empty_html(self):
        assert fb.clean_html("") == ""

    def test_plain_text_passthrough(self):
        result = fb.clean_html("Pas de HTML ici")
        assert result == "Pas de HTML ici"


# ═══════════════════════════════════════════════════════════════════════════════
# Fusion backlog — merge_with_existing_backlog()
# ═══════════════════════════════════════════════════════════════════════════════

class TestMergeWithExistingBacklog:
    def _make_item(self, titre: str, url: str, score: float = 50.0) -> dict:
        return {
            "titre": titre,
            "url": url,
            "categorie": "tech",
            "label": "Tech",
            "sources": [{"nom": "Source", "url": url}],
            "score": score,
            "body": "",
            "_source_nom": "Source",
            "_duplicate": False,
        }

    def test_no_overlap_keeps_fresh_items(self):
        fresh = [self._make_item("Quantum computing breakthrough at IBM", "https://ibm.com/a")]
        backlog = [self._make_item("OpenAI lance GPT-5 révolutionnaire", "https://openai.com/b")]
        remaining, updated = fb.merge_with_existing_backlog(fresh, backlog)
        assert len(remaining) == 1
        assert remaining[0]["titre"] == "Quantum computing breakthrough at IBM"

    def test_overlap_boosts_backlog_score(self):
        fresh = [self._make_item("OpenAI GPT-5 nouveau modèle révolution", "https://other.com/gpt5")]
        backlog = [self._make_item("OpenAI lance GPT-5 révolutionnaire modèle", "https://openai.com/gpt5", score=60.0)]
        remaining, updated = fb.merge_with_existing_backlog(fresh, backlog)
        assert len(remaining) == 0  # fusionné, pas ajouté
        assert updated[0]["score"] > 60.0  # boost appliqué

    def test_overlap_merges_sources(self):
        fresh_item = self._make_item("OpenAI GPT-5 nouveau modèle lancement", "https://verge.com/gpt5")
        fresh_item["sources"] = [{"nom": "The Verge", "url": "https://verge.com/gpt5"}]
        backlog_item = self._make_item("OpenAI lance GPT-5 nouveau modèle", "https://openai.com/gpt5")
        backlog_item["sources"] = [{"nom": "OpenAI", "url": "https://openai.com/gpt5"}]
        _, updated = fb.merge_with_existing_backlog([fresh_item], [backlog_item])
        source_urls = [s["url"] for s in updated[0]["sources"]]
        assert "https://verge.com/gpt5" in source_urls
        assert "https://openai.com/gpt5" in source_urls

    def test_empty_inputs(self):
        remaining, updated = fb.merge_with_existing_backlog([], [])
        assert remaining == []
        assert updated == []

    def test_empty_backlog(self):
        fresh = [self._make_item("Article tout neuf sur l'IA générative", "https://example.com/a")]
        remaining, updated = fb.merge_with_existing_backlog(fresh, [])
        assert len(remaining) == 1
        assert updated == []


# ═══════════════════════════════════════════════════════════════════════════════
# fetch_feed() — retour tuple + distinction erreur vs vide
# ═══════════════════════════════════════════════════════════════════════════════

class TestFetchFeed:
    """
    Ces tests mockent feedparser pour éviter tout appel réseau.
    Ils vérifient :
      - Le retour est toujours un tuple (list, bool)
      - rss_error=True sur erreur HTTP/exception
      - rss_error=False sur flux OK mais vide dans la fenêtre
      - Pas de fallback Tavily si rss_error=False
    """

    SOURCE = {"url": "https://example.com/feed.rss", "nom": "Example", "fiabilite": 80}

    def _make_feed(self, entries=None, status=200, bozo=False):
        """Construit un objet feed feedparser minimal."""
        feed = MagicMock()
        feed.status = status
        feed.bozo   = bozo
        feed.entries = entries or []
        return feed

    def _make_entry(self, titre="Titre article test complet IA", url="https://example.com/article"):
        entry = MagicMock()
        entry.title = titre
        entry.link  = url
        entry.summary = "Description courte de l'article."
        entry.description = ""
        # Date récente (maintenant)
        now = datetime.now(timezone.utc)
        entry.published_parsed = now.timetuple()[:9]
        entry.updated_parsed   = None
        return entry

    def test_returns_tuple(self):
        with patch("feedparser.parse", return_value=self._make_feed()):
            result = fb.fetch_feed(self.SOURCE, window_hours=24)
        assert isinstance(result, tuple)
        assert len(result) == 2
        items, rss_error = result
        assert isinstance(items, list)
        assert isinstance(rss_error, bool)

    def test_http_error_sets_rss_error_true(self):
        """Un flux HTTP 404 → rss_error=True."""
        with patch("feedparser.parse", return_value=self._make_feed(status=404)):
            items, rss_error = fb.fetch_feed(self.SOURCE, window_hours=24)
        assert rss_error is True
        assert items == []

    def test_exception_sets_rss_error_true(self):
        """Une exception feedparser → rss_error=True."""
        with patch("feedparser.parse", side_effect=Exception("Network error")):
            items, rss_error = fb.fetch_feed(self.SOURCE, window_hours=24)
        assert rss_error is True

    def test_feed_ok_no_entries_sets_rss_error_true(self):
        """
        Flux HTTP 200 mais 0 entrées feedparser → GitHub Actions IPs bloquées
        → rss_error=True (on veut le fallback Tavily dans ce cas).
        """
        with patch("feedparser.parse", return_value=self._make_feed(entries=[], status=200)):
            items, rss_error = fb.fetch_feed(self.SOURCE, window_hours=24)
        assert rss_error is True

    def test_feed_ok_entries_outside_window_rss_error_false(self):
        """
        Flux OK avec entrées, mais toutes hors fenêtre temporelle → rss_error=False.
        Source basse fréquence normale — pas de fallback Tavily.
        """
        old_entry = self._make_entry()
        old_time = datetime.now(timezone.utc) - timedelta(hours=72)
        old_entry.published_parsed = old_time.timetuple()[:9]
        old_entry.updated_parsed   = None

        feed = self._make_feed(entries=[old_entry], status=200)
        with patch("feedparser.parse", return_value=feed):
            items, rss_error = fb.fetch_feed(self.SOURCE, window_hours=24)
        assert rss_error is False    # pas d'erreur — source basse fréquence
        assert items == []            # mais aucun article dans la fenêtre

    def test_feed_ok_recent_entry_returned(self):
        """Flux OK avec entrée récente → 1 article retourné, rss_error=False."""
        entry = self._make_entry(titre="Article IA générative entreprise adoption récent")
        feed  = self._make_feed(entries=[entry], status=200)
        with patch("feedparser.parse", return_value=feed):
            items, rss_error = fb.fetch_feed(self.SOURCE, window_hours=24)
        assert rss_error is False
        assert len(items) == 1

    def test_tavily_fallback_triggered_on_rss_error(self):
        """rss_error=True ET tavily_fallback=True → Tavily est appelé."""
        reset_tavily_budget(budget=5)
        source = {**self.SOURCE, "tavily_fallback": True}

        with patch("feedparser.parse", return_value=self._make_feed(status=503)), \
             patch.object(fb, "HAS_TAVILY", True), \
             patch.object(fb, "TAVILY_API_KEY", "fake-key"), \
             patch.object(fb, "tavily_search", return_value=[]) as mock_tavily:
            fb.fetch_feed(source, window_hours=24)

        mock_tavily.assert_called_once()

    def test_no_tavily_fallback_on_empty_window(self):
        """rss_error=False (flux OK, fenêtre vide) → pas de Tavily."""
        reset_tavily_budget(budget=5)
        old_entry = self._make_entry()
        old_time  = datetime.now(timezone.utc) - timedelta(hours=48)
        old_entry.published_parsed = old_time.timetuple()[:9]
        old_entry.updated_parsed   = None

        feed = self._make_feed(entries=[old_entry], status=200)
        with patch("feedparser.parse", return_value=feed), \
             patch.object(fb, "tavily_search", return_value=[]) as mock_tavily:
            fb.fetch_feed(self.SOURCE, window_hours=24)

        mock_tavily.assert_not_called()

    def test_no_tavily_when_budget_exhausted(self):
        """Budget Tavily épuisé → pas d'appel Tavily même en cas d'erreur RSS."""
        reset_tavily_budget(budget=0)  # budget à zéro
        source = {**self.SOURCE, "tavily_fallback": True}

        with patch("feedparser.parse", return_value=self._make_feed(status=503)), \
             patch.object(fb, "HAS_TAVILY", True), \
             patch.object(fb, "TAVILY_API_KEY", "fake-key"), \
             patch.object(fb, "tavily_search", return_value=[]) as mock_tavily:
            fb.fetch_feed(source, window_hours=24)

        mock_tavily.assert_not_called()
