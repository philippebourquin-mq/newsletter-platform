"""
scripts/lib/builder.py
Logique de sélection et scoring des articles.

Fonctions :
    _key_terms              — mots-clés significatifs d'un titre
    detect_rebond           — détection doublon / rebond thématique
    detect_source_candidates — domaines fréquents non encore sources primaires
    update_source_scores    — ajustement score_global sources
    process_feedback        — intégration des retours lecteurs
    parse_newsletter_md     — parse un .md en {chapeau, articles}
    semantic_rebond_classify — classification sémantique Claude (batch)
    make_entry_from_backlog  — construit l'entrée news depuis un item backlog
    build_today             — sélectionne et construit l'édition du jour
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from lib.claude_client import call_claude
from lib.platform_config import PLATFORM
from lib.renderer import (
    generate_article_body,
    generate_chapeau,
    generate_radar_desc,
    load_recent_newsletter_summaries,
)
from lib.utils import (
    DateCtx,
    NewsletterConfig,
    get_label,
    get_default_cat,
    is_placeholder_body,
    read_json,
    write_json,
)


# ── Rebond detection ──────────────────────────────────────────────────────────

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


def detect_rebond(
    item: dict,
    historique: list,
    min_overlap: int | None = None,
    max_overlap: int | None = None,
    lookback_days: int = 14,
) -> tuple[bool, dict | None]:
    """
    Analyse le chevauchement thématique entre un article et l'historique récent.

    Retourne (is_duplicate, rebond_info) :
    - is_duplicate=True  : chevauchement ≥ max_overlap → même sujet, écarter
    - rebond_info        : dict {titre, date} si évolution notable
    - (False, None)      : sujet nouveau
    """
    if min_overlap is None:
        min_overlap = PLATFORM.min_overlap_rebond
    if max_overlap is None:
        max_overlap = PLATFORM.max_overlap_duplicate
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
                return True, None
            if min_overlap <= overlap > best_overlap:
                best_overlap = overlap
                best_match = {"titre": titre_hist, "date": row_date}

    return False, best_match


# ── Source scoring & discovery ────────────────────────────────────────────────

def detect_source_candidates(
    backlog: list,
    sources: dict,
    min_count: int = 3,
) -> list:
    """Identifie les domaines fréquents dans le backlog non encore sources primaires."""
    from urllib.parse import urlparse

    primary_domains: set[str] = set()
    primaires = sources.get("sources_acteurs_ia") or sources.get("sources_primaires") or []
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
        {"nom": domain_nom[d], "domaine": d, "url": f"https://{d}", "occurrences": c}
        for d, c in domain_count.items() if c >= min_count
    ]
    return sorted(candidates, key=lambda x: -x["occurrences"])


def update_source_scores(today: dict, sources: dict, feedback: dict) -> dict:
    """Ajuste score_global des sources primaires après chaque édition."""
    from urllib.parse import urlparse

    selected_domains: set[str] = set()
    for n in today.get("news", []):
        for s in n.get("sources", []):
            try:
                d = urlparse(s.get("url", "")).netloc
                if d:
                    selected_domains.add(d)
            except Exception:
                pass

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
    primaires = sources.get("sources_acteurs_ia") or sources.get("sources_primaires") or []
    for source in primaires:
        try:
            domain = urlparse(source.get("url", "")).netloc
        except Exception:
            continue
        if not domain:
            continue

        score = float(source.get("score_global", 3.0))
        if domain in selected_domains:
            score = min(PLATFORM.source_score_max, round(score + PLATFORM.source_score_bonus_multi, 2))
        else:
            score = max(PLATFORM.source_score_min, round(score - PLATFORM.source_score_malus_ignored, 2))
        if domain in feedback_domains:
            score = min(PLATFORM.source_score_max, round(score + PLATFORM.source_score_bonus_click, 2))

        if score != source.get("score_global"):
            source["score_global"] = score
            updated += 1

    if updated:
        print(f"  [sources] score_global mis à jour pour {updated} source(s)")
    return sources


# ── Feedback processing ───────────────────────────────────────────────────────

def process_feedback(
    date_ctx: DateCtx,
    config: dict,
    feedback: dict,
    briefing_dir: Path,
) -> dict:
    """Intègre les retours lecteurs (retour-*.json et feedback_ui.json)."""
    bonus = config.get("scoring", {}).get("bonus_feedback_pts", PLATFORM.bonus_feedback_pts_default)
    feedback.setdefault("articles", {})

    for file in briefing_dir.glob("retour-*.json"):
        payload = read_json(file, {})
        if payload.get("statut") != "en_attente":
            continue
        for article_id, note in payload.get("notes", {}).items():
            if isinstance(note, (int, float)) and note >= 4:
                feedback["articles"][article_id] = feedback["articles"].get(article_id, 0) + bonus
        payload["statut"] = "traité"
        write_json(file, payload)

    fb_ui_file = briefing_dir / "feedback_ui.json"
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


# ── Markdown parser ───────────────────────────────────────────────────────────

def parse_newsletter_md(content: str, date: str) -> dict:
    """Parse un fichier markdown newsletter → {chapeau, articles}."""
    lines = content.splitlines()
    chapeau = ""
    articles = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("> ") and not chapeau:
            chapeau = line[2:].strip()
        elif re.match(r"^## \d+\.\s+", line):
            titre = re.sub(r"^## \d+\.\s+", "", line).strip()
            body_lines = []
            i += 1
            # Sauter la ligne catégorie/confiance
            while i < len(lines) and (
                lines[i].startswith("**Catégorie") or lines[i].startswith("↩")
            ):
                i += 1
            # Collecter le body jusqu'à "Sources :"
            while i < len(lines) and not lines[i].startswith("Sources :") and not re.match(r"^## \d+\.", lines[i]):
                if lines[i].strip():
                    body_lines.append(lines[i].strip())
                i += 1
            body = " ".join(body_lines)
            articles.append({"date": date, "titre": titre, "body": body[:500]})
            continue
        i += 1

    return {"chapeau": chapeau, "articles": articles}


# ── Semantic rebond classification ────────────────────────────────────────────

def semantic_rebond_classify(
    candidates: list[dict],
    recent_articles: list[dict],
) -> dict:
    """
    Appelle Claude UNE FOIS pour classifier sémantiquement les candidats backlog.
    Retourne {idx (0-based): {"statut": "nouveau"|"doublon"|"rebond", "ref": dict|None}}
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not candidates or not recent_articles:
        return {}

    hist_lines = [
        f"  [{a['date']}] {a['titre']} — {a.get('body', '')[:120]}"
        for a in recent_articles[:40]
    ]
    cand_lines = [
        f"{i + 1}. {item.get('titre', '')}\n"
        f"   [{', '.join(s.get('nom', '') for s in item.get('sources', []))[:60]}] "
        f"{item.get('body', '')[:160]}"
        for i, item in enumerate(candidates)
    ]

    prompt = f"""Tu analyses des articles pour une newsletter IA.

ARTICLES DÉJÀ PUBLIÉS (derniers jours) :
{chr(10).join(hist_lines)}

NOUVEAUX CANDIDATS À CLASSIFIER ({len(candidates)}) :
{chr(10).join(cand_lines)}

Classe chaque candidat :
- "nouveau"  : sujet non couvert récemment
- "doublon"  : même fait/annonce déjà publié (même acteur + même événement précis)
- "rebond"   : évolution notable d'un sujet couvert (chiffre actualisé, décision officielle, réaction)

Réponds UNIQUEMENT avec JSON compact (sans markdown) :
{{"1":{{"s":"nouveau"}},"2":{{"s":"doublon","r":{{"t":"titre historique exact","d":"2024-01-15"}}}}}}"""

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
                idx = int(k) - 1
                statut = v.get("s", "nouveau")
                ref_raw = v.get("r")
                ref = {"titre": ref_raw.get("t", ""), "date": ref_raw.get("d", "")} if ref_raw else None
                out[idx] = {"statut": statut, "ref": ref}
            except (ValueError, AttributeError, KeyError):
                pass
        return out
    except (json.JSONDecodeError, AttributeError):
        return {}


# ── Article builder ───────────────────────────────────────────────────────────

def make_entry_from_backlog(
    item: dict,
    idx: int,
    date_ctx: DateCtx,
    nl_config: NewsletterConfig,
    rebond_info: dict | None = None,
) -> dict:
    """Construit l'entrée news complète depuis un item du backlog."""
    title    = item.get("titre", f"Signal IA #{idx}")
    category = item.get("categorie", get_default_cat(nl_config.categories))
    label    = item.get("label") or get_label(category)

    body = item.get("body", "")
    if is_placeholder_body(body):
        generated = generate_article_body(item, nl_config)
        body = generated if generated else (
            f"Signal important dans le domaine {label.lower()}. "
            "Consultez les sources pour les détails complets de cette annonce."
        )

    sources = item.get("sources")
    if not sources:
        url = item.get("url", "https://example.com")
        sources = [{"nom": "Source", "url": url}]

    confiance = "✅ source primaire" if len(sources) == 1 else "🔄 multi-sources"

    entry = {
        "id":        f"{date_ctx.date}-{idx:03d}",
        "num":       idx,
        "categorie": category,
        "label":     label,
        "confiance": confiance,
        "titre":     title,
        "body":      body,
        "sources":   sources,
    }
    if rebond_info:
        entry["rebond_de"] = rebond_info
    return entry


# ── Build today ───────────────────────────────────────────────────────────────

def build_today(
    date_ctx: DateCtx,
    config: dict,
    backlog: list[dict],
    historique: list[dict],
    nl_config: NewsletterConfig,
    newsletters_dir: Path,
) -> dict:
    """Sélectionne les articles et construit l'édition du jour."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    nb_main  = int(config.get("contenu", {}).get("nb_news_principal", 6))
    nb_radar = int(config.get("contenu", {}).get("nb_news_radar", 6))

    recent_titles = set()
    for row in historique[:5]:
        recent_titles.update(row.get("titres", []))

    usable = [x for x in backlog if x.get("titre") and x.get("titre") not in recent_titles]
    if len(usable) < nb_main:
        usable = list(backlog)

    usable_sorted = sorted(usable, key=lambda x: x.get("score", 0), reverse=True)

    inspect_pool = usable_sorted[:nb_main * PLATFORM.inspect_pool_multiplier]
    classifications: dict = {}

    if api_key:
        recent_summaries = load_recent_newsletter_summaries(newsletters_dir, date_ctx, days=7)
        if recent_summaries:
            print(f"[build_today] Analyse sémantique de {len(inspect_pool)} candidats vs {len(recent_summaries)} articles récents…")
            classifications = semantic_rebond_classify(inspect_pool, recent_summaries)
        else:
            print("[build_today] Pas d'historique markdown disponible — fallback keyword")
    else:
        print("[build_today] API indisponible — détection rebond par mots-clés uniquement")

    selected: list[dict] = []
    rebond_map: dict[str, dict] = {}
    cat_counts: dict[str, int] = {}
    max_per_cat = PLATFORM.max_per_cat(nb_main)

    for i, item in enumerate(inspect_pool):
        if len(selected) >= nb_main:
            break

        cls = classifications.get(i)
        if cls:
            statut = cls.get("statut", "nouveau")
            if statut == "doublon":
                print(f"  [doublon] Écarté : {item.get('titre', '')[:70]}")
                continue
            if statut == "rebond" and cls.get("ref"):
                rebond_map[item["titre"]] = cls["ref"]
                print(f"  [rebond] {item.get('titre', '')[:50]} ← {cls['ref'].get('titre', '')[:40]}")
        else:
            is_dup, rebond_kw = detect_rebond(item, historique)
            if is_dup:
                print(f"  [doublon-kw] Écarté : {item.get('titre', '')[:70]}")
                continue
            if rebond_kw:
                rebond_map[item["titre"]] = rebond_kw

        cat = item.get("categorie", "")
        if cat_counts.get(cat, 0) >= max_per_cat:
            print(f"  [panachage] Écarté (quota {max_per_cat}/{cat}) : {item.get('titre', '')[:60]}")
            continue

        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        selected.append(item)

    print(f"[build_today] {len(selected)} articles sélectionnés (score max: {selected[0].get('score', 0) if selected else 0})")

    news = [
        make_entry_from_backlog(item, i + 1, date_ctx, nl_config, rebond_map.get(item["titre"]))
        for i, item in enumerate(selected)
    ]

    # Radar
    selected_titles = {x["titre"] for x in selected}
    radar_pool  = [x for x in usable_sorted if x["titre"] not in selected_titles]
    radar_items = []
    for x in radar_pool[:nb_radar * 2]:
        pool_idx = usable_sorted.index(x) if x in usable_sorted else -1
        if classifications.get(pool_idx, {}).get("statut") == "doublon":
            continue
        radar_items.append(x)
        if len(radar_items) >= nb_radar:
            break

    radar = []
    for x in radar_items:
        desc = x.get("body", "")
        if desc and not is_placeholder_body(desc):
            first = re.split(r'(?<=[.!?])\s', desc)[0]
            desc = first[:117] + "…" if len(first) > 120 else first
        else:
            desc = (
                generate_radar_desc(x) if api_key
                else "Point à suivre pour les prochains arbitrages produit et métier."
            )
        radar.append({
            "titre": x.get("titre", "Signal radar"),
            "desc":  desc,
            "url":   x.get("url", "https://example.com"),
        })

    chapeau = generate_chapeau(date_ctx, news)

    return {
        "date":       date_ctx.date,
        "date_longue": date_ctx.date_longue,
        "chapeau":    chapeau,
        "news":       news,
        "radar":      radar,
    }
