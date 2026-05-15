"""
scripts/lib/storage.py
Persistance JSON et génération de data.js.

Fonctions :
    _extract_sources_default_key  — extrait une clé de SOURCES_DEFAULT dans data.js (legacy)
    _migrate_json_from_data_js    — migration one-shot : extrait ARCHIVE/ARCHIVE_FULL depuis data.js
    update_data_json              — écrit today.json, archive.json, archive_full.json
    generate_data_js              — regénère data.js depuis les JSON (zéro regex)
    update_annexes                — met à jour historique, backlog, sources après génération
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from lib.builder import (
    detect_source_candidates,
    parse_newsletter_md,
    update_source_scores,
)
from lib.platform_config import PLATFORM
from lib.utils import DateCtx, read_json, write_json


# ── Legacy extraction (SOURCES_DEFAULT disparu du nouveau format) ─────────────

def _extract_sources_default_key(key: str, data_js: Path):
    """
    Lit SOURCES_DEFAULT depuis data.js et extrait une clé spécifique.
    Utilisé pour initialiser sources.json au premier run sur l'ancien format.
    Retourne None si SOURCES_DEFAULT est absent (nouveau format).
    """
    try:
        text = data_js.read_text(encoding="utf-8")
        m = re.search(r"const SOURCES_DEFAULT\s*=\s*(\{.*?\});\s*\n", text, re.S)
        if not m:
            return None
        js_obj  = m.group(1)
        json_str = re.sub(r'(?<=[{,\[]\s*)(\w+)(?=\s*:)', r'"\1"', js_obj)
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        data = json.loads(json_str)
        return data.get(key)
    except Exception as e:
        print(f"  [sources] Impossible d'extraire {key} depuis data.js : {e}")
        return None


# ── Migration one-shot ────────────────────────────────────────────────────────

def _migrate_json_from_data_js(data_js: Path) -> tuple[list, dict]:
    """
    Extrait ARCHIVE et ARCHIVE_FULL depuis data.js existant si les JSON n'existent pas encore.
    """
    if not data_js.exists():
        return [], {}
    text = data_js.read_text(encoding="utf-8")
    archive: list = []
    archive_full: dict = {}

    m = re.search(r"const ARCHIVE\s*=\s*(\[.*?\]);", text, flags=re.S)
    if m:
        try:
            archive = json.loads(m.group(1))
        except Exception:
            pass

    m2 = re.search(r"const ARCHIVE_FULL\s*=\s*(\{.*?\});\s*\nconst CONFIG\s*=", text, flags=re.S)
    if m2:
        try:
            archive_full = json.loads(m2.group(1))
        except Exception:
            pass

    print(f"  [migration] Extrait depuis data.js : {len(archive)} entrées archive, {len(archive_full)} jours archive_full")
    return archive, archive_full


# ── Mise à jour JSON source-of-truth ─────────────────────────────────────────

def update_data_json(today: dict, date_ctx: DateCtx, paths: dict[str, Path]) -> None:
    """
    Écrit today.json, archive.json, archive_full.json — source de vérité.
    Plus aucun regex : on lit/écrit du JSON pur.
    """
    archive_json      = paths["archive_json"]
    archive_full_json = paths["archive_full_json"]
    today_json        = paths["today_json"]
    newsletters_dir   = paths["newsletters"]

    # Migration one-shot
    if not archive_json.exists() or not archive_full_json.exists():
        old_archive, old_af = _migrate_json_from_data_js(paths["data_js"])
        if not archive_json.exists():
            write_json(archive_json, old_archive)
        if not archive_full_json.exists():
            write_json(archive_full_json, old_af)

    # ARCHIVE (index léger)
    old_archive = read_json(archive_json, [])
    new_entry = {
        "date":        date_ctx.date,
        "date_longue": date_ctx.date_longue,
        "fichier":     f"newsletter-{date_ctx.date}.html",
        "is_today":    True,
        "categories":  list(dict.fromkeys([x["categorie"] for x in today["news"]])),
        "news": [
            {"titre": x["titre"], "categorie": x["categorie"], "label": x["label"]}
            for x in today["news"]
        ],
    }
    archive = [new_entry] + [x for x in old_archive if x.get("date") != date_ctx.date]
    for i in range(1, len(archive)):
        archive[i]["is_today"] = False
    write_json(archive_json, archive)

    # TODAY
    write_json(today_json, today)

    # ARCHIVE_FULL (articles complets depuis le markdown d'hier)
    old_af: dict = read_json(archive_full_json, {})
    md_hier = newsletters_dir / f"newsletter-{date_ctx.date_hier}.md"
    if md_hier.exists():
        content = md_hier.read_text(encoding="utf-8")
        parsed  = parse_newsletter_md(content, date_ctx.date_hier)
        if parsed["articles"]:
            print(f"  [ARCHIVE_FULL] {len(parsed['articles'])} articles parsés depuis {md_hier.name}")
            old_af = {
                date_ctx.date_hier: {"chapeau": parsed["chapeau"], "articles": parsed["articles"]},
                **{k: v for k, v in old_af.items() if k != date_ctx.date_hier},
            }
        else:
            print(f"  [ARCHIVE_FULL] Aucun article parsé depuis {md_hier.name} — chapeau seul conservé")
            chapeau_only = re.search(r"^>\s*(.+)$", content, flags=re.M)
            old_af = {
                date_ctx.date_hier: {
                    "chapeau": chapeau_only.group(1).strip() if chapeau_only else "",
                    "articles": [],
                },
                **{k: v for k, v in old_af.items() if k != date_ctx.date_hier},
            }
    write_json(archive_full_json, old_af)


# ── Génération data.js ────────────────────────────────────────────────────────

def generate_data_js(slug: str, config: dict, paths: dict[str, Path]) -> None:
    """
    Génère data.js depuis les fichiers JSON séparés — aucun regex, aucune mutation.
    Doit être appelé après update_data_json().
    """
    today        = read_json(paths["today_json"], {})
    archive      = read_json(paths["archive_json"], [])
    archive_full = read_json(paths["archive_full_json"], {})

    J = lambda obj: json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    nl_name = config.get("name", slug)

    content = (
        f"// ─── {nl_name} — data.js ───────────────────────────────────────────────────────\n"
        f"// Regénéré automatiquement depuis today.json, archive.json, archive_full.json.\n"
        f"// Ne pas modifier manuellement — modifier les fichiers JSON sources à la place.\n"
        f"\n"
        f"const NEWSLETTER_SLUG='{slug}';\n"
        f"\n"
        f"const TODAY = {J(today)};\n"
        f"\n"
        f"const ARCHIVE={J(archive)};\n"
        f"\n"
        f"const ARCHIVE_FULL={J(archive_full)};\n"
        f"const CONFIG= {J(config)};\n"
    )
    paths["data_js"].write_text(content, encoding="utf-8")
    print(f"  [data.js] Regénéré depuis JSON ({len(archive)} entrées archive, {len(archive_full)} jours full)")


# ── Mise à jour des annexes ───────────────────────────────────────────────────

def update_annexes(
    today: dict,
    date_ctx: DateCtx,
    config: dict,
    backlog: list[dict],
    historique: list[dict],
    sources: dict,
    feedback: dict,
    paths: dict[str, Path],
) -> None:
    """Met à jour historique, backlog, sources après chaque génération."""
    # Historique
    historique = [{
        "date":       date_ctx.date,
        "ids":        [x["id"] for x in today["news"]],
        "titres":     [x["titre"] for x in today["news"]],
        "categories": [x["categorie"] for x in today["news"]],
    }] + [x for x in historique if x.get("date") != date_ctx.date]
    write_json(paths["historique_json"], historique[:30])

    # Backlog — décroissance + suppression des articles publiés
    selected_titles = {x["titre"] for x in today["news"]}
    dec_pct   = config.get("scoring", {}).get("decroissance_quotidienne_pct",
                           PLATFORM.decroissance_quotidienne_pct_default)
    min_score = config.get("scoring", {}).get("score_minimum_backlog",
                           PLATFORM.score_minimum_default)
    dec_pct   = max(3.0, min(40.0, float(dec_pct)))
    min_score = PLATFORM.clamp_score_minimum(min_score)
    dec       = dec_pct / 100

    for row in backlog:
        if isinstance(row.get("score"), (int, float)) and row.get("titre") not in selected_titles:
            row["score"] = round(max(0, row["score"] * (1 - dec)), 1)
    backlog = [
        x for x in backlog
        if x.get("titre") not in selected_titles and x.get("score", 0) >= min_score
    ]
    write_json(paths["backlog_json"], backlog)

    # Sources — découvertes, scores, candidats
    discovered = sources.get("sources_decouvertes", [])
    seen = {x.get("url") for x in discovered if isinstance(x, dict)}
    for n in today["news"]:
        for s in n.get("sources", []):
            if s.get("url") not in seen:
                discovered.append({
                    "nom": s.get("nom", "Source"),
                    "url": s.get("url"),
                    "ajoute_le": date_ctx.date,
                })
                seen.add(s.get("url"))
    sources["sources_decouvertes"] = discovered
    sources["derniere_maj"] = date_ctx.date

    # Préserver les champs primaires/relais depuis l'ancien SOURCES_DEFAULT si nécessaire
    for key in ("meta", "sources_acteurs_ia", "sources_relais"):
        if key not in sources:
            val = _extract_sources_default_key(key, paths["data_js"])
            if val is not None:
                sources[key] = val

    sources = update_source_scores(today, sources, feedback)

    candidates = detect_source_candidates(backlog, sources, min_count=3)
    if candidates:
        print(f"  [sources] {len(candidates)} source(s) candidate(s) : {[c['domaine'] for c in candidates[:3]]}")
    sources["sources_candidates"] = candidates

    write_json(paths["sources_json"], sources)
