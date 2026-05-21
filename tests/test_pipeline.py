"""
tests/test_pipeline.py
Test d'intégration : pipeline complet daily_briefing_workflow.py

Simule un run complet (sans appel Claude ni réseau) depuis un répertoire temporaire
isolé. Vérifie que tous les fichiers attendus sont produits avec la bonne structure.

Approche :
  - Crée un slug de test minimal (fixtures JSON) dans tmp_path
  - Mocke call_claude → retourne des valeurs vides (mode dégradé)
  - Exécute daily_briefing_workflow.main() directement
  - Vérifie les sorties : today.json, archive.json, data.js, newsletter-*.html
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT    = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


# ── Fixtures minimales ────────────────────────────────────────────────────────

FIXTURE_CONFIG = {
    "name": "Test Pipeline NL",
    "categories": {
        "fonctionnel": "Outils et modèles IA",
        "economie":    "Business et marché",
    },
    "persona": "Tu es un expert IA synthétique.",
    "contenu": {
        "nb_news_principal": 2,
        "nb_news_radar":     1,
    },
    "scoring": {
        "decroissance_quotidienne_pct": 15,
        "score_minimum_backlog": 5,
    },
}

FIXTURE_BACKLOG = [
    {
        "titre":     "OpenAI lance un modèle révolutionnaire pour l'entreprise",
        "categorie": "fonctionnel",
        "label":     "Fonctionnel",
        "score":     90,
        "url":       "https://openai.com/blog/new-model",
        "body":      "OpenAI a annoncé ce mardi le lancement d'un nouveau modèle destiné aux entreprises.",
        "sources":   [{"nom": "OpenAI", "url": "https://openai.com/blog/new-model"}],
        "_duplicate": False,
    },
    {
        "titre":     "Anthropic lève deux milliards de dollars en Série D",
        "categorie": "economie",
        "label":     "Economie",
        "score":     80,
        "url":       "https://anthropic.com/funding",
        "body":      "Anthropic annonce une levée de fonds record de deux milliards de dollars.",
        "sources":   [{"nom": "Anthropic", "url": "https://anthropic.com/funding"}],
        "_duplicate": False,
    },
    {
        "titre":     "Google DeepMind publie une étude sur l'alignement des LLMs",
        "categorie": "fonctionnel",
        "label":     "Fonctionnel",
        "score":     70,
        "url":       "https://deepmind.google/alignment",
        "body":      "DeepMind publie des résultats prometteurs sur l'alignement des modèles de langage.",
        "sources":   [{"nom": "DeepMind", "url": "https://deepmind.google/alignment"}],
        "_duplicate": False,
    },
]

FIXTURE_SOURCES_RSS = {
    "feeds": [
        {"nom": "OpenAI Blog", "url": "https://openai.com/blog/rss.xml", "fiabilite": 90},
    ],
    "max_tavily_calls": 0,
}

FIXTURE_HISTORIQUE: list = []
FIXTURE_FEEDBACK = {"articles": {}, "derniere_maj": "2026-05-13"}
FIXTURE_SOURCES = {"sources_acteurs_ia": [], "sources_relais": [], "sources_decouvertes": []}

FIXTURE_TEMPLATE_HTML = """\
<!DOCTYPE html>
<html lang="fr">
<head><title>{{NL_NAME}} — {{DATE_LONGUE}}</title></head>
<body>
<h1>{{DATE_LONGUE}}</h1>
<p>{{CHAPEAU}}</p>
{{ARTICLES_HTML}}
{{RADAR_HTML}}
</body>
</html>
"""

TEST_DATE = "2026-05-14"


# ── Setup du répertoire de test ───────────────────────────────────────────────

def setup_test_newsletter(tmp_path: Path, slug: str = "test-pipeline") -> tuple[Path, dict]:
    """
    Crée la structure de fichiers minimale pour une newsletter de test.
    Retourne (racine_projet_fictive, dict_chemins).
    """
    # Structure : tmp_path/newsletters/{slug}/...
    nl_dir   = tmp_path / "newsletters" / slug
    tmpl_dir = nl_dir / "templates"
    news_dir = nl_dir / "newsletters"
    for d in (nl_dir, tmpl_dir, news_dir):
        d.mkdir(parents=True)

    def jwrite(path: Path, data) -> None:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    jwrite(nl_dir / "config.json",      FIXTURE_CONFIG)
    jwrite(nl_dir / "backlog.json",     FIXTURE_BACKLOG)
    jwrite(nl_dir / "historique.json",  FIXTURE_HISTORIQUE)
    jwrite(nl_dir / "feedback.json",    FIXTURE_FEEDBACK)
    jwrite(nl_dir / "feedback_ui.json", {"notes": {}, "statut": "traité"})
    jwrite(nl_dir / "sources.json",     FIXTURE_SOURCES)
    jwrite(nl_dir / "sources_rss.json", FIXTURE_SOURCES_RSS)
    (tmpl_dir / "newsletter-template.html").write_text(FIXTURE_TEMPLATE_HTML, encoding="utf-8")

    # index.json à la racine newsletters/
    index_path = tmp_path / "newsletters" / "index.json"
    index_path.write_text(json.dumps({
        "newsletters": [{"slug": slug, "name": "Test Pipeline NL", "status": "active"}]
    }, ensure_ascii=False), encoding="utf-8")

    paths = {
        "briefing":          nl_dir,
        "newsletters":       news_dir,
        "templates":         tmpl_dir,
        "data_js":           nl_dir / "data.js",
        "config_json":       nl_dir / "config.json",
        "historique_json":   nl_dir / "historique.json",
        "backlog_json":      nl_dir / "backlog.json",
        "feedback_json":     nl_dir / "feedback.json",
        "sources_json":      nl_dir / "sources.json",
        "sources_rss_json":  nl_dir / "sources_rss.json",
        "template_html":     tmpl_dir / "newsletter-template.html",
        "today_json":        nl_dir / "today.json",
        "archive_json":      nl_dir / "archive.json",
        "archive_full_json": nl_dir / "archive_full.json",
    }
    return tmp_path, paths


# ═══════════════════════════════════════════════════════════════════════════════
# Test d'intégration pipeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    """
    Exécute build_today → update_data_json → generate_data_js → write_markdown → write_html
    avec Claude mocké (mode dégradé), sans réseau.
    """

    @pytest.fixture
    def pipeline_paths(self, tmp_path):
        _, paths = setup_test_newsletter(tmp_path)
        return paths

    def _run_pipeline(self, paths: dict) -> dict:
        """
        Lance le pipeline de génération de bout en bout en important
        directement les fonctions lib/ (sans passer par subprocess).
        """
        from lib.builder import build_today, process_feedback
        from lib.renderer import write_markdown, write_html
        from lib.storage import generate_data_js, update_data_json, update_annexes
        from lib.utils import NewsletterConfig, compute_date_ctx, read_json, write_json

        date_ctx  = compute_date_ctx(TEST_DATE)
        config    = json.loads(paths["config_json"].read_text())
        backlog   = json.loads(paths["backlog_json"].read_text())
        historique = json.loads(paths["historique_json"].read_text())
        feedback  = json.loads(paths["feedback_json"].read_text())
        sources   = json.loads(paths["sources_json"].read_text())
        nl_config = NewsletterConfig.from_config(config)

        with patch("lib.builder.call_claude", return_value=""), \
             patch("lib.renderer.call_claude", return_value="Édition du jour."):

            feedback = process_feedback(date_ctx, config, feedback, paths["briefing"])
            today    = build_today(date_ctx, config, backlog, historique, nl_config, paths["newsletters"])
            write_markdown(today, date_ctx, paths["newsletters"], config.get("name", "Test"))
            write_html(today, date_ctx, paths["newsletters"], paths["template_html"])

        update_data_json(today, date_ctx, paths)
        generate_data_js("test-pipeline", config, paths)
        update_annexes(today, date_ctx, config, backlog, historique, sources, feedback, paths)

        return today

    # ── Fichiers produits ──────────────────────────────────────────────────────

    def test_today_json_created(self, pipeline_paths):
        self._run_pipeline(pipeline_paths)
        assert pipeline_paths["today_json"].exists(), "today.json doit être créé"

    def test_archive_json_created(self, pipeline_paths):
        self._run_pipeline(pipeline_paths)
        assert pipeline_paths["archive_json"].exists(), "archive.json doit être créé"

    def test_archive_full_json_created(self, pipeline_paths):
        self._run_pipeline(pipeline_paths)
        assert pipeline_paths["archive_full_json"].exists(), "archive_full.json doit être créé"

    def test_data_js_created(self, pipeline_paths):
        self._run_pipeline(pipeline_paths)
        assert pipeline_paths["data_js"].exists(), "data.js doit être créé"

    def test_html_newsletter_created(self, pipeline_paths):
        self._run_pipeline(pipeline_paths)
        html_files = list(pipeline_paths["newsletters"].glob("newsletter-*.html"))
        assert len(html_files) >= 1, "Au moins un fichier HTML de newsletter doit être créé"

    def test_md_newsletter_created(self, pipeline_paths):
        self._run_pipeline(pipeline_paths)
        md_files = list(pipeline_paths["newsletters"].glob("newsletter-*.md"))
        assert len(md_files) >= 1, "Au moins un fichier Markdown de newsletter doit être créé"

    # ── Structure de today ─────────────────────────────────────────────────────

    def test_today_json_has_required_keys(self, pipeline_paths):
        today = self._run_pipeline(pipeline_paths)
        for key in ("date", "date_longue", "chapeau", "news", "radar"):
            assert key in today, f"Clé '{key}' manquante dans today"

    def test_today_date_matches(self, pipeline_paths):
        today = self._run_pipeline(pipeline_paths)
        assert today["date"] == TEST_DATE

    def test_news_count_respects_config(self, pipeline_paths):
        today = self._run_pipeline(pipeline_paths)
        nb_max = FIXTURE_CONFIG["contenu"]["nb_news_principal"]
        assert len(today["news"]) <= nb_max, (
            f"today['news'] contient {len(today['news'])} articles, max={nb_max}"
        )

    def test_news_items_have_required_fields(self, pipeline_paths):
        today = self._run_pipeline(pipeline_paths)
        for item in today["news"]:
            for field in ("id", "num", "titre", "categorie", "label", "body", "sources"):
                assert field in item, f"Champ '{field}' manquant dans news item: {item.get('titre', '?')}"

    def test_news_ids_are_unique(self, pipeline_paths):
        today = self._run_pipeline(pipeline_paths)
        ids = [item["id"] for item in today["news"]]
        assert len(ids) == len(set(ids)), "Les IDs des articles doivent être uniques"

    # ── Structure archive ──────────────────────────────────────────────────────

    def test_archive_json_structure(self, pipeline_paths):
        self._run_pipeline(pipeline_paths)
        archive = json.loads(pipeline_paths["archive_json"].read_text())
        assert isinstance(archive, list)
        assert len(archive) >= 1
        assert archive[0]["date"] == TEST_DATE
        assert archive[0]["is_today"] is True

    # ── Structure data.js ──────────────────────────────────────────────────────

    def test_data_js_contains_all_constants(self, pipeline_paths):
        self._run_pipeline(pipeline_paths)
        content = pipeline_paths["data_js"].read_text()
        for const in ("const TODAY", "const ARCHIVE", "const ARCHIVE_FULL", "const CONFIG"):
            assert const in content, f"Constante '{const}' manquante dans data.js"

    def test_data_js_today_is_valid_json(self, pipeline_paths):
        """TODAY dans data.js doit être parseable."""
        self._run_pipeline(pipeline_paths)
        content = pipeline_paths["data_js"].read_text()
        # Extraire la valeur de TODAY
        start = content.index("const TODAY = ") + len("const TODAY = ")
        end   = content.index(";\n\nconst ARCHIVE=", start)
        today_raw = content[start:end]
        parsed = json.loads(today_raw)
        assert parsed["date"] == TEST_DATE

    # ── Backlog mis à jour ─────────────────────────────────────────────────────

    def test_published_articles_removed_from_backlog(self, pipeline_paths):
        """Les articles publiés dans today.news doivent disparaître du backlog."""
        today = self._run_pipeline(pipeline_paths)
        updated_backlog = json.loads(pipeline_paths["backlog_json"].read_text())
        published_titles = {n["titre"] for n in today["news"]}
        backlog_titles   = {b["titre"] for b in updated_backlog}
        overlap = published_titles & backlog_titles
        assert not overlap, f"Ces titres publiés restent dans le backlog : {overlap}"

    # ── Idempotence ────────────────────────────────────────────────────────────

    def test_second_run_does_not_duplicate_archive(self, pipeline_paths):
        """Un deuxième run à la même date ne doit pas dupliquer l'entrée dans archive."""
        self._run_pipeline(pipeline_paths)
        self._run_pipeline(pipeline_paths)
        archive = json.loads(pipeline_paths["archive_json"].read_text())
        dates = [a["date"] for a in archive if a["date"] == TEST_DATE]
        assert len(dates) == 1, "La date ne doit apparaître qu'une fois dans l'archive"


# ═══════════════════════════════════════════════════════════════════════════════
# Test de la migration data.js → JSON
# ═══════════════════════════════════════════════════════════════════════════════

class TestMigrationDataJs:
    """
    Vérifie que _migrate_json_from_data_js() extrait correctement
    les données depuis un data.js existant (cas de premier run).
    """

    def test_migrates_archive_from_data_js(self, tmp_path):
        from lib.storage import _migrate_json_from_data_js

        data_js = tmp_path / "data.js"
        data_js.write_text(
            'const ARCHIVE=[{"date":"2026-05-13","is_today":false}];\n'
            'const ARCHIVE_FULL={"2026-05-13":{"chapeau":"Test","articles":[]}};\n',
            encoding="utf-8",
        )
        archive, archive_full = _migrate_json_from_data_js(data_js)
        assert len(archive) == 1
        assert archive[0]["date"] == "2026-05-13"
        assert "2026-05-13" in archive_full

    def test_handles_nested_json_in_archive(self, tmp_path):
        """L'extracteur bracket-balanced doit gérer les structures imbriquées."""
        from lib.storage import _migrate_json_from_data_js

        data_js = tmp_path / "data.js"
        nested_archive = json.dumps([
            {
                "date": "2026-05-13",
                "news": [
                    {"titre": "Article 1", "categorie": "tech"},
                    {"titre": "Article 2 avec des [crochets] dans le titre", "categorie": "eco"},
                ],
                "is_today": False,
            }
        ])
        data_js.write_text(
            f"const ARCHIVE={nested_archive};\nconst ARCHIVE_FULL={{}};\n",
            encoding="utf-8",
        )
        archive, _ = _migrate_json_from_data_js(data_js)
        assert len(archive) == 1
        assert len(archive[0]["news"]) == 2
        # Le titre avec des crochets doit être préservé intact
        assert "crochets" in archive[0]["news"][1]["titre"]

    def test_empty_data_js_returns_defaults(self, tmp_path):
        from lib.storage import _migrate_json_from_data_js

        data_js = tmp_path / "data.js"
        data_js.write_text("", encoding="utf-8")
        archive, archive_full = _migrate_json_from_data_js(data_js)
        assert archive == []
        assert archive_full == {}
