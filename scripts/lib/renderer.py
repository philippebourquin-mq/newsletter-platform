"""
scripts/lib/renderer.py
Génération de contenu textuel et HTML pour les newsletters.

Fonctions :
    generate_article_body  — corps d'article via Claude
    generate_radar_desc    — description radar via Claude
    generate_chapeau       — chapeau d'introduction via Claude
    load_recent_newsletter_summaries — charge les résumés markdown récents
    write_markdown         — écrit le fichier .md de l'édition
    write_html             — écrit le fichier .html de l'édition
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from lib.claude_client import call_claude
from lib.utils import DateCtx, NewsletterConfig, get_label, get_default_cat, is_placeholder_body

_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


# ── Génération via Claude ─────────────────────────────────────────────────────

def generate_article_body(item: dict, nl_config: NewsletterConfig) -> str:
    """Génère un corps d'article contextuel via Claude API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    cats = nl_config.categories
    pers = nl_config.persona

    title = item.get("titre", "")
    cat_slug = item.get("categorie", get_default_cat(cats))
    label = item.get("label") or get_label(cat_slug)
    url = item.get("url", "")
    sources_text = " / ".join(
        s.get("nom", "") for s in item.get("sources", []) if s.get("nom")
    )
    cat_desc = cats.get(cat_slug, "")
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


def generate_radar_desc(item: dict) -> str:
    """Génère une description courte pour le radar via Claude."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ""

    title  = item.get("titre", "")
    url    = item.get("url", "")
    body   = item.get("body", "")[:200]
    prompt = (
        f"Résume en UNE phrase courte (max 120 caractères) le signal suivant pour une newsletter IA :\n"
        f"Titre : {title}\nURL : {url}\nContexte : {body}\n\n"
        f"Réponds UNIQUEMENT avec la phrase, sans guillemets."
    )
    return call_claude(prompt, max_tokens=80)


def generate_chapeau(date_ctx: DateCtx, news: list[dict]) -> str:
    """Génère le chapeau introductif de l'édition via Claude."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return f"Édition du {date_ctx.date_longue}."

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
"Ce vendredi marque une double accélération : les modèles les plus puissants franchissent les portes des systèmes régaliens — le Pentagone discute d'un accord Gemini classifié — tandis que la gouvernance reprend la main en Europe, avec Elon Musk convoqué à Paris dans l'enquête Grok."

Réponds UNIQUEMENT avec le texte du chapeau, sans balise ni introduction."""

    result = call_claude(prompt, max_tokens=200)
    if result:
        print(f"  [Claude] Chapeau généré pour {date_ctx.date}")
    return result or f"Édition du {date_ctx.date_longue}."


# ── Chargement des résumés récents (pour rebond sémantique) ──────────────────

def load_recent_newsletter_summaries(
    newsletters_dir: Path,
    date_ctx: DateCtx,
    days: int = 7,
) -> list[dict]:
    """
    Charge titres + extraits de corps des newsletters récentes depuis les .md.
    Retourne [{date, titre, body_short}] pour alimenter le prompt Claude.
    """
    summaries = []
    md_files = sorted(newsletters_dir.glob("newsletter-*.md"), reverse=True)
    pattern = re.compile(
        r"^## \d+\.\s+(.+?)\s*\n"
        r"(?:\*\*Cat[eé]gorie.*?\n)?"
        r"(?:↩.*?\n)?"
        r"(.+?)(?=\nSources|\Z)",
        re.S | re.M,
    )
    for md_file in md_files[:days + 1]:
        date_str = md_file.stem.replace("newsletter-", "")
        if date_str == date_ctx.date:
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in pattern.finditer(content):
            titre = m.group(1).strip()
            body_raw = m.group(2).strip()
            body_short = re.split(r'(?<=[.!?])\s', body_raw)[0][:160]
            summaries.append({"date": date_str, "titre": titre, "body": body_short})
        if len(summaries) >= 50:
            break
    return summaries


# ── Écriture des fichiers ─────────────────────────────────────────────────────

def write_markdown(
    today: dict,
    date_ctx: DateCtx,
    newsletters_dir: Path,
    nl_name: str,
) -> None:
    """Écrit le fichier .md de l'édition dans newsletters_dir."""
    lines = [f"# {nl_name} — {date_ctx.date_longue}", "", f"> {today['chapeau']}", ""]
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
    (newsletters_dir / f"newsletter-{date_ctx.date}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def write_html(
    today: dict,
    date_ctx: DateCtx,
    newsletters_dir: Path,
    template_html: Path,
) -> None:
    """Écrit le fichier .html de l'édition dans newsletters_dir."""
    template = template_html.read_text(encoding="utf-8")
    articles_html = []
    for idx, n in enumerate(today["news"], start=1):
        src = " · ".join(
            f"<a href=\"{s['url']}\">{s['nom']}</a>" for s in n.get("sources", [])
        )
        articles_html.append(
            f"<section class='box'>"
            f"<h2>{idx}. {n['titre']}</h2>"
            f"<p><strong>Catégorie :</strong> {n['label']} | "
            f"<strong>Confiance :</strong> {n['confiance']}</p>"
            f"<p>{n['body']}</p>"
            f"<p><strong>Sources :</strong> {src}</p>"
            f"</section>"
        )
    radar_html = "".join(
        f"<li><strong>{r['titre']}</strong> — {r['desc']} "
        f"<a href=\"{r['url']}\">Lire</a></li>"
        for r in today.get("radar", [])
    )
    out = (
        template
        .replace("{{DATE_LONGUE}}", date_ctx.date_longue)
        .replace("{{CHAPEAU}}", today["chapeau"])
        .replace("{{ARTICLES_HTML}}", "\n".join(articles_html))
        .replace("{{RADAR_HTML}}", radar_html)
    )
    (newsletters_dir / f"newsletter-{date_ctx.date}.html").write_text(out, encoding="utf-8")
