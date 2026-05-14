"""
scripts/lib/paths.py
Résolution centralisée des chemins de fichiers par slug de newsletter.

Usage :
    from scripts.lib.paths import get_paths, ROOT

    p = get_paths("briefing-ia")
    config = json.loads(p["config_json"].read_text())
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # racine du projet


def get_paths(slug: str) -> dict[str, Path]:
    """
    Retourne un dict de tous les chemins standard pour un slug de newsletter.

    Clés disponibles :
        briefing       Répertoire de la newsletter  (newsletters/<slug>/)
        newsletters    Sous-répertoire des fichiers  (newsletters/<slug>/newsletters/)
        templates      Sous-répertoire templates     (newsletters/<slug>/templates/)
        data_js        Fichier de données JS         (newsletters/<slug>/data.js)
        config_json    Configuration                 (newsletters/<slug>/config.json)
        historique_json Historique des éditions      (newsletters/<slug>/historique.json)
        backlog_json   Backlog articles              (newsletters/<slug>/backlog.json)
        feedback_json  Feedbacks                     (newsletters/<slug>/feedback.json)
        sources_json   Sources actives               (newsletters/<slug>/sources.json)
        sources_rss_json Flux RSS configurés         (newsletters/<slug>/sources_rss.json)
        template_html  Template HTML newsletter      (newsletters/<slug>/templates/newsletter-template.html)
    """
    briefing = ROOT / "newsletters" / slug
    return {
        "briefing":          briefing,
        "newsletters":       briefing / "newsletters",
        "templates":         briefing / "templates",
        "data_js":           briefing / "data.js",
        "config_json":       briefing / "config.json",
        "historique_json":   briefing / "historique.json",
        "backlog_json":      briefing / "backlog.json",
        "feedback_json":     briefing / "feedback.json",
        "sources_json":      briefing / "sources.json",
        "sources_rss_json":  briefing / "sources_rss.json",
        "template_html":     briefing / "templates" / "newsletter-template.html",
        # Fichiers JSON source de vérité (remplacent les regex dans data.js)
        "today_json":        briefing / "today.json",
        "archive_json":      briefing / "archive.json",
        "archive_full_json": briefing / "archive_full.json",
    }
