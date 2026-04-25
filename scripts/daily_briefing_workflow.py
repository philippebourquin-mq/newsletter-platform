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
BRIEFING = ROOT / "newsletters" / "briefing-ia"
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

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Phrases indicatrices d'un corps générique/placeholder à remplacer
PLACEHOLDER_MARKERS = [
    "Ce signal confirme une dynamique opérationnelle importante",
    "Point à suivre pour les prochains arbitrages produit",
]

LABEL_MAP = {
    "societal": "Sociétal",
    "economie": "Économie",
    "fonctionnel": "Fonctionnel",
    "use_cases": "Use Cases",
    "fun_facts": "Fun Facts",
}

# Reverse map label → categorie (pour parser le markdown)
LABEL_TO_CAT = {v.lower(): k for k, v in LABEL_MAP.items()}
# Labels custom souvent présents dans le backlog
LABEL_TO_CAT.update({
    "architecture & technique": "fonctionnel",
    "produits & plateformes": "use_cases",
    "performance & évaluation": "fonctionnel",
    "créativité & ia": "fun_facts",
    "gouvernance & réglementation": "societal",
    "sécurité & risques": "societal",
    "marché & investissements": "economie",
    "emploi & organisation": "economie",
    "recherche & science": "fonctionnel",
    "infrastructure & cloud": "fonctionnel",
})


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


# ─── CLAUDE API ───────────────────────────────────────────────────────────────

def call_claude(prompt: str, max_tokens: int = 500, system: str = "") -> str:
    """Appelle l'API Claude pour générer du contenu. Retourne "" si indisponible."""
    if not ANTHROPIC_API_KEY:
        print("[Claude API] ANTHROPIC_API_KEY non définie — génération IA désactivée.")
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        kwargs: dict = {
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        message = client.messages.create(**kwargs)
        return message.content[0].text.strip()
    except Exception as e:
        print(f"[Claude API] Erreur : {e}")
        return ""


def is_placeholder_body(body: str) -> bool:
    """Retourne True si le body est un texte générique/placeholder."""
    if not body:
        return True
    body_lower = body.lower()
    return any(m.lower() in body_lower for m in PLACEHOLDER_MARKERS)


def generate_article_body(item: dict) -> str:
    """Génère un corps d'article contextuel via Claude API."""
    title = item.get("titre", "")
    label = item.get("label") or LABEL_MAP.get(item.get("categorie", ""), "IA")
    url = item.get("url", "")
    sources_text = " / ".join(
        s.get("nom", "") for s in item.get("sources", []) if s.get("nom")
    )

    prompt = f"""Tu rédiges un article pour une newsletter IA professionnelle destinée à des experts (directeurs, product managers, ingénieurs seniors).

Titre : {title}
Catégorie : {label}
Source principale : {url}
Autres sources : {sources_text or "N/A"}

Rédige un corps d'article de 4 à 6 phrases. Règles :
- Ton direct, factuel, analytique — jamais promotionnel ni générique
- Commence par un fait concret ou chiffre clé si possible
- Inclure l'impact business / technique / réglementaire selon la catégorie
- Terminer par une implication concrète pour les équipes ou décideurs

Exemples de style cible :
→ "Alphabet est en pourparlers avancés avec le Département de la Défense américain pour déployer ses modèles Gemini dans des environnements à accès restreint. L'accord potentiel permettrait au Pentagone d'utiliser l'IA pour des opérations légales, y compris classifiées — une première pour Google, qui avait quitté le programme Maven en 2018. Ce mouvement s'inscrit dans le sillage du contrat OpenAI/Pentagone de février 2026. La course à l'IA de défense est désormais ouverte entre les grands laboratoires."
→ "Un guide pratique clarifie les critères de choix entre RAG et fine-tuning : le RAG convient aux données qui changent fréquemment, le fine-tuning s'impose pour les domaines très spécialisés. Les deux approches sont souvent complémentaires en production."

Réponds UNIQUEMENT avec le corps de l'article, sans titre ni balise."""

    result = call_claude(prompt, max_tokens=400)
    if result:
        print(f"  [Claude] Corps généré pour : {title[:60]}")
    return result


def generate_chapeau(date_ctx: DateCtx, news: list[dict]) -> str:
    """Génère le chapeau introductif de l'édition via Claude API."""
    titles_text = "\n".join(f"- {n['titre']}" for n in news)

    prompt = f"""Tu rédiges le chapeau d'ouverture d'une newsletter IA professionnelle pour des experts.

Date : {date_ctx.date_longue}
Articles du jour :
{titles_text}

Rédige UN seul paragraphe de 2 à 3 phrases qui synthétise les thèmes dominants de cette édition.
Règles :
- Percutant, informatif, donne envie de lire
- Pas de formule de salutation ("Bonjour", "Bienvenue", etc.)
- Peut utiliser des contrastes ou parallèles entre les sujets
- Mentionner 1-2 acteurs ou faits marquants du jour si pertinent

Exemple de style cible :
"Ce vendredi marque une double accélération : les modèles les plus puissants franchissent les portes des systèmes régaliens — le Pentagone discute d'un accord Gemini classifié — tandis que la gouvernance reprend la main en Europe, avec Elon Musk convoqué à Paris dans l'enquête Grok. Pendant ce temps, Claude Opus 4.7 est officiellement disponible et Londres devient le champ de bataille du recrutement mondial de l'IA."

Réponds UNIQUEMENT avec le texte du chapeau, sans balise ni introduction."""

    result = call_claude(prompt, max_tokens=200)
    if result:
        print(f"  [Claude] Chapeau généré pour {date_ctx.date}")
        return result

    # Fallback générique amélioré
    first_word = news[0]["titre"].split(" ")[0] if news else "l’IA"
    return (
        f"Au programme de ce {date_ctx.date_longue.split()[0].lower()} : "
        f"{first_word} et {len(news)} signaux clés "
        f"pour anticiper les prochains arbitrages produit, technique et stratégique."
    )


def generate_radar_desc(item: dict) -> str:
    """Génère une courte description radar via Claude API."""
    title = item.get("titre", "")
    url = item.get("url", "")

    prompt = f"""En une seule phrase courte (15-20 mots max), résume pourquoi cet article est à suivre pour un expert IA.

Titre : {title}
URL : {url}

Réponds UNIQUEMENT avec la phrase, sans ponctuation finale ni balise."""

    result = call_claude(prompt, max_tokens=60)
    return result or "Point à suivre pour les prochains arbitrages produit et métier."


# ─── FEEDBACK ─────────────────────────────────────────────────────────────────

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


# ─── ARTICLE BUILDER ──────────────────────────────────────────────────────────

def make_entry_from_backlog(item: dict, idx: int, date_ctx: DateCtx) -> dict:
    title = item.get("titre", f"Signal IA #{idx}")
    category = item.get("categorie", "fonctionnel")
    label = item.get("label") or LABEL_MAP.get(category, category)

    # Utiliser le body du backlog s'il est substantiel, sinon générer via Claude
    body = item.get("body", "")
    if is_placeholder_body(body):
        generated = generate_article_body(item)
        body = generated if generated else (
            f"Signal important dans le domaine {label.lower()}. "
            "Consultez les sources pour les détails complets de cette annonce."
        )

    # Utiliser les sources du backlog ou créer une entrée minimale
    sources = item.get("sources")
    if not sources:
        url = item.get("url", "https://example.com")
        sources = [{"nom": "Source", "url": url}]

    # Déterminer le niveau de confiance selon le nombre de sources
    confiance = "✅ source primaire" if len(sources) == 1 else "🔄 multi-sources"

    return {
        "id": f"{date_ctx.date}-{idx:03d}",
        "num": idx,
        "categorie": category,
        "label": label,
        "confiance": confiance,
        "titre": title,
        "body": body,
        "sources": sources,
    }


# ─── BUILD TODAY ──────────────────────────────────────────────────────────────

def build_today(date_ctx: DateCtx, config: dict, backlog: list[dict], historique: list[dict]) -> dict:
    nb_main = int(config.get("contenu", {}).get("nb_news_principal", 6))
    nb_radar = int(config.get("contenu", {}).get("nb_news_radar", 6))

    recent_titles = set()
    for row in historique[:5]:
        recent_titles.update(row.get("titres", []))

    usable = [x for x in backlog if x.get("titre") and x.get("titre") not in recent_titles]
    if len(usable) < nb_main:
        usable = list(backlog)

    # Trier par score décroissant (les items avec le meilleur score en premier)
    usable_sorted = sorted(usable, key=lambda x: x.get("score", 0), reverse=True)

    selected = usable_sorted[:nb_main]
    print(f"[build_today] {len(selected)} articles sélectionnés (score max: {selected[0].get('score', 0) if selected else 0})")

    news = [make_entry_from_backlog(item, i + 1, date_ctx) for i, item in enumerate(selected)]

    # Radar : items suivants par score
    radar_items = usable_sorted[nb_main: nb_main + nb_radar]
    radar = []
    for x in radar_items:
        desc = x.get("body", "")
        # Raccourcir le body pour le radar, ou générer une description courte
        if desc and not is_placeholder_body(desc):
            # Première phrase du body existant
            first_sentence = re.split(r'(?<=[.!?])\s', desc)[0]
            if len(first_sentence) > 120:
                first_sentence = first_sentence[:117] + "…"
            desc = first_sentence
        else:
            desc = generate_radar_desc(x) if ANTHROPIC_API_KEY else "Point à suivre pour les prochains arbitrages produit et métier."
        radar.append({
            "titre": x.get("titre", "Signal radar"),
            "desc": desc,
            "url": x.get("url", "https://example.com"),
        })

    # Générer le chapeau contextuel
    chapeau = generate_chapeau(date_ctx, news)

    return {
        "date": date_ctx.date,
        "date_longue": date_ctx.date_longue,
        "chapeau": chapeau,
        "news": news,
        "radar": radar,
    }


# ─── MARKDOWN PARSER ──────────────────────────────────────────────────────────

def parse_newsletter_md(content: str, date: str) -> dict:
    """
    Parse un fichier markdown newsletter et retourne {chapeau, articles}.
    Compatible avec le format produit par write_markdown().
    """
    # Chapeau
    chapeau_match = re.search(r"^>\s*(.+)$", content, flags=re.M)
    chapeau = chapeau_match.group(1).strip() if chapeau_match else ""

    articles = []

    # Pattern : ## N. Titre\n**Catégorie :** Label | **Confiance :** conf\nbody\nSources : ...
    # La ligne body peut être multiligne jusqu'à "Sources :"
    pattern = re.compile(
        r"^## (\d+)\.\s+(.+?)\s*\n"                        # ## N. Titre
        r"\*\*Cat[eé]gorie\s*:\*\*\s*(.+?)"                # **Catégorie :** Label
        r"\s*\|\s*\*\*Confiance\s*:\*\*\s*(.+?)"           # | **Confiance :** conf
        r"(?:\s*\|\s*\*\*cat:\*\*\s*(\w+))?\n"             # | **cat:** categorie (optionnel)
        r"(.*?)\n"                                          # body (une ligne ou plusieurs)
        r"Sources\s*[:\-]\s*(.+?)(?=\n##|\Z)",             # Sources : ...
        re.S | re.M
    )

    for m in pattern.finditer(content):
        num_str, titre, label, confiance, cat_inline, body_raw, sources_str = m.groups()

        # Nettoyer le body (peut avoir des sauts de ligne)
        body = body_raw.strip()

        # Parser les sources — formats supportés :
        #   [Nom](url) · [Nom](url)     (markdown links, newsletters Dropbox)
        #   url1 · url2                 (URLs brutes, ancien write_markdown)
        sources = []
        for part in sources_str.strip().split(" · "):
            part = part.strip()
            if not part:
                continue
            md_link = re.match(r'\[(.+?)\]\((.+?)\)', part)
            if md_link:
                sources.append({"nom": md_link.group(1), "url": md_link.group(2)})
            elif part.startswith("http"):
                sources.append({"nom": "Source", "url": part})

        # Catégorie : depuis le champ inline **cat:** si présent, sinon reverse-map du label
        label_clean = label.strip()
        if cat_inline:
            cat = cat_inline.strip()
        else:
            cat = LABEL_TO_CAT.get(label_clean.lower(), "fonctionnel")

        num = int(num_str)
        articles.append({
            "id": f"{date}-{num:03d}",
            "num": num,
            "categorie": cat,
            "label": label_clean,
            "confiance": confiance.strip(),
            "titre": titre.strip(),
            "body": body,
            "sources": sources or [{"nom": "Source", "url": "#"}],
        })

    return {"chapeau": chapeau, "articles": articles}


# ─── WRITE OUTPUTS ────────────────────────────────────────────────────────────

def write_markdown(today: dict, date_ctx: DateCtx):
    lines = [f"# Briefing IA — {date_ctx.date_longue}", "", f"> {today['chapeau']}", ""]
    for idx, n in enumerate(today["news"], start=1):
        lines.extend([
            f"## {idx}. {n['titre']}",
            f"**Catégorie :** {n['label']} | **Confiance :** {n['confiance']} | **cat:** {n['categorie']}",
            n["body"],
            "Sources : " + " · ".join(
                f"[{s['nom']}]({s['url']})" for s in n.get("sources", [])
            ),
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


# ─── UPDATE data.js ───────────────────────────────────────────────────────────

def update_data_js(today: dict, date_ctx: DateCtx):
    text = DATA_JS.read_text(encoding="utf-8")

    # ── ARCHIVE (index léger) ──
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

    # ── ARCHIVE_FULL (articles complets) ──
    old_af: dict = {}
    m_af = re.search(r"const ARCHIVE_FULL=(\{.*?\});\nconst CONFIG=", text, flags=re.S)
    if m_af:
        try:
            old_af = json.loads(m_af.group(1))
        except Exception:
            old_af = {}

    # Parser le markdown d'hier pour obtenir les articles complets
    md_hier = NEWSLETTERS / f"newsletter-{date_ctx.date_hier}.md"
    if md_hier.exists():
        content = md_hier.read_text(encoding="utf-8")
        parsed = parse_newsletter_md(content, date_ctx.date_hier)

        if parsed["articles"]:
            print(f"  [ARCHIVE_FULL] {len(parsed['articles'])} articles parsés depuis {md_hier.name}")
            old_af = {
                date_ctx.date_hier: {
                    "chapeau": parsed["chapeau"],
                    "articles": parsed["articles"],
                },
                **{k: v for k, v in old_af.items() if k != date_ctx.date_hier},
            }
        else:
            # Fallback : stocker au moins le chapeau si le parse échoue
            print(f"  [ARCHIVE_FULL] Aucun article parsé depuis {md_hier.name} — chapeau seul conservé")
            chapeau_only = re.search(r"^>\s*(.+)$", content, flags=re.M)
            old_af = {
                date_ctx.date_hier: {
                    "chapeau": chapeau_only.group(1).strip() if chapeau_only else "",
                    "articles": [],
                },
                **{k: v for k, v in old_af.items() if k != date_ctx.date_hier},
            }

    # Garder seulement les 7 dernières entrées
    old_af = dict(list(old_af.items())[:7])

    # ── Écriture dans data.js ──
    text = re.sub(
        r"const TODAY\s*=\s*\{.*?\};",
        f"const TODAY = {json.dumps(today, ensure_ascii=False, separators=(',', ':'))};",
        text, flags=re.S
    )
    text = re.sub(
        r"const ARCHIVE=\[.*?\];",
        f"const ARCHIVE={json.dumps(archive, ensure_ascii=False, separators=(',', ':'))};",
        text, flags=re.S
    )
    text = re.sub(
        r"const ARCHIVE_FULL=\{.*?\};\nconst CONFIG=",
        f"const ARCHIVE_FULL={json.dumps(old_af, ensure_ascii=False, separators=(',', ':'))};\nconst CONFIG=",
        text, flags=re.S
    )
    DATA_JS.write_text(text, encoding="utf-8")


# ─── UPDATE ANNEXES ───────────────────────────────────────────────────────────

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


# ─── VALIDATE ─────────────────────────────────────────────────────────────────

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


# ─── MAIN ─────────────────────────────────────────────────────────────────────

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

    if ANTHROPIC_API_KEY:
        print(f"[main] API Claude disponible — génération IA activée")
    else:
        print(f"[main] ANTHROPIC_API_KEY absente — génération IA désactivée (bodies du backlog utilisés)")

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
