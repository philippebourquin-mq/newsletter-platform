#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import os
import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BRIEFING = ROOT / "briefing-ia-phil"
NEWSLETTERS = BRIEFING / "newsletters"
TEMPLATES = BRIEFING / "templates"

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

DATA_JS = BRIEFING / "data.js"
CONFIG_JSON = BRIEFING / "config.json"
HISTORIQUE_JSON = BRIEFING / "historique.json"
BACKLOG_JSON = BRIEFING / "backlog.json"
FEEDBACK_JSON = BRIEFING / "feedback.json"
SOURCES_JSON = BRIEFING / "sources.json"
TEMPLATE_HTML = TEMPLATES / "newsletter-template.html"


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
    date = d.strftime("%Y-%m-%d")
    date_hier = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    date_longue = f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}"
    return DateCtx(date=date, date_longue=date_longue, date_hier=date_hier)


def read_json(path: Path, default):
    if not path.exists():
        return deepcopy(default)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def ensure_files(date_ctx: DateCtx) -> None:
    NEWSLETTERS.mkdir(parents=True, exist_ok=True)
    TEMPLATES.mkdir(parents=True, exist_ok=True)

    if not CONFIG_JSON.exists():
        write_json(CONFIG_JSON, {
            "destinataire": {"nom": "Phil", "niveau_expertise": "expert"},
            "contenu": {
                "nb_news_principal": 6,
                "nb_news_radar": 6,
                "categories_actives": ["societal", "economie", "fonctionnel", "use_cases", "fun_facts"],
            },
            "format": {"ton": "accessible_expert"},
            "scoring": {
                "poids": {"fraicheur": 30, "reprise_multi_sources": 25, "impact_sectoriel": 20, "originalite": 15, "engagement_potentiel": 10},
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
        TEMPLATE_HTML.write_text(
            "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Briefing IA</title><style>body{font-family:Arial,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#1f2937}h1{font-size:28px}h2{font-size:21px;margin-top:28px}.meta{color:#4b5563;font-size:14px;margin-bottom:12px}.box{border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin:16px 0}.radar li{margin:10px 0}</style></head><body><h1>Briefing IA — {{DATE_LONGUE}}</h1><p class=\"meta\">{{CHAPEAU}}</p><div>{{ARTICLES_HTML}}</div><h2>📡 Radar</h2><ul class=\"radar\">{{RADAR_HTML}}</ul></body></html>",
            encoding="utf-8",
        )


def process_feedback(date_ctx: DateCtx, config: dict, feedback: dict) -> dict:
    bonus = config.get("scoring", {}).get("bonus_feedback_pts", 10)
    feedback.setdefault("articles", {})
    for file in BRIEFING.glob("retour-*.json"):
        payload = read_json(file, {})
        if payload.get("statut") != "en_attente":
            continue
        for article_id, note in payload.get("notes", {}).items():
            if isinstance(note, (int, float)) and note >= 4:
                feedback["articles"][article_id] = feedback["articles"].get(article_id, 0) + bonus
        payload["statut"] = "traité"
        write_json(file, payload)
    feedback["derniere_maj"] = date_ctx.date
    return feedback


def make_entry_from_backlog(item: dict, idx: int, date_ctx: DateCtx) -> dict:
    title = item.get("titre", f"Signal IA #{idx}")
    category = item.get("categorie", "fonctionnel")
    label_map = {
        "societal": "Sociétal",
        "economie": "Économie",
        "fonctionnel": "Fonctionnel",
        "use_cases": "Use Cases",
        "fun_facts": "Fun Facts",
    }
    label = label_map.get(category, category)
    body = (
        f"Ce signal confirme une dynamique opérationnelle importante pour les équipes qui déploient l'IA en production. "
        f"Au-delà de l'annonce, le point clé est l'impact concret sur l'organisation, la gouvernance et les priorités produit. "
        f"Les acteurs qui cadrent vite leurs usages peuvent transformer cette évolution en avantage compétitif durable. "
        f"À court terme, il faut vérifier les impacts sécurité, conformité et dépendance fournisseur avant généralisation."
    )
    return {
        "id": f"{date_ctx.date}-{idx:03d}",
        "num": idx,
        "categorie": category,
        "label": label,
        "confiance": "🔄 multi-sources",
        "titre": title,
        "body": body,
        "sources": [{"nom": "Source", "url": item.get("url", "https://example.com")}],
    }


def build_today(date_ctx: DateCtx, config: dict, backlog: list[dict], historique: list[dict]) -> dict:
    nb_main = int(config.get("contenu", {}).get("nb_news_principal", 6))
    nb_radar = int(config.get("contenu", {}).get("nb_news_radar", 6))

    recent_titles = set()
    for row in historique[:5]:
        recent_titles.update(row.get("titres", []))

    usable = [x for x in backlog if x.get("titre") and x.get("titre") not in recent_titles]
    if len(usable) < nb_main:
        usable = backlog[:max(nb_main, len(backlog))]

    selected = usable[:nb_main]
    news = [make_entry_from_backlog(item, i + 1, date_ctx) for i, item in enumerate(selected)]

    radar_items = usable[nb_main: nb_main + nb_radar]
    radar = [{
        "titre": x.get("titre", "Signal radar"),
        "desc": "Point à suivre pour les prochains arbitrages produit et métier.",
        "url": x.get("url", "https://example.com"),
    } for x in radar_items]

    chapeau = (
        "Le briefing du jour se concentre sur les signaux actionnables pour déployer l'IA avec un impact métier mesurable. "
        "L'objectif est de transformer les annonces en décisions opérationnelles, sans perdre la maîtrise des risques."
    )

    return {
        "date": date_ctx.date,
        "date_longue": date_ctx.date_longue,
        "chapeau": chapeau,
        "news": news,
        "radar": radar,
    }


def write_markdown(today: dict, date_ctx: DateCtx):
    lines = [f"# Briefing IA — {date_ctx.date_longue}", "", f"> {today['chapeau']}", ""]
    for idx, n in enumerate(today["news"], start=1):
        lines.extend([
            f"## {idx}. {n['titre']}",
            f"**Catégorie :** {n['label']} | **Confiance :** {n['confiance']}",
            n["body"],
            "Sources : " + " · ".join(s["url"] for s in n.get("sources", [])),
            "",
        ])
    lines.append("## 📡 Radar")
    for r in today.get("radar", []):
        lines.append(f"- **{r['titre']}** — {r['desc']} {r['url']}")
    (NEWSLETTERS / f"newsletter-{date_ctx.date}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_html(today: dict, date_ctx: DateCtx):
    template = TEMPLATE_HTML.read_text(encoding="utf-8")
    articles_html = []
    for idx, n in enumerate(today["news"], start=1):
        src = " · ".join([f"<a href=\"{s['url']}\">{s['nom']}</a>" for s in n.get("sources", [])])
        articles_html.append(
            f"<section class='box'><h2>{idx}. {n['titre']}</h2><p><strong>Catégorie :</strong> {n['label']} | <strong>Confiance :</strong> {n['confiance']}</p><p>{n['body']}</p><p><strong>Sources :</strong> {src}</p></section>"
        )
    radar_html = "".join([
        f"<li><strong>{r['titre']}</strong> — {r['desc']} <a href=\"{r['url']}\">Lire</a></li>" for r in today.get("radar", [])
    ])
    out = template.replace("{{DATE_LONGUE}}", date_ctx.date_longue).replace("{{CHAPEAU}}", today["chapeau"]).replace("{{ARTICLES_HTML}}", "\n".join(articles_html)).replace("{{RADAR_HTML}}", radar_html)
    (NEWSLETTERS / f"newsletter-{date_ctx.date}.html").write_text(out, encoding="utf-8")


def update_data_js(today: dict, date_ctx: DateCtx):
    text = DATA_JS.read_text(encoding="utf-8")

    old_archive = []
    m_arc = re.search(r"const ARCHIVE=(\[.*?\]);", text, flags=re.S)
    if m_arc:
        try:
            old_archive = json.loads(m_arc.group(1))
        except Exception:
            old_archive = []

    new_entry = {
        "date": date_ctx.date,
        "date_longue": date_ctx.date_longue,
        "fichier": f"newsletter-{date_ctx.date}.html",
        "is_today": True,
        "categories": list(dict.fromkeys([x["categorie"] for x in today["news"]])),
        "news": [{"titre": x["titre"], "categorie": x["categorie"], "label": x["label"]} for x in today["news"]],
    }
    archive = [new_entry] + [x for x in old_archive if x.get("date") != date_ctx.date]
    for i in range(1, len(archive)):
        archive[i]["is_today"] = False
    archive = archive[:7]

    old_af = {}
    m_af = re.search(r"const ARCHIVE_FULL=(\{.*?\});\nconst CONFIG=", text, flags=re.S)
    if m_af:
        try:
            old_af = json.loads(m_af.group(1))
        except Exception:
            old_af = {}

    md_hier = NEWSLETTERS / f"newsletter-{date_ctx.date_hier}.md"
    if md_hier.exists():
        content = md_hier.read_text(encoding="utf-8")
        chapeau = re.search(r"^>\s*(.+)$", content, flags=re.M)
        old_af = {
            date_ctx.date_hier: {
                "chapeau": chapeau.group(1).strip() if chapeau else "",
                "articles": []
            },
            **{k: v for k, v in old_af.items() if k != date_ctx.date_hier}
        }
    old_af = dict(list(old_af.items())[:7])

    text = re.sub(r"const TODAY\s*=\s*\{.*?\};", f"const TODAY = {json.dumps(today, ensure_ascii=False, separators=(',', ':'))};", text, flags=re.S)
    text = re.sub(r"const ARCHIVE=\[.*?\];", f"const ARCHIVE={json.dumps(archive, ensure_ascii=False, separators=(',', ':'))};", text, flags=re.S)
    text = re.sub(r"const ARCHIVE_FULL=\{.*?\};\nconst CONFIG=", f"const ARCHIVE_FULL={json.dumps(old_af, ensure_ascii=False, separators=(',', ':'))};\nconst CONFIG=", text, flags=re.S)
    DATA_JS.write_text(text, encoding="utf-8")


def update_annexes(today: dict, date_ctx: DateCtx, config: dict, backlog: list[dict], historique: list[dict], sources: dict):
    historique = [{
        "date": date_ctx.date,
        "ids": [x["id"] for x in today["news"]],
        "titres": [x["titre"] for x in today["news"]],
        "categories": [x["categorie"] for x in today["news"]],
    }] + [x for x in historique if x.get("date") != date_ctx.date]
    write_json(HISTORIQUE_JSON, historique[:30])

    selected_titles = {x["titre"] for x in today["news"]}
    dec = config.get("scoring", {}).get("decroissance_quotidienne_pct", 15) / 100
    min_score = config.get("scoring", {}).get("score_minimum_backlog", 10)
    for row in backlog:
        if isinstance(row.get("score"), (int, float)) and row.get("titre") not in selected_titles:
            row["score"] = round(max(0, row["score"] * (1 - dec)), 1)
    backlog = [x for x in backlog if x.get("titre") not in selected_titles and x.get("score", 0) >= min_score]
    write_json(BACKLOG_JSON, backlog)

    discovered = sources.get("sources_decouvertes", [])
    seen = {x.get("url") for x in discovered if isinstance(x, dict)}
    for n in today["news"]:
        for s in n.get("sources", []):
            if s.get("url") not in seen:
                discovered.append({"nom": s.get("nom", "Source"), "url": s.get("url"), "ajoute_le": date_ctx.date})
                seen.add(s.get("url"))
    sources["sources_decouvertes"] = discovered
    sources["derniere_maj"] = date_ctx.date
    write_json(SOURCES_JSON, sources)

    retour = {
        "date": date_ctx.date,
        "statut": "en_attente",
        "notes": {x["id"]: None for x in today["news"]},
        "commentaire": "",
    }
    write_json(BRIEFING / f"retour-{date_ctx.date}.json", retour)


def validate_structure() -> None:
    for path in [BRIEFING / "index.html", BRIEFING / "app.js", DATA_JS]:
        if not path.exists():
            raise SystemExit(f"Fichier requis absent: {path}")
    js = DATA_JS.read_text(encoding="utf-8")
    if "const TODAY" not in js or "const ARCHIVE" not in js or "const ARCHIVE_FULL" not in js:
        raise SystemExit("data.js ne contient pas les blocs attendus")
    html = TEMPLATE_HTML.read_text(encoding="utf-8") if TEMPLATE_HTML.exists() else ""
    if TEMPLATE_HTML.exists() and "{{DATE_LONGUE}}" not in html:
        raise SystemExit("Template HTML invalide (placeholder manquant)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Date forcée YYYY-MM-DD")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    date_ctx = compute_date_ctx(args.date)
    ensure_files(date_ctx)
    validate_structure()
    if args.validate_only:
        print(f"Validation OK pour {date_ctx.date}")
        return

    config = read_json(CONFIG_JSON, {})
    historique = read_json(HISTORIQUE_JSON, [])
    backlog = read_json(BACKLOG_JSON, [])
    feedback = read_json(FEEDBACK_JSON, {})
    sources = read_json(SOURCES_JSON, {})

    feedback = process_feedback(date_ctx, config, feedback)
    write_json(FEEDBACK_JSON, feedback)

    if not backlog:
        raise SystemExit("backlog.json est vide : impossible de générer l'édition automatiquement")

    today = build_today(date_ctx, config, backlog, historique)
    write_markdown(today, date_ctx)
    write_html(today, date_ctx)
    update_data_js(today, date_ctx)
    update_annexes(today, date_ctx, config, backlog, historique, sources)

    print(f"Génération terminée pour {date_ctx.date} ({date_ctx.date_longue})")


if __name__ == "__main__":
    main()
