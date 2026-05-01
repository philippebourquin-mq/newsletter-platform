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

# Chemins initialisés dynamiquement par _init_paths(slug) dans main()
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

def _init_paths(slug: str) -> None:
    """Initialise toutes les constantes de chemin pour un slug de newsletter donné."""
    global BRIEFING, NEWSLETTERS, TEMPLATES, DATA_JS, CONFIG_JSON
    global HISTORIQUE_JSON, BACKLOG_JSON, FEEDBACK_JSON, SOURCES_JSON, TEMPLATE_HTML
    BRIEFING       = ROOT / "newsletters" / slug
    NEWSLETTERS    = BRIEFING / "newsletters"
    TEMPLATES      = BRIEFING / "templates"
    DATA_JS        = BRIEFING / "data.js"
    CONFIG_JSON    = BRIEFING / "config.json"
    HISTORIQUE_JSON= BRIEFING / "historique.json"
    BACKLOG_JSON   = BRIEFING / "backlog.json"
    FEEDBACK_JSON  = BRIEFING / "feedback.json"
    SOURCES_JSON   = BRIEFING / "sources.json"
    TEMPLATE_HTML  = TEMPLATES / "newsletter-template.html"

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Phrases indicatrices d'un corps générique/placeholder à remplacer
PLACEHOLDER_MARKERS = [
    "Ce signal confirme une dynamique opérationnelle importante",
    "Point à suivre pour les prochains arbitrages produit",
]

# ── Catégories dynamiques — initialisées dans main() depuis config.json ──────
_CATEGORIES: dict[str, str] = {}   # slug → description
_PERSONA: str = ""                  # contexte lecteur cible

_FALLBACK_CATEGORIES: dict[str, str] = {
    "fonctionnel": "Vie des modèles et des outils IA",
    "use_cases":   "Déploiements concrets en entreprise",
    "fun_facts":   "L'inattendu : records, découvertes surprenantes",
    "societal":    "Réglementation, éthique, gouvernance",
    "economie":    "Marché, financements, business models",
}
_FALLBACK_PERSONA = (
    "Tu analyses l'actualité pour des experts tech (directeurs, ingénieurs seniors, product managers)."
)


def derive_label(cat_slug: str) -> str:
    """'fun_facts' → 'Fun Facts', 'societal' → 'Societal', etc."""
    return cat_slug.replace("_", " ").title()


def build_label_to_cat(categories: dict[str, str]) -> dict[str, str]:
    """Construit le reverse map label.lower() → slug depuis les catégories config."""
    return {derive_label(slug).lower(): slug for slug in categories}


def get_label(cat_slug: str) -> str:
    """Retourne le label affiché pour un slug, depuis _CATEGORIES si dispo."""
    return derive_label(cat_slug)


def get_default_cat() -> str:
    cats = _CATEGORIES or _FALLBACK_CATEGORIES
    return next(iter(cats), "general")


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
            "contenu": {"nb_news_principal": 5, "nb_news_radar": 5},
            "persona": _FALLBACK_PERSONA,
            "categories": _FALLBACK_CATEGORIES,
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
    label = item.get("label") or get_label(item.get("categorie", get_default_cat()))
    url = item.get("url", "")
    sources_text = " / ".join(
        s.get("nom", "") for s in item.get("sources", []) if s.get("nom")
    )

    pers = _PERSONA or _FALLBACK_PERSONA
    cats = _CATEGORIES or _FALLBACK_CATEGORIES
    cat_desc = cats.get(item.get("categorie", ""), "")
    cat_context = f"Catégorie : {label}" + (f" — {cat_desc}" if cat_desc else "")

    prompt = f"""{pers}

Titre : {title}
{cat_context}
Source principale : {url}
Autres sources : {sources_text or "N/A"}

Rédige un corps d'article de 4 à 6 phrases. Règles :
- Ton direct, factuel, analytique — jamais promotionnel ni générique
- Commence par un fait concret ou chiffre clé si possible
- Inclure l'impact métier selon la catégorie
- Terminer par une implication concrète pour le lecteur cible

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

    # Lire les retours manuels (retour-*.json) — format historique
    for file in BRIEFING.glob("retour-*.json"):
        payload = read_json(file, {})
        if payload.get("statut") != "en_attente":
            continue
        for article_id, note in payload.get("notes", {}).items():
            if isinstance(note, (int, float)) and note >= 4:
                feedback["articles"][article_id] = feedback["articles"].get(article_id, 0) + bonus
        payload["statut"] = "traité"
        write_json(file, payload)

    # Lire les feedbacks UI exportés depuis le navigateur (feedback_ui.json)
    fb_ui_file = BRIEFING / "feedback_ui.json"
    if fb_ui_file.exists():
        fb_ui = read_json(fb_ui_file, {})
        if fb_ui.get("statut") != "traité":
            applied = 0
            for article_id, note in fb_ui.get("notes", {}).items():
                if isinstance(note, (int, float)) and note >= 4:
                    feedback["articles"][article_id] = feedback["articles"].get(article_id, 0) + bonus
                    applied += 1
            fb_ui["statut"] = "traité"
            fb_ui["traite_le"] = date_ctx.date
            write_json(fb_ui_file, fb_ui)
            print(f"  ✓ feedback_ui.json : {applied} bonus appliqués")

    feedback["derniere_maj"] = date_ctx.date
    return feedback


# ─── ARTICLE BUILDER ──────────────────────────────────────────────────────────

def make_entry_from_backlog(item: dict, idx: int, date_ctx: DateCtx, rebond_info: dict | None = None) -> dict:
    title = item.get("titre", f"Signal IA #{idx}")
    category = item.get("categorie", "fonctionnel")
    label = item.get("label") or get_label(category)

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

    entry = {
        "id": f"{date_ctx.date}-{idx:03d}",
        "num": idx,
        "categorie": category,
        "label": label,
        "confiance": confiance,
        "titre": title,
        "body": body,
        "sources": sources,
    }
    if rebond_info:
        entry["rebond_de"] = rebond_info   # {"titre": "...", "date": "YYYY-MM-DD"}
    return entry


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

    # Trier par score décroissant
    usable_sorted = sorted(usable, key=lambda x: x.get("score", 0), reverse=True)

    # ── Analyse sémantique des candidats vs historique (1 appel Claude batch) ──
    inspect_pool = usable_sorted[:nb_main * 3]
    classifications: dict = {}

    if ANTHROPIC_API_KEY:
        recent_summaries = load_recent_newsletter_summaries(date_ctx, days=7)
        if recent_summaries:
            print(f"[build_today] Analyse sémantique de {len(inspect_pool)} candidats vs {len(recent_summaries)} articles récents…")
            classifications = semantic_rebond_classify(inspect_pool, recent_summaries)
        else:
            print("[build_today] Pas d'historique markdown disponible — fallback keyword")
    else:
        print("[build_today] API indisponible — détection rebond par mots-clés uniquement")

    selected = []
    rebond_map: dict[str, dict] = {}
    cat_counts: dict[str, int] = {}
    # Plafond par catégorie : max 2 articles sur nb_main=6, ajusté si nb_main diffère
    max_per_cat = max(2, nb_main // 3)

    for i, item in enumerate(inspect_pool):
        if len(selected) >= nb_main:
            break

        cls = classifications.get(i)
        if cls:
            # ── Analyse sémantique disponible ──
            statut = cls.get("statut", "nouveau")
            if statut == "doublon":
                print(f"  [doublon] Écarté : {item.get('titre', '')[:70]}")
                continue
            if statut == "rebond" and cls.get("ref"):
                rebond_map[item["titre"]] = cls["ref"]
                print(f"  [rebond] {item.get('titre', '')[:50]} ← {cls['ref'].get('titre', '')[:40]} ({cls['ref'].get('date', '')})")
        else:
            # ── Fallback keyword si l'article n'a pas été classifié ──
            is_dup, rebond_kw = detect_rebond(item, historique)
            if is_dup:
                print(f"  [doublon-kw] Écarté : {item.get('titre', '')[:70]}")
                continue
            if rebond_kw:
                rebond_map[item["titre"]] = rebond_kw

        # ── Plafond par catégorie (panachage) ──
        cat = item.get("categorie", "")
        if cat_counts.get(cat, 0) >= max_per_cat:
            print(f"  [panachage] Écarté (quota {max_per_cat}/{cat}) : {item.get('titre', '')[:60]}")
            continue

        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        selected.append(item)

    print(f"[build_today] {len(selected)} articles sélectionnés (score max: {selected[0].get('score', 0) if selected else 0})")

    news = [make_entry_from_backlog(item, i + 1, date_ctx, rebond_map.get(item["titre"])) for i, item in enumerate(selected)]

    # Radar : items suivants par score, en excluant les doublons déjà détectés
    selected_titles = {x["titre"] for x in selected}
    radar_pool = [x for x in usable_sorted if x["titre"] not in selected_titles]
    radar_items_raw = radar_pool[:nb_radar * 2]   # Prendre un peu plus pour compenser les doublons éventuels

    radar_items = []
    for i, x in enumerate(radar_items_raw):
        # Vérifier dans les classifications si cet item est un doublon
        pool_idx = usable_sorted.index(x) if x in usable_sorted else -1
        cls = classifications.get(pool_idx, {})
        if cls.get("statut") == "doublon":
            continue
        radar_items.append(x)
        if len(radar_items) >= nb_radar:
            break

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
            label_to_cat = build_label_to_cat(_CATEGORIES or _FALLBACK_CATEGORIES)
            cat = label_to_cat.get(label_clean.lower(), get_default_cat())

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
        rebond_line = ""
        if n.get("rebond_de"):
            rb = n["rebond_de"]
            rebond_line = f"↩ Suite de : *{rb['titre']}* ({rb['date']})"
        lines.extend([
            f"## {idx}. {n['titre']}",
            f"**Catégorie :** {n['label']} | **Confiance :** {n['confiance']} | **cat:** {n['categorie']}",
            *([rebond_line] if rebond_line else []),
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

def update_data_js(today: dict, date_ctx: DateCtx, args_slug: str = "briefing-ia"):
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
    # Utiliser des lambdas comme remplacement pour que re.sub n'interprète pas
    # les \n et \\ du JSON comme des séquences d'échappement regex.

    # Injecter / mettre à jour NEWSLETTER_SLUG (clé multi-newsletter)
    slug_line = f"const NEWSLETTER_SLUG='{args_slug}';"
    if "const NEWSLETTER_SLUG=" in text:
        text = re.sub(r"const NEWSLETTER_SLUG='[^']*';", slug_line, text)
    else:
        text = text.replace("// ─── DATA ─────────────────────────────────────────────────────────────────────",
                            f"{slug_line}\n\n// ─── DATA ─────────────────────────────────────────────────────────────────────")

    _today_repl = f"const TODAY = {json.dumps(today, ensure_ascii=False, separators=(',', ':'))};"
    text = re.sub(
        r"const TODAY\s*=\s*\{.*?\};",
        lambda m: _today_repl,
        text, flags=re.S
    )
    _archive_repl = f"const ARCHIVE={json.dumps(archive, ensure_ascii=False, separators=(',', ':'))};"
    text = re.sub(
        r"const ARCHIVE=\[.*?\];",
        lambda m: _archive_repl,
        text, flags=re.S
    )
    _af_repl = f"const ARCHIVE_FULL={json.dumps(old_af, ensure_ascii=False, separators=(',', ':'))};\nconst CONFIG="
    text = re.sub(
        r"const ARCHIVE_FULL=\{.*?\};\nconst CONFIG=",
        lambda m: _af_repl,
        text, flags=re.S
    )
    DATA_JS.write_text(text, encoding="utf-8")


# ─── REBOND DETECTION ────────────────────────────────────────────────────────

def load_recent_newsletter_summaries(date_ctx: DateCtx, days: int = 7) -> list[dict]:
    """
    Charge titres + extraits de corps des newsletters récentes depuis les fichiers .md.
    Retourne une liste de {date, titre, body_short} pour alimenter le prompt Claude.
    """
    summaries = []
    md_files = sorted(NEWSLETTERS.glob("newsletter-*.md"), reverse=True)
    for md_file in md_files[:days + 1]:
        date_str = md_file.stem.replace("newsletter-", "")
        if date_str == date_ctx.date:
            continue  # Pas encore publiée aujourd'hui
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        # Parser titre + début du body de chaque article
        pattern = re.compile(
            r"^## \d+\.\s+(.+?)\s*\n"
            r"(?:\*\*Cat[eé]gorie.*?\n)?"
            r"(?:↩.*?\n)?"
            r"(.+?)(?=\nSources|\Z)",
            re.S | re.M,
        )
        for m in pattern.finditer(content):
            titre = m.group(1).strip()
            body_raw = m.group(2).strip()
            # Première phrase seulement
            body_short = re.split(r'(?<=[.!?])\s', body_raw)[0][:160]
            summaries.append({"date": date_str, "titre": titre, "body": body_short})
        if len(summaries) >= 50:  # Limiter pour le prompt
            break
    return summaries


def semantic_rebond_classify(candidates: list[dict], recent_articles: list[dict]) -> dict:
    """
    Appelle Claude UNE FOIS pour classifier sémantiquement les candidats backlog
    par rapport aux articles récents publiés.

    Retourne {idx (0-based): {"statut": "nouveau"|"doublon"|"rebond", "ref": dict|None}}
    """
    if not ANTHROPIC_API_KEY or not candidates or not recent_articles:
        return {}

    # Contexte historique compact
    hist_lines = []
    for art in recent_articles[:40]:
        hist_lines.append(f"  [{art['date']}] {art['titre']} — {art.get('body', '')[:120]}")

    # Candidats à analyser
    cand_lines = []
    for i, item in enumerate(candidates):
        titre = item.get("titre", "")
        body = item.get("body", "")[:160]
        src = ", ".join(s.get("nom", "") for s in item.get("sources", []))[:60]
        cand_lines.append(f"{i + 1}. {titre}\n   [{src}] {body}")

    prompt = f"""Tu analyses des articles pour une newsletter IA.

ARTICLES DÉJÀ PUBLIÉS (derniers jours) :
{chr(10).join(hist_lines)}

NOUVEAUX CANDIDATS À CLASSIFIER ({len(candidates)}) :
{chr(10).join(cand_lines)}

Classe chaque candidat :
- "nouveau"  : sujet non couvert récemment
- "doublon"  : même fait/annonce déjà publié (même acteur + même événement précis)
- "rebond"   : évolution notable d'un sujet couvert (chiffre actualisé, décision officielle, réaction, suite directe)

Réponds UNIQUEMENT avec JSON compact (sans markdown) :
{{"1":{{"s":"nouveau"}},"2":{{"s":"doublon","r":{{"t":"titre historique exact","d":"2024-01-15"}}}},"3":{{"s":"rebond","r":{{"t":"titre","d":"2024-01-14"}}}}}}"""

    result = call_claude(prompt, max_tokens=700)
    if not result:
        return {}

    try:
        json_match = re.search(r'\{.*\}', result, re.S)
        if not json_match:
            return {}
        raw = json.loads(json_match.group())
        out: dict = {}
        for k, v in raw.items():
            try:
                idx = int(k) - 1   # Convertir en index 0-based
                statut = v.get("s", "nouveau")
                ref_raw = v.get("r")
                ref = {"titre": ref_raw.get("t", ""), "date": ref_raw.get("d", "")} if ref_raw else None
                out[idx] = {"statut": statut, "ref": ref}
            except (ValueError, AttributeError, KeyError):
                pass
        return out
    except (json.JSONDecodeError, AttributeError):
        return {}

def _key_terms(titre: str) -> set[str]:
    """Extrait les termes significatifs d'un titre (≥4 caractères, hors stop-words)."""
    STOP = {
        "the","a","an","and","or","but","in","on","at","to","for","of","with",
        "is","are","was","were","has","have","it","its","this","that","how",
        "why","what","when","from","by","as","le","la","les","un","une","des",
        "de","du","et","ou","en","sur","avec","pour","par","dans","est","sont",
        "qui","que","plus","dans","leur","leurs","son","sa","ses","nous","vous",
    }
    words = re.findall(r"[a-zA-ZÀ-ÿ]{4,}", titre.lower())
    return {w for w in words if w not in STOP}


def detect_rebond(item: dict, historique: list,
                  min_overlap: int = 2, max_overlap: int = 4,
                  lookback_days: int = 14) -> tuple[bool, dict | None]:
    """
    Analyse le chevauchement thématique entre un article et l'historique récent.

    Retourne (is_duplicate, rebond_info) :
    - is_duplicate=True  : chevauchement ≥ max_overlap → même sujet, écarter
    - rebond_info        : dict {titre, date} si évolution notable (min ≤ overlap < max)
    - (False, None)      : sujet nouveau
    """
    terms = _key_terms(item.get("titre", ""))
    if not terms:
        return False, None

    best_overlap = 0
    best_match: dict | None = None

    for row in historique[:lookback_days]:
        row_date = row.get("date", "")
        for titre_hist in row.get("titres", []):
            hist_terms = _key_terms(titre_hist)
            overlap = len(terms & hist_terms)
            if overlap >= max_overlap:
                return True, None          # Même sujet — écarter
            if min_overlap <= overlap > best_overlap:
                best_overlap = overlap
                best_match = {"titre": titre_hist, "date": row_date}

    return False, best_match              # (False, None) ou (False, rebond_info)


# ─── SOURCE SCORING & DISCOVERY ──────────────────────────────────────────────

def detect_source_candidates(backlog: list, sources: dict, min_count: int = 3) -> list:
    """
    Identifie les domaines fréquents dans le backlog (≥ min_count occurrences)
    qui ne sont pas encore dans sources_primaires.
    Retourne une liste triée par occurrences décroissantes.
    """
    from urllib.parse import urlparse

    primary_domains: set[str] = set()
    primaires = (sources.get("sources_acteurs_ia")
                 or sources.get("sources_primaires")
                 or [])
    for s in primaires:
        try:
            primary_domains.add(urlparse(s.get("url", "")).netloc)
        except Exception:
            pass

    domain_count: dict[str, int] = {}
    domain_nom: dict[str, str] = {}

    for item in backlog:
        for s in item.get("sources", []):
            url = s.get("url", "")
            try:
                domain = urlparse(url).netloc
            except Exception:
                continue
            if not domain or domain in primary_domains:
                continue
            domain_count[domain] = domain_count.get(domain, 0) + 1
            if domain not in domain_nom:
                domain_nom[domain] = s.get("nom", domain)

    candidates = [
        {
            "nom": domain_nom[d],
            "domaine": d,
            "url": f"https://{d}",
            "occurrences": c,
        }
        for d, c in domain_count.items() if c >= min_count
    ]
    return sorted(candidates, key=lambda x: -x["occurrences"])


def update_source_scores(today: dict, sources: dict, feedback: dict) -> dict:
    """
    Ajuste score_global des sources primaires après chaque édition :
    - Article sélectionné dans l'édition  → +0.10 (max 5.0)
    - Source absente de l'édition          → −0.02 (min 1.0)
    - Feedback positif sur un article      → +0.05 supplémentaire
    Modifie sources en place et retourne l'objet mis à jour.
    """
    from urllib.parse import urlparse

    # Domaines ayant contribué à l'édition du jour
    selected_domains: set[str] = set()
    for n in today.get("news", []):
        for s in n.get("sources", []):
            try:
                d = urlparse(s.get("url", "")).netloc
                if d:
                    selected_domains.add(d)
            except Exception:
                pass

    # Domaines ayant reçu un feedback positif
    fb_articles = feedback.get("articles", {})
    feedback_domains: set[str] = set()
    for n in today.get("news", []):
        if fb_articles.get(n.get("id", ""), 0) > 0:
            for s in n.get("sources", []):
                try:
                    d = urlparse(s.get("url", "")).netloc
                    if d:
                        feedback_domains.add(d)
                except Exception:
                    pass

    updated = 0
    primaires = (sources.get("sources_acteurs_ia")
                 or sources.get("sources_primaires")
                 or [])
    for source in primaires:
        try:
            domain = urlparse(source.get("url", "")).netloc
        except Exception:
            continue
        if not domain:
            continue

        score = float(source.get("score_global", 3.0))
        if domain in selected_domains:
            score = min(5.0, round(score + 0.10, 2))
        else:
            score = max(1.0, round(score - 0.02, 2))
        if domain in feedback_domains:
            score = min(5.0, round(score + 0.05, 2))

        if score != source.get("score_global"):
            source["score_global"] = score
            updated += 1

    if updated:
        print(f"  [sources] score_global mis à jour pour {updated} source(s)")
    return sources


# ─── UPDATE ANNEXES ───────────────────────────────────────────────────────────

def update_annexes(today: dict, date_ctx: DateCtx, config: dict, backlog: list[dict], historique: list[dict], sources: dict, feedback: dict):
    historique = [{
        "date": date_ctx.date,
        "ids": [x["id"] for x in today["news"]],
        "titres": [x["titre"] for x in today["news"]],
        "categories": [x["categorie"] for x in today["news"]],
    }] + [x for x in historique if x.get("date") != date_ctx.date]
    write_json(HISTORIQUE_JSON, historique[:30])

    selected_titles = {x["titre"] for x in today["news"]}
    dec_pct   = config.get("scoring", {}).get("decroissance_quotidienne_pct", 15)
    min_score = config.get("scoring", {}).get("score_minimum_backlog", 10)
    # Garde-fous : on borne les valeurs configurables pour éviter des comportements aberrants
    dec_pct   = max(3.0, min(40.0, float(dec_pct)))   # entre 3 %/jour et 40 %/jour
    min_score = max(5,   min(30,   int(min_score)))    # entre 5 et 30
    dec       = dec_pct / 100
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

    # Préserver les champs primaires/relais s'ils existent déjà dans sources.json
    for key in ("meta", "sources_acteurs_ia", "sources_relais"):
        if key not in sources:
            val = _extract_sources_default_key(key)
            if val is not None:
                sources[key] = val

    # Étape 7 — Ajuster le score_global des sources primaires
    sources = update_source_scores(today, sources, feedback)

    # Étape 6 — Détecter les sources candidates (domaines fréquents non encore primaires)
    candidates = detect_source_candidates(backlog, sources, min_count=3)
    if candidates:
        print(f"  [sources] {len(candidates)} source(s) candidate(s) détectée(s) : {[c['domaine'] for c in candidates[:3]]}")
    sources["sources_candidates"] = candidates

    write_json(SOURCES_JSON, sources)


def _extract_sources_default_key(key: str):
    """
    Lit SOURCES_DEFAULT depuis data.js et extrait une clé spécifique.
    Utilisé pour initialiser sources.json au premier run.
    """
    try:
        text = DATA_JS.read_text(encoding="utf-8")
        # SOURCES_DEFAULT est du JS avec clés non quotées — on le convertit en JSON
        m = re.search(r"const SOURCES_DEFAULT\s*=\s*(\{.*?\});\s*\n", text, re.S)
        if not m:
            return None
        js_obj = m.group(1)
        # Ajouter des guillemets autour des clés non quotées
        json_str = re.sub(r'(?<=[{,\[]\s*)(\w+)(?=\s*:)', r'"\1"', js_obj)
        json_str = re.sub(r',\s*}', '}', json_str)   # trailing commas
        json_str = re.sub(r',\s*]', ']', json_str)
        data = json.loads(json_str)
        return data.get(key)
    except Exception as e:
        print(f"  [sources] Impossible d'extraire {key} depuis data.js : {e}")
        return None

    retour = {
        "date": date_ctx.date,
        "statut": "en_attente",
        "notes": {x["id"]: None for x in today["news"]},
        "commentaire": "",
    }
    write_json(BRIEFING / f"retour-{date_ctx.date}.json", retour)


# ─── VALIDATE ─────────────────────────────────────────────────────────────────

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


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", default="briefing-ia", help="Slug de la newsletter (ex: briefing-ia)")
    parser.add_argument("--date", help="Date forcée YYYY-MM-DD")
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

    if ANTHROPIC_API_KEY:
        print(f"[main] API Claude disponible — génération IA activée")
    else:
        print(f"[main] ANTHROPIC_API_KEY absente — génération IA désactivée (bodies du backlog utilisés)")

    config = read_json(CONFIG_JSON, {})

    # ── Charger persona + categories depuis config (data-driven) ─────────────
    global _CATEGORIES, _PERSONA
    _CATEGORIES = config.get("categories") or _FALLBACK_CATEGORIES
    _PERSONA    = config.get("persona") or _FALLBACK_PERSONA
    print(f"[main] {len(_CATEGORIES)} catégories : {', '.join(_CATEGORIES.keys())}")
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
    update_data_js(today, date_ctx, args_slug=args.slug)
    update_annexes(today, date_ctx, config, backlog, historique, sources, feedback)

    print(f"Génération terminée pour {date_ctx.date} ({date_ctx.date_longue})")


if __name__ == "__main__":
    main()
