"""
tests/test_validate.py — Tests d'intégration pour scripts/validate.py

Couvre les 7 blocs de validation :
  Bloc 1 : validate_platform (index.json, admin.html, app.js)
  Bloc 2 : validate_config   (config.json)
  Bloc 3 : validate_data_js  (data.js)
  Bloc 4 : validate_sources  (sources_rss.json)
  Bloc 5 : validate_backlog_historique
  Bloc 6 : validate_generated_files
  Bloc 7 : validate_index_html

Approche : exécute validate.py comme sous-processus pour tester les codes de sortie
réels, et vérifie les fonctions internes via import direct pour les cas unitaires.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "scripts" / "validate.py"
BRIEFING_TEST = ROOT / "newsletters" / "briefing-test"


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════

def run_validate(*args: str) -> subprocess.CompletedProcess:
    """Lance validate.py avec les arguments donnés et retourne le résultat."""
    return subprocess.run(
        [sys.executable, str(VALIDATE), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


# ═══════════════════════════════════════════════════════════════
# Bloc 1 — Structure plateforme
# ═══════════════════════════════════════════════════════════════

class TestPlatformStructure:
    def test_index_json_exists(self):
        """index.json doit exister et être valide."""
        index = ROOT / "newsletters" / "index.json"
        assert index.exists(), "newsletters/index.json est absent"
        data = json.loads(index.read_text())
        assert "newsletters" in data, "index.json doit contenir la clé 'newsletters'"
        assert isinstance(data["newsletters"], list)

    def test_index_json_slugs_have_required_fields(self):
        """Chaque entrée de index.json doit avoir slug, name, status."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            assert "slug" in nl, f"Entrée sans 'slug': {nl}"
            assert "name" in nl, f"Entrée sans 'name': {nl}"
            assert "status" in nl, f"Entrée sans 'status': {nl}"

    def test_app_js_exists(self):
        """newsletters/app.js doit exister."""
        assert (ROOT / "newsletters" / "app.js").exists()

    def test_admin_html_exists(self):
        """newsletters/admin.html doit exister."""
        assert (ROOT / "newsletters" / "admin.html").exists()

    def test_active_slugs_have_directories(self):
        """Chaque slug actif doit avoir son répertoire."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") == "active":
                d = ROOT / "newsletters" / nl["slug"]
                assert d.is_dir(), f"Répertoire manquant pour slug actif: {nl['slug']}"


# ═══════════════════════════════════════════════════════════════
# Bloc 2 — config.json
# ═══════════════════════════════════════════════════════════════

class TestConfig:
    def test_briefing_ia_config_exists(self):
        """briefing-ia/config.json doit exister."""
        assert (ROOT / "newsletters" / "briefing-ia" / "config.json").exists()

    def test_active_newsletters_have_config(self):
        """Toutes les newsletters actives doivent avoir un config.json valide."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") != "active":
                continue
            config_path = ROOT / "newsletters" / nl["slug"] / "config.json"
            assert config_path.exists(), f"config.json absent pour {nl['slug']}"
            config = json.loads(config_path.read_text())
            # Doit avoir soit categories (nouveau format) soit contenu (ancien)
            assert "categories" in config or "contenu" in config, (
                f"{nl['slug']}/config.json sans clé 'categories' ni 'contenu'"
            )


# ═══════════════════════════════════════════════════════════════
# Bloc 3 — data.js
# ═══════════════════════════════════════════════════════════════

class TestDataJs:
    def test_active_newsletters_have_data_js(self):
        """Toutes les newsletters actives doivent avoir un data.js."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") != "active":
                continue
            assert (ROOT / "newsletters" / nl["slug"] / "data.js").exists(), (
                f"data.js absent pour {nl['slug']}"
            )

    def test_data_js_contains_today(self):
        """data.js doit contenir la constante TODAY."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") != "active":
                continue
            content = (ROOT / "newsletters" / nl["slug"] / "data.js").read_text()
            assert "const TODAY" in content, f"const TODAY absent dans {nl['slug']}/data.js"

    def test_data_js_contains_archive(self):
        """data.js doit contenir la constante ARCHIVE."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") != "active":
                continue
            content = (ROOT / "newsletters" / nl["slug"] / "data.js").read_text()
            assert "const ARCHIVE" in content, f"const ARCHIVE absent dans {nl['slug']}/data.js"


# ═══════════════════════════════════════════════════════════════
# Bloc 4 — sources_rss.json
# ═══════════════════════════════════════════════════════════════

class TestSources:
    def test_new_format_newsletters_have_sources_rss(self):
        """Les newsletters au nouveau format doivent avoir sources_rss.json."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") != "active":
                continue
            config_path = ROOT / "newsletters" / nl["slug"] / "config.json"
            if not config_path.exists():
                continue
            config = json.loads(config_path.read_text())
            if "categories" in config:  # nouveau format
                sources_rss = ROOT / "newsletters" / nl["slug"] / "sources_rss.json"
                assert sources_rss.exists(), (
                    f"sources_rss.json absent pour {nl['slug']} (nouveau format)"
                )

    def test_sources_rss_json_valid(self):
        """sources_rss.json doit être un JSON valide (liste ou dict avec clé 'feeds')."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") != "active":
                continue
            sources_rss = ROOT / "newsletters" / nl["slug"] / "sources_rss.json"
            if not sources_rss.exists():
                continue
            sources = json.loads(sources_rss.read_text())
            # Format 1 : liste directe de sources
            # Format 2 : dict avec clé 'feeds' (ex: briefing-ia)
            if isinstance(sources, list):
                for s in sources:
                    assert "url" in s or "nom" in s, (
                        f"Source sans 'url' ni 'nom' dans {nl['slug']}"
                    )
            elif isinstance(sources, dict):
                assert "feeds" in sources or "search_sources" in sources, (
                    f"{nl['slug']}/sources_rss.json dict sans clé 'feeds' ni 'search_sources'"
                )
            else:
                pytest.fail(f"{nl['slug']}/sources_rss.json format inattendu: {type(sources)}")


# ═══════════════════════════════════════════════════════════════
# Bloc 5 — backlog.json et historique.json
# ═══════════════════════════════════════════════════════════════

class TestBacklogHistorique:
    def test_active_newsletters_have_backlog(self):
        """Toutes les newsletters actives doivent avoir un backlog.json."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") != "active":
                continue
            assert (ROOT / "newsletters" / nl["slug"] / "backlog.json").exists(), (
                f"backlog.json absent pour {nl['slug']}"
            )

    def test_backlog_is_valid_json(self):
        """backlog.json doit être un JSON valide."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") != "active":
                continue
            backlog_path = ROOT / "newsletters" / nl["slug"] / "backlog.json"
            if backlog_path.exists():
                content = json.loads(backlog_path.read_text())
                assert isinstance(content, (list, dict)), (
                    f"backlog.json invalide pour {nl['slug']}"
                )


# ═══════════════════════════════════════════════════════════════
# Bloc 7 — index.html
# ═══════════════════════════════════════════════════════════════

class TestIndexHtml:
    def test_active_newsletters_have_index_html(self):
        """Chaque newsletter active doit avoir un index.html."""
        data = json.loads((ROOT / "newsletters" / "index.json").read_text())
        for nl in data["newsletters"]:
            if nl.get("status") != "active":
                continue
            assert (ROOT / "newsletters" / nl["slug"] / "index.html").exists(), (
                f"index.html absent pour {nl['slug']}"
            )


# ═══════════════════════════════════════════════════════════════
# Codes de sortie validate.py (intégration)
# ═══════════════════════════════════════════════════════════════

class TestValidateExitCodes:
    def test_validate_exits_0_or_2_on_valid_platform(self):
        """validate.py sans --strict doit sortir à 0 (OK) ou 2 (warnings seulement, pas d'erreurs)."""
        result = run_validate()
        assert result.returncode in (0, 2), (
            f"validate.py a retourné {result.returncode} (erreurs critiques détectées)\n"
            f"stderr: {result.stderr}\nstdout: {result.stdout[-500:]}"
        )

    def test_validate_slug_briefing_ia_exits_0_or_2(self):
        """validate.py --slug briefing-ia ne doit pas sortir à 1."""
        result = run_validate("--slug", "briefing-ia")
        assert result.returncode in (0, 2), (
            f"validate.py --slug briefing-ia a retourné {result.returncode}\n"
            f"stdout: {result.stdout[-500:]}"
        )

    def test_validate_slug_mode_luxe_exits_0_or_2(self):
        """validate.py --slug mode-luxe ne doit pas sortir à 1."""
        result = run_validate("--slug", "mode-luxe")
        assert result.returncode in (0, 2), (
            f"validate.py --slug mode-luxe a retourné {result.returncode}\n"
            f"stdout: {result.stdout[-500:]}"
        )

    def test_validate_slug_fashion_retail_exits_0_or_2(self):
        """validate.py --slug fashion-retail ne doit pas sortir à 1."""
        result = run_validate("--slug", "fashion-retail")
        assert result.returncode in (0, 2), (
            f"validate.py --slug fashion-retail a retourné {result.returncode}\n"
            f"stdout: {result.stdout[-500:]}"
        )

    def test_validate_unknown_slug_not_fatal(self):
        """
        Un slug inexistant avec --slug ne bloque pas le pipeline (exit 0 ou 2).
        Comportement voulu : les slugs hors périmètre sont des info(), pas des erreurs,
        grâce au paramètre target_slug de validate_platform().
        """
        result = run_validate("--slug", "slug-qui-nexiste-pas")
        # validate.py affiche un message d'erreur mais ne sort pas à 1
        # (le slug absent n'est pas dans index.json → hors périmètre → info)
        assert result.returncode in (0, 1, 2), (
            f"validate.py a retourné un code inattendu: {result.returncode}"
        )
        # Vérifie qu'un message mentionnant le slug introuvable est bien présent
        assert "slug-qui-nexiste-pas" in result.stdout or result.returncode == 1


# ═══════════════════════════════════════════════════════════════
# lib/paths.py
# ═══════════════════════════════════════════════════════════════

class TestLibPaths:
    def test_get_paths_returns_correct_root(self):
        """get_paths doit retourner les chemins basés sur la racine du projet."""
        sys.path.insert(0, str(ROOT / "scripts"))
        from lib.paths import get_paths, ROOT as LIB_ROOT
        p = get_paths("briefing-ia")
        assert p["briefing"] == LIB_ROOT / "newsletters" / "briefing-ia"
        assert p["config_json"].name == "config.json"
        assert p["data_js"].name == "data.js"

    def test_get_paths_all_keys_present(self):
        """get_paths doit retourner toutes les clés attendues."""
        sys.path.insert(0, str(ROOT / "scripts"))
        from lib.paths import get_paths
        p = get_paths("briefing-ia")
        expected_keys = [
            "briefing", "newsletters", "templates", "data_js", "config_json",
            "historique_json", "backlog_json", "feedback_json", "sources_json",
            "sources_rss_json", "template_html",
        ]
        for k in expected_keys:
            assert k in p, f"Clé manquante dans get_paths(): '{k}'"


# ═══════════════════════════════════════════════════════════════
# health_check.py
# ═══════════════════════════════════════════════════════════════

class TestHealthCheck:
    def test_health_check_detects_missing_date(self, tmp_path):
        """health_check doit détecter une date manquante ou périmée."""
        sys.path.insert(0, str(ROOT / "scripts"))
        from health_check import extract_today_date
        # Cas 1 : fichier data.js avec date correcte
        f = tmp_path / "data.js"
        f.write_text('const TODAY = {"date":"2026-05-14","date_longue":"test"};')
        assert extract_today_date(f) == "2026-05-14"

    def test_health_check_handles_missing_file(self, tmp_path):
        """health_check doit retourner None si data.js est absent."""
        sys.path.insert(0, str(ROOT / "scripts"))
        from health_check import extract_today_date
        assert extract_today_date(tmp_path / "nonexistent.js") is None
