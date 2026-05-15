#!/usr/bin/env python3
"""
scripts/daily_briefing_workflow.py
Orchestrateur principal — délègue toute la logique aux modules lib/.

Usage :
    python scripts/daily_briefing_workflow.py --slug briefing-ia
    python scripts/daily_briefing_workflow.py --slug briefing-ia --date 2026-05-14
    python scripts/daily_briefing_workflow.py --slug briefing-ia --validate-only
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# ── Résolution du sys.path (lib/ doit être trouvé) ────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))

# ── Modules lib/ ──────────────────────────────────────────────────────────────
from lib.builder import build_today, process_feedback       # noqa: E402
from lib.paths import ROOT as _ROOT, get_paths as _get_paths  # noqa: E402
from lib.renderer import write_markdown, write_html         # noqa: E402
from lib.storage import generate_data_js, update_annexes, update_data_json  # noqa: E402
from lib.utils import (                                      # noqa: E402
    NewsletterConfig,
    compute_date_ctx,
    read_json,
    write_json,
)

ROOT = _ROOT  # réexposé pour rétrocompatibilité

# ── Chemins — initialisés dans _init_paths() ──────────────────────────────────
BRIEFING: Path
NEWSLETTERS: Path
TEMPLATES: Path
DATA_JS: Path
CONFIG_JSON: Path
HISTORIQUE_JSON: Path
BACKLOG_JSON: Path
FEEDBACK_JSON: Path
SOURCES_JSON: Path
TEMPLATE_HTML: Path
TODAY_JSON: Path
ARCHIVE_JSON: Path
ARCHIVE_FULL_JSON: Path

_PATHS: dict[str, Path] = {}


def _init_paths(slug: str) -> None:
    """Initialise les constantes de chemin — délègue à lib.paths.get_paths()."""
    global BRIEFING, NEWSLETTERS, TEMPLATES, DATA_JS, CONFIG_JSON
    global HISTORIQUE_JSON, BACKLOG_JSON, FEEDBACK_JSON, SOURCES_JSON, TEMPLATE_HTML
    global TODAY_JSON, ARCHIVE_JSON, ARCHIVE_FULL_JSON, _PATHS
    p = _get_paths(slug)
    _PATHS            = p
    BRIEFING          = p["briefing"]
    NEWSLETTERS       = p["newsletters"]
    TEMPLATES         = p["templates"]
    DATA_JS           = p["data_js"]
    CONFIG_JSON       = p["config_json"]
    HISTORIQUE_JSON   = p["historique_json"]
    BACKLOG_JSON      = p["backlog_json"]
    FEEDBACK_JSON     = p["feedback_json"]
    SOURCES_JSON      = p["sources_json"]
    TEMPLATE_HTML     = p["template_html"]
    TODAY_JSON        = p["today_json"]
    ARCHIVE_JSON      = p["archive_json"]
    ARCHIVE_FULL_JSON = p["archive_full_json"]


# ── Initialisation des fichiers (premier run) ─────────────────────────────────

from lib.utils import FALLBACK_CATEGORIES, FALLBACK_PERSONA  # noqa: E402


def ensure_files(date_ctx) -> None:
    NEWSLETTERS.mkdir(parents=True, exist_ok=True)
    TEMPLATES.mkdir(parents=True, exist_ok=True)

    if not CONFIG_JSON.exists():
        write_json(CONFIG_JSON, {
            "contenu": {"nb_news_principal": 5, "nb_news_radar": 5},
            "persona": FALLBACK_PERSONA,
            "categories": FALLBACK_CATEGORIES,
            "scoring": {
                "poids": {
                    "fraicheur": 30, "reprise_multi_sources": 25,
                    "impact_sectoriel": 20, "originalite": 15, "engagement_potentiel": 10,
                },
                "decroissance_quotidienne_pct": 15,
                "bonus_feedback_pts": 10,
                "score_minimum_backlog": 10,
            },
        })

    if not HISTORIQUE_JSON.exists():
        write_json(HISTORIQUE_JSON, [])
    if not BACKLOG_JSON.exists():
        write_json(BACKLOG_JSON, [])
    if not FEEDBACK_JSON.exists():
        write_json(FEEDBACK_JSON, {"articles": {}, "derniere_maj": date_ctx.date})
    if not SOURCES_JSON.exists():
        write_json(SOURCES_JSON, {"sources_decouvertes": [], "derniere_maj": date_ctx.date})

    if not TEMPLATE_HTML.exists():
        from lib.utils import NewsletterConfig
        nl_name = "Newsletter"  # sera surchargé après lecture config
        TEMPLATE_HTML.write_text(
            f"<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
            f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{nl_name}</title>"
            f"<style>body{{font-family:Arial,sans-serif;max-width:900px;margin:24px auto;"
            f"padding:0 16px;color:#1f2937}}h1{{font-size:28px}}h2{{font-size:21px;"
            f"margin-top:28px}}.meta{{color:#4b5563;font-size:14px;margin-bottom:12px}}"
            f".box{{border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin:16px 0}}"
            f".radar li{{margin:10px 0}}</style></head>"
            f"<body><h1>{nl_name} — {{{{DATE_LONGUE}}}}</h1>"
            f"<p class=\"meta\">{{{{CHAPEAU}}}}</p>"
            f"<div>{{{{ARTICLES_HTML}}}}</div>"
            f"<h2>📡 Radar</h2>"
            f"<ul class=\"radar\">{{{{RADAR_HTML}}}}</ul></body></html>",
            encoding="utf-8",
        )


# ── Validation de la structure ────────────────────────────────────────────────

def validate_structure() -> None:
    shared_app_js = ROOT / "newsletters" / "app.js"
    for path in [BRIEFING / "index.html", shared_app_js, DATA_JS]:
        if not path.exists():
            raise SystemExit(f"Fichier requis absent: {path}")
    js = DATA_JS.read_text(encoding="utf-8")
    if "const TODAY" not in js or "const ARCHIVE" not in js or "const ARCHIVE_FULL" not in js:
        raise SystemExit("data.js ne contient pas les blocs attendus")
    html = TEMPLATE_HTML.read_text(encoding="utf-8") if TEMPLATE_HTML.exists() else ""
    if TEMPLATE_HTML.exists() and "{{DATE_LONGUE}}" not in html:
        raise SystemExit("Template HTML invalide (placeholder manquant)")


# ── Orchestrateur principal ───────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug",          default="briefing-ia", help="Slug de la newsletter")
    parser.add_argument("--date",          help="Date forcée YYYY-MM-DD")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    _init_paths(args.slug)
    print(f"[main] Newsletter : {args.slug}")

    date_ctx = compute_date_ctx(args.date)
    ensure_files(date_ctx)
    validate_structure()

    if args.validate_only:
        print(f"Validation OK pour {date_ctx.date}")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        print("[main] API Claude disponible — génération IA activée")
    else:
        print("[main] ANTHROPIC_API_KEY absente — génération IA désactivée")

    config     = read_json(CONFIG_JSON, {})
    nl_config  = NewsletterConfig.from_config(config)
    print(f"[main] {len(nl_config.categories)} catégories : {', '.join(nl_config.categories.keys())}")

    historique = read_json(HISTORIQUE_JSON, [])
    backlog    = read_json(BACKLOG_JSON, [])
    feedback   = read_json(FEEDBACK_JSON, {})
    sources    = read_json(SOURCES_JSON, {})

    feedback = process_feedback(date_ctx, config, feedback, BRIEFING)
    write_json(FEEDBACK_JSON, feedback)

    if not backlog:
        raise SystemExit("backlog.json est vide : impossible de générer l'édition automatiquement")

    today = build_today(date_ctx, config, backlog, historique, nl_config, NEWSLETTERS)

    write_markdown(today, date_ctx, NEWSLETTERS, nl_config.name)
    write_html(today, date_ctx, NEWSLETTERS, TEMPLATE_HTML)

    update_data_json(today, date_ctx, _PATHS)
    generate_data_js(args.slug, config, _PATHS)

    update_annexes(today, date_ctx, config, backlog, historique, sources, feedback, _PATHS)

    print(f"Génération terminée pour {date_ctx.date} ({date_ctx.date_longue})")


if __name__ == "__main__":
    main()
