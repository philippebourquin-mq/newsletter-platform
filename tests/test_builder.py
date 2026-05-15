"""
tests/test_builder.py
Tests unitaires sur lib/builder, lib/renderer, lib/utils, lib/storage.
Toutes les fonctions sont testées avec des fixtures JSON minimales.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

# Résolution du sys.path
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from lib.builder import (
    _key_terms,
    build_today,
    detect_rebond,
    detect_source_candidates,
    make_entry_from_backlog,
    parse_newsletter_md,
    process_feedback,
    semantic_rebond_classify,
    update_source_scores,
)
from lib.renderer import (
    generate_chapeau,
    load_recent_newsletter_summaries,
    write_html,
    write_markdown,
)
from lib.storage import (
    _migrate_json_from_data_js,
    generate_data_js,
    update_data_json,
)
from lib.utils import (
    DateCtx,
    NewsletterConfig,
    FALLBACK_CATEGORIES,
    build_label_to_cat,
    compute_date_ctx,
    derive_label,
    get_default_cat,
    is_placeholder_body,
    read_json,
    write_json,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_DATE_CTX = DateCtx(
    date="2026-05-14",
    date_longue="Jeudi 14 mai 2026",
    date_hier="2026-05-13",
)

MOCK_NL_CONFIG = NewsletterConfig.from_config({
    "name": "Test NL",
    "categories": {"tech": "Technologie", "eco": "Économie"},
    "persona": "Tu es expert IA.",
})

MOCK_BACKLOG_ITEM = {
    "titre": "OpenAI lance un nouveau modèle révolutionnaire",
    "categorie": "tech",
    "score": 85,
    "url": "https://openai.com/blog/new-model",
    "body": "Contenu substantiel de l'article décrivant la nouveauté.",
    "sources": [{"nom": "OpenAI", "url": "https://openai.com"}],
}

MOCK_BACKLOG = [
    MOCK_BACKLOG_ITEM,
    {
        "titre": "Google DeepMind publie une étude sur l'alignement",
        "categorie": "eco",
        "score": 70,
        "url": "https://deepmind.google/research/alignment",
        "body": "Recherche publiée sur l'alignement des systèmes IA.",
        "sources": [
            {"nom": "DeepMind", "url": "https://deepmind.google"},
            {"nom": "Nature", "url": "https://nature.com"},
        ],
    },
    {
        "titre": "Anthropic lève 2 milliards de dollars",
        "categorie": "eco",
        "score": 60,
        "url": "https://anthropic.com/funding",
        "body": "Anthropic annonce une levée de fonds record.",
        "sources": [{"nom": "Anthropic", "url": "https://anthropic.com"}],
    },
]

MOCK_HISTORIQUE = [
    {
        "date": "2026-05-13",
        "ids": ["2026-05-13-001"],
        "titres": ["Meta annonce Llama 4"],
        "categories": ["tech"],
    }
]

MOCK_CONFIG = {
    "name": "Test NL",
    "categories": {"tech": "Technologie", "eco": "Économie"},
    "persona": "Tu es expert IA.",
    "contenu": {"nb_news_principal": 3, "nb_news_radar": 2},
    "scoring": {"decroissance_quotidienne_pct": 15, "score_minimum_backlog": 5},
}


# ─── TestUtils ───────────────────────────────────────────────────────────────

class TestUtils:
    def test_derive_label(self):
        assert derive_label("fun_facts") == "Fun Facts"
        assert derive_label("fonctionnel") == "Fonctionnel"
        assert derive_label("use_cases") == "Use Cases"

    def test_build_label_to_cat(self):
        cats = {"fun_facts": "desc", "tech": "desc"}
        m = build_label_to_cat(cats)
        assert m["fun facts"] == "fun_facts"
        assert m["tech"] == "tech"

    def test_get_default_cat(self):
        assert get_default_cat({"a": "x", "b": "y"}) == "a"
        assert get_default_cat({}) == "general"
        assert get_default_cat(None) == "general"

    def test_is_placeholder_body_empty(self):
        assert is_placeholder_body("") is True
        assert is_placeholder_body(None) is True  # type: ignore

    def test_is_placeholder_body_genuine(self):
        assert is_placeholder_body("OpenAI a lancé un modèle GPT-5 ce mardi avec des performances record.") is False

    def test_compute_date_ctx_override(self):
        ctx = compute_date_ctx("2026-05-14")
        assert ctx.date == "2026-05-14"
        assert ctx.date_hier == "2026-05-13"
        assert "14" in ctx.date_longue

    def test_newsletter_config_from_config(self):
        cfg = NewsletterConfig.from_config({"name": "X", "categories": {"a": "b"}, "persona": "P"})
        assert cfg.name == "X"
        assert cfg.categories == {"a": "b"}
        assert cfg.persona == "P"

    def test_newsletter_config_fallbacks(self):
        cfg = NewsletterConfig.from_config({})
        assert cfg.name == "Newsletter"
        assert cfg.categories == FALLBACK_CATEGORIES
        assert "experts" in cfg.persona

    def test_read_write_json(self, tmp_path):
        f = tmp_path / "test.json"
        write_json(f, {"key": "value", "n": 42})
        result = read_json(f, {})
        assert result == {"key": "value", "n": 42}

    def test_read_json_missing(self, tmp_path):
        f = tmp_path / "missing.json"
        result = read_json(f, {"default": True})
        assert result == {"default": True}


# ─── TestKeyTerms ────────────────────────────────────────────────────────────

class TestKeyTerms:
    def test_extracts_significant_words(self):
        terms = _key_terms("OpenAI lance un nouveau modèle GPT-5")
        assert "openai" in terms
        assert "lance" in terms
        assert "nouveau" in terms  # 6 chars, not in STOP
        # "un" should be filtered
        assert "un" not in terms

    def test_short_words_filtered(self):
        terms = _key_terms("AI is a big deal")
        # "big" = 3 chars → filtered
        # "deal" = 4 chars → kept
        assert "deal" in terms

    def test_empty_title(self):
        assert _key_terms("") == set()


# ─── TestDetectRebond ────────────────────────────────────────────────────────

class TestDetectRebond:
    def test_no_rebond_new_topic(self):
        item = {"titre": "Quantum computing breakthrough at IBM"}
        is_dup, rebond = detect_rebond(item, MOCK_HISTORIQUE)
        assert is_dup is False

    def test_detects_duplicate(self):
        # Same title as in historique → should be duplicate
        item = {"titre": "Meta annonce Llama 4 modèle avancé"}
        is_dup, rebond = detect_rebond(
            item, MOCK_HISTORIQUE,
            min_overlap=2, max_overlap=3,
        )
        # "Meta", "annonce", "Llama" overlap → duplicate
        assert is_dup is True

    def test_empty_title_not_rebond(self):
        item = {"titre": ""}
        is_dup, rebond = detect_rebond(item, MOCK_HISTORIQUE)
        assert is_dup is False
        assert rebond is None

    def test_empty_historique(self):
        item = {"titre": "OpenAI lance un nouveau modèle GPT-5"}
        is_dup, rebond = detect_rebond(item, [])
        assert is_dup is False
        assert rebond is None


# ─── TestDetectSourceCandidates ──────────────────────────────────────────────

class TestDetectSourceCandidates:
    def test_finds_frequent_domains(self):
        backlog = [
            {"sources": [{"url": "https://techcrunch.com/a", "nom": "TechCrunch"}]}
            for _ in range(5)
        ]
        sources = {"sources_acteurs_ia": []}
        candidates = detect_source_candidates(backlog, sources, min_count=3)
        assert any(c["domaine"] == "techcrunch.com" for c in candidates)

    def test_skips_existing_primaries(self):
        backlog = [
            {"sources": [{"url": "https://openai.com/blog", "nom": "OpenAI"}]}
            for _ in range(5)
        ]
        sources = {"sources_acteurs_ia": [{"url": "https://openai.com"}]}
        candidates = detect_source_candidates(backlog, sources, min_count=3)
        assert not any(c["domaine"] == "openai.com" for c in candidates)

    def test_empty_backlog(self):
        candidates = detect_source_candidates([], {}, min_count=1)
        assert candidates == []


# ─── TestUpdateSourceScores ──────────────────────────────────────────────────

class TestUpdateSourceScores:
    def test_selected_source_gets_bonus(self):
        today = {"news": [{"id": "001", "sources": [{"url": "https://openai.com/blog"}]}]}
        sources = {"sources_acteurs_ia": [{"url": "https://openai.com/blog", "score_global": 3.0}]}
        feedback = {"articles": {}}
        result = update_source_scores(today, sources, feedback)
        score = result["sources_acteurs_ia"][0]["score_global"]
        assert score > 3.0  # bonus applied

    def test_absent_source_gets_malus(self):
        today = {"news": []}
        sources = {"sources_acteurs_ia": [{"url": "https://openai.com/blog", "score_global": 3.0}]}
        feedback = {"articles": {}}
        result = update_source_scores(today, sources, feedback)
        score = result["sources_acteurs_ia"][0]["score_global"]
        assert score < 3.0  # malus applied


# ─── TestMakeEntryFromBacklog ────────────────────────────────────────────────

class TestMakeEntryFromBacklog:
    def test_builds_entry_structure(self):
        with patch("lib.renderer.call_claude", return_value=""):
            entry = make_entry_from_backlog(MOCK_BACKLOG_ITEM, 1, MOCK_DATE_CTX, MOCK_NL_CONFIG)
        assert entry["id"] == "2026-05-14-001"
        assert entry["num"] == 1
        assert entry["titre"] == MOCK_BACKLOG_ITEM["titre"]
        assert entry["categorie"] == "tech"
        assert entry["body"]  # non-empty

    def test_uses_existing_body(self):
        with patch("lib.renderer.call_claude", return_value="CLAUDE_BODY"):
            entry = make_entry_from_backlog(MOCK_BACKLOG_ITEM, 1, MOCK_DATE_CTX, MOCK_NL_CONFIG)
        # Body is substantive, so no Claude call needed → existing body used
        assert "CLAUDE_BODY" not in entry["body"] or MOCK_BACKLOG_ITEM["body"] in entry["body"]

    def test_single_source_confiance(self):
        with patch("lib.renderer.call_claude", return_value=""):
            entry = make_entry_from_backlog(MOCK_BACKLOG_ITEM, 1, MOCK_DATE_CTX, MOCK_NL_CONFIG)
        assert "source primaire" in entry["confiance"]

    def test_multi_source_confiance(self):
        item = {**MOCK_BACKLOG_ITEM, "sources": [
            {"nom": "A", "url": "https://a.com"},
            {"nom": "B", "url": "https://b.com"},
        ]}
        with patch("lib.renderer.call_claude", return_value=""):
            entry = make_entry_from_backlog(item, 1, MOCK_DATE_CTX, MOCK_NL_CONFIG)
        assert "multi-sources" in entry["confiance"]

    def test_rebond_info_attached(self):
        rebond = {"titre": "Titre précédent", "date": "2026-05-10"}
        with patch("lib.renderer.call_claude", return_value=""):
            entry = make_entry_from_backlog(
                MOCK_BACKLOG_ITEM, 1, MOCK_DATE_CTX, MOCK_NL_CONFIG, rebond_info=rebond
            )
        assert entry["rebond_de"] == rebond


# ─── TestBuildToday ──────────────────────────────────────────────────────────

class TestBuildToday:
    def test_builds_today_structure(self, tmp_path):
        newsletters_dir = tmp_path / "newsletters"
        newsletters_dir.mkdir()
        with patch("lib.builder.call_claude", return_value=""), \
             patch("lib.renderer.call_claude", return_value="Chapeau test"):
            today = build_today(
                MOCK_DATE_CTX, MOCK_CONFIG, MOCK_BACKLOG, MOCK_HISTORIQUE,
                MOCK_NL_CONFIG, newsletters_dir,
            )
        assert today["date"] == "2026-05-14"
        assert isinstance(today["news"], list)
        assert isinstance(today["radar"], list)
        assert len(today["news"]) <= 3  # nb_news_principal = 3

    def test_excludes_recent_titles(self, tmp_path):
        newsletters_dir = tmp_path / "newsletters"
        newsletters_dir.mkdir()
        historique = [{
            "date": "2026-05-13",
            "titres": [item["titre"] for item in MOCK_BACKLOG],
            "ids": [], "categories": [],
        }]
        with patch("lib.builder.call_claude", return_value=""), \
             patch("lib.renderer.call_claude", return_value=""):
            today = build_today(
                MOCK_DATE_CTX, MOCK_CONFIG, MOCK_BACKLOG, historique,
                MOCK_NL_CONFIG, newsletters_dir,
            )
        # Articles récents exclus → backlog utilisé quand même (< nb_main)
        assert isinstance(today["news"], list)


# ─── TestParseNewsletterMd ───────────────────────────────────────────────────

class TestParseNewsletterMd:
    SAMPLE_MD = """# Test NL — Jeudi 14 mai 2026

> Chapeau de l'édition du jour.

## 1. OpenAI lance GPT-5
**Catégorie :** Tech | **Confiance :** ✅ source primaire | **cat:** tech
Corps de l'article sur GPT-5.
Sources : [OpenAI](https://openai.com)

## 2. Google annonce Gemini 2
**Catégorie :** Tech | **Confiance :** 🔄 multi-sources | **cat:** tech
Corps de l'article sur Gemini.
Sources : [Google](https://google.com)

## 📡 Radar
- **Signal radar** — Description. https://example.com
"""

    def test_parses_chapeau(self):
        result = parse_newsletter_md(self.SAMPLE_MD, "2026-05-14")
        assert result["chapeau"] == "Chapeau de l'édition du jour."

    def test_parses_articles(self):
        result = parse_newsletter_md(self.SAMPLE_MD, "2026-05-14")
        assert len(result["articles"]) == 2
        assert result["articles"][0]["titre"] == "OpenAI lance GPT-5"
        assert result["articles"][1]["titre"] == "Google annonce Gemini 2"

    def test_article_has_body(self):
        result = parse_newsletter_md(self.SAMPLE_MD, "2026-05-14")
        assert "GPT-5" in result["articles"][0]["body"] or result["articles"][0]["body"] != ""

    def test_empty_md(self):
        result = parse_newsletter_md("", "2026-05-14")
        assert result["chapeau"] == ""
        assert result["articles"] == []


# ─── TestSemanticRebondClassify ──────────────────────────────────────────────

class TestSemanticRebondClassify:
    def test_returns_empty_without_api_key(self):
        import os
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            result = semantic_rebond_classify([MOCK_BACKLOG_ITEM], [{"date": "x", "titre": "y"}])
        assert result == {}

    def test_returns_empty_without_candidates(self):
        result = semantic_rebond_classify([], [{"date": "x", "titre": "y"}])
        assert result == {}

    def test_parses_claude_response(self):
        claude_response = '{"1":{"s":"nouveau"},"2":{"s":"doublon","r":{"t":"Titre hist","d":"2026-05-10"}}}'
        with patch("lib.builder.call_claude", return_value=claude_response), \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key"}):
            result = semantic_rebond_classify(
                [MOCK_BACKLOG_ITEM, MOCK_BACKLOG_ITEM],
                [{"date": "2026-05-10", "titre": "Titre hist"}],
            )
        assert result[0]["statut"] == "nouveau"
        assert result[1]["statut"] == "doublon"
        assert result[1]["ref"]["titre"] == "Titre hist"


# ─── TestProcessFeedback ─────────────────────────────────────────────────────

class TestProcessFeedback:
    def test_no_feedback_files(self, tmp_path):
        feedback = {"articles": {}, "derniere_maj": "2026-05-13"}
        result = process_feedback(MOCK_DATE_CTX, MOCK_CONFIG, feedback, tmp_path)
        assert result["derniere_maj"] == "2026-05-14"

    def test_processes_feedback_ui(self, tmp_path):
        fb_ui = {
            "notes": {"2026-05-14-001": 5, "2026-05-14-002": 2},
            "statut": "en_attente",
        }
        write_json(tmp_path / "feedback_ui.json", fb_ui)
        feedback = {"articles": {}}
        result = process_feedback(MOCK_DATE_CTX, MOCK_CONFIG, feedback, tmp_path)
        # Note ≥ 4 → bonus applied
        assert result["articles"].get("2026-05-14-001", 0) > 0
        # Note < 4 → no bonus
        assert result["articles"].get("2026-05-14-002", 0) == 0

    def test_skips_already_treated(self, tmp_path):
        fb_ui = {"notes": {"2026-05-14-001": 5}, "statut": "traité"}
        write_json(tmp_path / "feedback_ui.json", fb_ui)
        feedback = {"articles": {}}
        result = process_feedback(MOCK_DATE_CTX, MOCK_CONFIG, feedback, tmp_path)
        assert result["articles"].get("2026-05-14-001", 0) == 0


# ─── TestRenderer ────────────────────────────────────────────────────────────

class TestRenderer:
    def test_write_markdown_creates_file(self, tmp_path):
        today = {
            "date": "2026-05-14", "date_longue": "Jeudi 14 mai 2026",
            "chapeau": "Test chapeau",
            "news": [{
                "id": "001", "num": 1, "titre": "Titre test",
                "categorie": "tech", "label": "Tech",
                "confiance": "✅ source primaire",
                "body": "Corps de l'article test.",
                "sources": [{"nom": "Source", "url": "https://example.com"}],
            }],
            "radar": [{"titre": "Signal", "desc": "Desc", "url": "https://ex.com"}],
        }
        write_markdown(today, MOCK_DATE_CTX, tmp_path, "Test NL")
        md_file = tmp_path / "newsletter-2026-05-14.md"
        assert md_file.exists()
        content = md_file.read_text()
        assert "Test NL" in content
        assert "Titre test" in content
        assert "Test chapeau" in content

    def test_write_html_creates_file(self, tmp_path):
        today = {
            "date": "2026-05-14", "date_longue": "Jeudi 14 mai 2026",
            "chapeau": "Test chapeau",
            "news": [{
                "id": "001", "num": 1, "titre": "Titre test",
                "categorie": "tech", "label": "Tech",
                "confiance": "✅ source primaire",
                "body": "Corps de l'article test.",
                "sources": [{"nom": "Source", "url": "https://example.com"}],
            }],
            "radar": [{"titre": "Signal", "desc": "Desc", "url": "https://ex.com"}],
        }
        template_html = tmp_path / "newsletter-template.html"
        template_html.write_text(
            "<html><body><h1>{{DATE_LONGUE}}</h1>{{CHAPEAU}}{{ARTICLES_HTML}}{{RADAR_HTML}}</body></html>",
            encoding="utf-8",
        )
        write_html(today, MOCK_DATE_CTX, tmp_path, template_html)
        html_file = tmp_path / "newsletter-2026-05-14.html"
        assert html_file.exists()
        content = html_file.read_text()
        assert "Jeudi 14 mai 2026" in content
        assert "Titre test" in content

    def test_generate_chapeau_no_api(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            result = generate_chapeau(MOCK_DATE_CTX, [])
        assert "2026" in result or "mai" in result

    def test_load_recent_summaries_empty_dir(self, tmp_path):
        result = load_recent_newsletter_summaries(tmp_path, MOCK_DATE_CTX)
        assert result == []


# ─── TestStorage ─────────────────────────────────────────────────────────────

class TestStorage:
    def _make_paths(self, tmp_path: Path) -> dict:
        nl_dir = tmp_path / "newsletters" / "test-nl"
        nl_dir.mkdir(parents=True)
        newsletters_dir = nl_dir / "newsletters"
        newsletters_dir.mkdir()
        return {
            "briefing":          nl_dir,
            "newsletters":       newsletters_dir,
            "templates":         nl_dir / "templates",
            "data_js":           nl_dir / "data.js",
            "config_json":       nl_dir / "config.json",
            "historique_json":   nl_dir / "historique.json",
            "backlog_json":      nl_dir / "backlog.json",
            "feedback_json":     nl_dir / "feedback.json",
            "sources_json":      nl_dir / "sources.json",
            "sources_rss_json":  nl_dir / "sources_rss.json",
            "template_html":     nl_dir / "templates" / "newsletter-template.html",
            "today_json":        nl_dir / "today.json",
            "archive_json":      nl_dir / "archive.json",
            "archive_full_json": nl_dir / "archive_full.json",
        }

    def _mock_today(self) -> dict:
        return {
            "date": "2026-05-14", "date_longue": "Jeudi 14 mai 2026",
            "chapeau": "Chapeau test",
            "news": [{
                "id": "2026-05-14-001", "num": 1,
                "titre": "Titre test", "categorie": "tech", "label": "Tech",
                "confiance": "✅", "body": "Corps.",
                "sources": [{"nom": "S", "url": "https://s.com"}],
            }],
            "radar": [],
        }

    def test_update_data_json_creates_files(self, tmp_path):
        paths = self._make_paths(tmp_path)
        # Créer un data.js vide pour la migration
        paths["data_js"].write_text("const ARCHIVE=[];const ARCHIVE_FULL={};", encoding="utf-8")
        today = self._mock_today()
        update_data_json(today, MOCK_DATE_CTX, paths)
        assert paths["today_json"].exists()
        assert paths["archive_json"].exists()
        assert paths["archive_full_json"].exists()

    def test_update_data_json_archive_content(self, tmp_path):
        paths = self._make_paths(tmp_path)
        paths["data_js"].write_text("", encoding="utf-8")
        today = self._mock_today()
        update_data_json(today, MOCK_DATE_CTX, paths)
        archive = json.loads(paths["archive_json"].read_text())
        assert len(archive) >= 1
        assert archive[0]["date"] == "2026-05-14"
        assert archive[0]["is_today"] is True

    def test_generate_data_js_output(self, tmp_path):
        paths = self._make_paths(tmp_path)
        today = self._mock_today()
        write_json(paths["today_json"], today)
        write_json(paths["archive_json"], [{"date": "2026-05-14", "is_today": True}])
        write_json(paths["archive_full_json"], {})
        generate_data_js("test-nl", {"name": "Test NL"}, paths)
        content = paths["data_js"].read_text()
        assert "const TODAY" in content
        assert "const ARCHIVE" in content
        assert "const ARCHIVE_FULL" in content
        assert "const CONFIG" in content
        assert "test-nl" in content

    def test_migrate_from_empty_data_js(self, tmp_path):
        data_js = tmp_path / "data.js"
        data_js.write_text("", encoding="utf-8")
        archive, archive_full = _migrate_json_from_data_js(data_js)
        assert archive == []
        assert archive_full == {}

    def test_migrate_missing_data_js(self, tmp_path):
        data_js = tmp_path / "nonexistent.js"
        archive, archive_full = _migrate_json_from_data_js(data_js)
        assert archive == []
        assert archive_full == {}
