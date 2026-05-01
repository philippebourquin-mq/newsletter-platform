#!/usr/bin/env python3
"""
fetch_backlog.py — Alimente backlog.json depuis les flux RSS IA configurés
dans sources_rss.json.

Flux :
  1. Fetch tous les flux RSS de la config
     → Fallback Tavily si un flux RSS est inaccessible
  2. Fetch les sources de type "search" via Tavily (LinkedIn, personnalités, etc.)
  3. Filtre les articles des dernières N heures, pertinents IA
  4. Déduplique et booste les articles repris par plusieurs sources
  5. Fetch le contenu HTML de chaque article retenu (ou extrait Tavily)
  6. Appelle Claude pour générer un corps factuel + détecter la catégorie
  7. Fusionne avec le backlog existant (sans écraser les articles déjà présents)
"""
from __future__ import annotations

import json
import math
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False
    print("[fetch_backlog] feedparser non disponible — installe-le via pip install feedparser")

try:
    from tavily import TavilyClient
    HAS_TAVILY = True
except ImportError:
    HAS_TAVILY = False

ROOT = Path(__file__).resolve().parents[1]

# Chemins initialisés dynamiquement par _init_paths(slug) dans main()
BRIEFING: Path
BACKLOG_JSON: Path
HISTORIQUE_JSON: Path
SOURCES_RSS_JSON: Path
SOURCES_JSON: Path
CONFIG_JSON: Path

def _init_paths(slug: str) -> None:
    """Initialise toutes les constantes de chemin pour un slug de newsletter donné."""
    global BRIEFING, BACKLOG_JSON, HISTORIQUE_JSON, SOURCES_RSS_JSON, SOURCES_JSON, CONFIG_JSON
    BRIEFING         = ROOT / "newsletters" / slug
    BACKLOG_JSON     = BRIEFING / "backlog.json"
    HISTORIQUE_JSON  = BRIEFING / "historique.json"
    SOURCES_RSS_JSON = BRIEFING / "sources_rss.json"
    SOURCES_JSON     = BRIEFING / "sources.json"
    CONFIG_JSON      = BRIEFING / "config.json"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY    = os.environ.get("TAVILY_API_KEY", "")

USER_AGENT = (
    "Mozilla/5.0 (compatible; BriefingIA-Bot/1.0; "
    "+https://github.com/philippebourquin-mq/newsletter-platform)"
)

# ─── SOURCES RELAIS — AUTO-RÉFÉRENCE ─────────────────────────────────────────
# Les sources "relais" (influenceurs, newsletters, commentateurs) ne doivent pas
# alimenter la newsletter avec des articles qui les concernent elles-mêmes.
# Règle simple : si le nom de la source apparaît dans le titre → l'article parle
# d'elle → on filtre. Applicable uniquement aux sources marquées "relay": true.
#
# Les sources primaires (OpenAI, Anthropic, Google…) sont exclues de cette logique :
# elles SONT le sujet — leurs annonces sont exactement ce qu'on veut capter.

# Mots vides à ignorer lors de la tokenisation du nom de la source
_NAME_STOP = {"le", "la", "les", "un", "une", "des", "de", "du", "et", "ou",
              "the", "a", "an", "of", "and", "or", "for", "by", "in"}


def _source_tokens(source_nom: str) -> set[str]:
    """
    Extrait les tokens significatifs du nom d'une source (longueur ≥ 3, hors mots vides).
    Cas spécial : handles sociaux (@unefille.ia) → extrait aussi le suffixe de chaque
    partie concaténée (ex: "unefille" → ajoute "fille", dernier mot reconnaissable).
    """
    raw = re.findall(r"[a-zàâéèêëïîôùûü]+", source_nom.lower())
    result: set[str] = set()
    for t in raw:
        if len(t) >= 3 and t not in _NAME_STOP:
            result.add(t)
        # Pour les handles concaténés (ex: "unefille"), extraire le suffixe de 4-6 chars
        # qui correspond souvent au mot significatif final (ex: "fille")
        if len(t) >= 7 and source_nom.startswith("@"):
            suffix = t[-5:] if len(t) >= 5 else t[-4:]
            if suffix not in _NAME_STOP:
                result.add(suffix)
    return result


def is_relay_self_ref(titre: str, source_nom: str) -> bool:
    """
    Retourne True si le titre d'un article mentionne la source relais elle-même.
    Dans ce cas l'article parle de la source → à filtrer.
    """
    title_lc = titre.lower()
    tokens   = _source_tokens(source_nom)
    return any(tok in title_lc for tok in tokens)


# ─── PLATEFORMES NON-SOURCES ──────────────────────────────────────────────────
# Plateformes de diffusion vidéo ou sociale : ne produisent pas d'articles
# textuels exploitables et ne doivent pas être traitées comme des sources.
# Elles peuvent apparaître en lien dans un article, mais pas en être l'URL principale.

NON_SOURCE_PLATFORMS = {
    "youtube.com", "www.youtube.com", "youtu.be",
    "tiktok.com", "www.tiktok.com",
    "instagram.com", "www.instagram.com",
    "twitter.com", "x.com", "www.twitter.com",
    "facebook.com", "www.facebook.com",
    "reddit.com", "www.reddit.com",
    "twitch.tv", "www.twitch.tv",
    "vimeo.com", "www.vimeo.com",
}


def is_non_source_platform(url: str) -> bool:
    """Retourne True si l'URL pointe vers une plateforme vidéo/sociale, pas un article."""
    try:
        domain = url.split("//")[1].split("/")[0].lower()
        return domain in NON_SOURCE_PLATFORMS
    except (IndexError, AttributeError):
        return False


# Chemins génériques qui indiquent une page de catégorie ou d'accueil
_GENERIC_PATHS = {
    "", "/", "/research", "/blog", "/news", "/about", "/products",
    "/models", "/api", "/home", "/index", "/fr", "/en",
}

def is_homepage_or_generic(url: str, titre: str) -> bool:
    """
    Retourne True si l'URL est une page d'accueil / catégorie (pas un article).
    Détecte aussi les titres génériques style 'OpenAI | OpenAI' ou 'Home \\ Anthropic'.
    """
    try:
        path = "/" + "/".join(url.split("//")[1].split("/")[1:])
        path = path.rstrip("/").lower() or "/"
        # Chemin vide ou catégorie de 1er niveau générique
        if path in _GENERIC_PATHS:
            return True
        # Chemin très court sans slug d'article (ex: /research ou /blog)
        if path.count("/") < 2 and path in _GENERIC_PATHS:
            return True
    except Exception:
        pass

    # Titre générique : contient " | " ou " \\ " (séparateur de site)
    if " | " in titre or " \\ " in titre:
        return True
    # Titre trop court pour être un article (≤ 3 mots)
    if len(titre.split()) <= 3:
        return True

    return False


# ─── MOTS-CLÉS ────────────────────────────────────────────────────────────────

# Score +20 si le titre/description contient l'un de ces termes
AI_KEYWORDS_HIGH = [
    "gpt", "claude", "gemini", "llama", "mistral", "grok",
    "chatgpt", "copilot", "llm", "large language model",
    "ai agent", "agent ia", "multimodal", "rag", "fine-tun",
    "anthropic", "openai", "deepmind", "meta ai", "xai",
    "intelligence artificielle", "modèle de langage",
]
# Score +8 si le titre/description contient l'un de ces termes
AI_KEYWORDS_MED = [
    "artificial intelligence", "machine learning", "deep learning",
    "neural network", "natural language", "computer vision",
    "generative ai", "foundation model", "transformer",
    "embedding", "inference", "nvidia", "gpu cluster",
    " ai ", " ia ", "générative",
]

STOP_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "is", "are", "was", "were", "has", "have", "it", "its",
    "this", "that", "how", "why", "what", "when", "from", "by", "as",
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "ou", "en",
    "sur", "avec", "pour", "par", "dans", "est", "sont", "qui", "que",
}

# ─── CATÉGORIE PAR MOTS-CLÉS ─────────────────────────────────────────────────

CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("societal", [
        "regulation", "law", "policy", "government", "eu", "ai act", "gdpr",
        "ethic", "réglementation", "loi", "gouvernement", "éthique", "deepfake",
        "droit", "sénat", "parlement", "privacy", "surveillance", "bias",
    ]),
    ("economie", [
        "funding", "billion", "million", "invest", "acquisition", "ipo", "revenue",
        "startup", "valuation", "levée", "rachat", "financement", "emploi", "layoff",
        "hiring", "job", "market", "stock", "share", "deal",
    ]),
    # Use Cases : déploiements concrets en entreprise, retours d'expérience éprouvés,
    # adoption sectorielle — PAS les annonces produits ni les articles techniques
    ("use_cases", [
        "deploy", "automat", "workflow", "adoption", "implementation", "pilot",
        "entreprise", "client", "médical", "santé", "retail", "legal",
        "education", "manufacturing", "healthcare", "cas d'usage", "retour d'expérience",
        "gain de productivité", "roi", "success story", "mise en production",
    ]),
    # Fun Facts : l'inattendu — faits surprenants, records, premières mondiales,
    # recherches atypiques, chiffres insolites, applications décalées
    ("fun_facts", [
        "unexpected", "surprising", "record", "first ever", "unprecedented", "bizarre",
        "insolite", "étonnant", "inattendu", "première mondiale", "découverte",
        "percée", "paradoxe", "robot", "humanoid", "autonomous", "sci-fi",
        "jamais vu", "révèle", "démontre que", "prouve que",
    ]),
    # Fonctionnel : vie des modèles et des outils — sorties, benchmarks, architectures,
    # APIs, frameworks, recherche technique fondamentale
    ("fonctionnel", [
        "api", "model", "framework", "sdk", "benchmark", "architecture", "training",
        "inference", "fine-tun", "rag", "vector", "embedding", "open source",
        "release", "version", "update", "performance", "token", "context window",
        "weights", "checkpoint", "pre-train", "alignment", "evals",
    ]),
]


def detect_category(titre: str, description: str = "") -> str:
    text = (titre + " " + description).lower()
    scores: dict[str, int] = {}
    for cat, keywords in CATEGORY_RULES:
        count = sum(1 for kw in keywords if kw in text)
        if count:
            scores[cat] = count
    if not scores:
        return "fonctionnel"
    return max(scores, key=lambda k: scores[k])


LABEL_MAP = {
    "societal": "Sociétal",
    "economie": "Économie",
    "fonctionnel": "Fonctionnel",
    "use_cases": "Use Cases",
    "fun_facts": "Fun Facts",
}

# ─── HTML PARSER ──────────────────────────────────────────────────────────────

class TextExtractor(HTMLParser):
    """Extrait le texte brut d'un HTML en sautant scripts/styles/nav."""
    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside",
                 "form", "noscript", "iframe", "svg", "button"}

    def __init__(self):
        super().__init__()
        self.text_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self.text_parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self.text_parts)


def clean_html(html: str) -> str:
    parser = TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    text = parser.get_text()
    # Normaliser les espaces
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


# ─── TAVILY ───────────────────────────────────────────────────────────────────

def tavily_search(query: str, days: int = 2, max_results: int = 5) -> list[dict]:
    """
    Recherche via Tavily et retourne des items normalisés.
    Chaque item contient titre, url, content (extrait), et published_date.
    Retourne [] si Tavily n'est pas disponible.
    """
    if not HAS_TAVILY or not TAVILY_API_KEY:
        return []
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        resp = client.search(
            query=query,
            max_results=max_results,
            days=days,
            include_answer=False,
            search_depth="basic",
        )
        results = []
        for r in resp.get("results", []):
            titre = r.get("title", "").strip()
            url   = r.get("url", "").strip()
            if not titre or not url:
                continue
            if is_non_source_platform(url):
                continue
            if is_homepage_or_generic(url, titre):
                continue
            results.append({
                "titre":     titre,
                "url":       url,
                "content":   r.get("content", ""),        # extrait déjà propre
                "published": r.get("published_date", None),
            })
        return results
    except Exception as e:
        print(f"  [Tavily] Erreur : {e}")
        return []


def tavily_items_to_backlog(results: list[dict], source_nom: str,
                             fiabilite: int, window_hours: int) -> list[dict]:
    """Convertit les résultats Tavily en items normalisés pour le backlog."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    items = []
    for r in results:
        titre = r["titre"]
        url   = r["url"]

        # Filtrer par fraîcheur si la date est disponible
        published = None
        if r.get("published"):
            try:
                published = datetime.fromisoformat(r["published"].replace("Z", "+00:00"))
                if published < cutoff:
                    continue
            except Exception:
                pass

        freshness  = compute_freshness_score(published)
        ai_bonus   = compute_ai_score(titre, r.get("content", ""))
        score      = round(freshness + ai_bonus + (fiabilite / 100) * 20, 1)

        cat = detect_category(titre, r.get("content", ""))
        items.append({
            "titre":        titre,
            "url":          url,
            "categorie":    cat,
            "label":        LABEL_MAP.get(cat, "Fonctionnel"),
            "sources":      [{"nom": source_nom, "url": url}],
            "score":        score,
            "body":         "",
            "_source_nom":  source_nom,
            "_published":   r.get("published"),
            "_description": r.get("content", "")[:300],
            "_content":     r.get("content", ""),   # déjà extrait par Tavily
            "_duplicate":   False,
        })
    return items


# ─── RÉSEAU ───────────────────────────────────────────────────────────────────

def http_get(url: str, timeout: int = 10) -> str | None:
    """Fetch une URL et retourne le contenu texte, ou None en cas d'erreur."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except Exception as e:
        print(f"  [http] Erreur {url[:60]}: {e}")
        return None


def extract_youtube_video_id(url: str) -> str | None:
    """Extrait le video_id depuis une URL YouTube."""
    try:
        if "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0].split("/")[0]
        import urllib.parse as _up
        params = _up.parse_qs(_up.urlparse(url).query)
        vid = params.get("v", [None])[0]
        return vid
    except Exception:
        return None


def fetch_youtube_transcript(url: str, max_chars: int = 3000) -> str:
    """
    Extrait le transcript d'une vidéo YouTube (pas de clé API requise).
    Essaie le français d'abord, puis l'anglais.
    Retourne "" si le transcript est indisponible.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
    except ImportError:
        print("  [YouTube] youtube-transcript-api non installé")
        return ""

    video_id = extract_youtube_video_id(url)
    if not video_id:
        return ""

    import concurrent.futures
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                YouTubeTranscriptApi.get_transcript,
                video_id, languages=["fr", "fr-FR", "en", "en-US", "en-GB"]
            )
            transcript = future.result(timeout=15)
        text = " ".join(entry["text"] for entry in transcript)
        # Nettoyer les artefacts courants des sous-titres auto-générés
        text = re.sub(r"\[.*?\]", "", text)          # [Musique], [Applaudissements]…
        text = re.sub(r"\s{2,}", " ", text).strip()
        return text[:max_chars]
    except concurrent.futures.TimeoutError:
        print(f"  [YouTube] Timeout transcript ({video_id}) — ignoré")
        return ""
    except Exception as e:
        print(f"  [YouTube] Transcript indisponible ({video_id}): {type(e).__name__}")
        return ""


def is_youtube_url(url: str) -> bool:
    """Retourne True si l'URL est une vidéo YouTube."""
    return "youtube.com/watch" in url or "youtu.be/" in url


def fetch_article_text(url: str, max_chars: int = 2500) -> str:
    """Fetche le contenu d'un article. Utilise le transcript pour les vidéos YouTube."""
    if is_youtube_url(url):
        return fetch_youtube_transcript(url, max_chars=3000)
    html = http_get(url, timeout=8)
    if not html:
        return ""
    text = clean_html(html)
    return text[:max_chars]


# ─── CLAUDE API ───────────────────────────────────────────────────────────────

def call_claude(prompt: str, max_tokens: int = 500) -> str:
    if not ANTHROPIC_API_KEY:
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text.strip()
    except Exception as e:
        print(f"  [Claude API] Erreur : {e}")
        return ""


def generate_entry_with_claude(titre: str, url: str, source_nom: str,
                                rss_description: str, article_text: str) -> dict:
    """
    Appelle Claude avec le contenu de l'article pour générer :
    - un corps de 4-6 phrases factuel et analytique
    - la catégorie la plus pertinente
    - un titre reformulé en français si nécessaire
    """
    # Contexte disponible pour Claude
    context_parts = []
    if rss_description:
        context_parts.append(f"Résumé RSS : {rss_description[:500]}")
    if article_text:
        context_parts.append(f"Extrait de l'article :\n{article_text[:2000]}")
    context = "\n\n".join(context_parts) or "(aucun contenu disponible)"

    prompt = f"""Tu analyses un article pour une newsletter IA destinée à des experts (directeurs, product managers, ingénieurs seniors).

Titre original : {titre}
Source : {source_nom} ({url})

{context}

Réponds UNIQUEMENT avec un objet JSON (pas de markdown, pas d'explication) avec ces 3 champs :

{{
  "titre_fr": "titre en français, reformulé si nécessaire, factuel et précis (max 90 caractères)",
  "body": "corps de 4 à 6 phrases. Ton direct, factuel, analytique. Commence par un fait concret ou chiffre. Inclut l'impact business/technique/réglementaire. Termine par une implication concrète pour les équipes.",
  "categorie": "une des valeurs : societal | economie | fonctionnel | use_cases | fun_facts"
}}

Définition des catégories (choisir la plus représentative) :
- societal    : réglementation, éthique, politique publique, vie privée, biais, gouvernance de l'IA
- economie    : financement, investissement, acquisition, emploi, marché, valorisation, IPO
- fonctionnel : vie des modèles et outils — sorties de modèles, benchmarks, APIs, architectures, recherche technique, fine-tuning, open source
- use_cases   : applications concrètes déployées en entreprise — retours d'expérience réels, adoption sectorielle (santé, legal, retail…), gains de productivité mesurés. PAS les simples annonces produit.
- fun_facts   : l'inattendu — fait surprenant, record, première mondiale, découverte contre-intuitive, chiffre insolite, application décalée ou anecdote remarquable. Si le contenu provoque un "wow, je ne savais pas ça", c'est fun_facts.

Règles :
- titre_fr : si le titre est déjà en français et bon, garde-le tel quel
- body : basé uniquement sur les faits présents dans l'article, sans invention
- En cas de doute entre fonctionnel et use_cases : fonctionnel si l'article parle du modèle/outil lui-même, use_cases si l'article parle d'un déploiement réel chez des utilisateurs"""

    result = call_claude(prompt, max_tokens=600)
    if not result:
        return {}

    # Parser le JSON retourné
    try:
        # Chercher un bloc JSON dans la réponse
        json_match = re.search(r'\{.*\}', result, re.S)
        if json_match:
            data = json.loads(json_match.group())
            return data
    except (json.JSONDecodeError, AttributeError):
        pass
    return {}


# ─── SCORING ─────────────────────────────────────────────────────────────────

def compute_ai_score(titre: str, description: str = "") -> int:
    """Score de pertinence IA basé sur les mots-clés."""
    text = (titre + " " + description).lower()
    score = 0
    for kw in AI_KEYWORDS_HIGH:
        if kw in text:
            score += 20
            break
    for kw in AI_KEYWORDS_MED:
        if kw in text:
            score += 8
            break
    return min(score, 30)


def compute_freshness_score(published_dt: datetime | None) -> int:
    """Score de fraîcheur : 30 pts pour <6h, dégressif jusqu'à 0 à 48h."""
    if not published_dt:
        return 5  # Score minimal si date inconnue
    now = datetime.now(timezone.utc)
    if published_dt.tzinfo is None:
        published_dt = published_dt.replace(tzinfo=timezone.utc)
    age_hours = (now - published_dt).total_seconds() / 3600
    if age_hours < 6:
        return 30
    elif age_hours < 12:
        return 22
    elif age_hours < 24:
        return 15
    elif age_hours < 36:
        return 8
    else:
        return 2


def key_terms(titre: str) -> set[str]:
    """Extrait les termes significatifs d'un titre pour la déduplication."""
    words = re.findall(r"[a-zA-ZÀ-ÿ]{4,}", titre.lower())
    return {w for w in words if w not in STOP_WORDS}


def boost_multi_source(items: list[dict]) -> list[dict]:
    """
    Détecte les articles traitant du même sujet (>= 2 termes en commun).
    Booste le score du premier et marque les doublons.
    """
    boosted: set[int] = set()
    for i, item in enumerate(items):
        terms_i = key_terms(item["titre"])
        if not terms_i:
            continue
        same_topic_sources: list[str] = []
        for j, other in enumerate(items):
            if i == j:
                continue
            if len(terms_i & key_terms(other["titre"])) >= 2:
                same_topic_sources.append(other["_source_nom"])
                other["_duplicate"] = True

        if same_topic_sources and i not in boosted:
            item["score"] = item.get("score", 50) + 25
            # Fusionner les sources pour l'article représentant
            existing_urls = {s["url"] for s in item.get("sources", [])}
            for src_nom in same_topic_sources:
                # Trouver l'URL de cette source dans les items doublons
                for other in items:
                    if other.get("_source_nom") == src_nom and other.get("_duplicate"):
                        for s in other.get("sources", []):
                            if s["url"] not in existing_urls:
                                item.setdefault("sources", []).append(s)
                                existing_urls.add(s["url"])
            boosted.add(i)

    return [x for x in items if not x.get("_duplicate")]


def merge_with_existing_backlog(fresh_items: list[dict], backlog: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Pour chaque article frais couvrant le même sujet qu'un item du backlog existant
    (≥2 termes en commun dans le titre), fusionne les sources et booste le score
    de l'item backlog (+15) au lieu d'ajouter un doublon.
    Retourne (items_non_fusionnés, backlog_mis_à_jour).
    """
    backlog_copy = [dict(item) for item in backlog]
    remaining = []
    merged_count = 0

    for fresh in fresh_items:
        terms_f = key_terms(fresh["titre"])
        if not terms_f:
            remaining.append(fresh)
            continue

        fused = False
        for bl in backlog_copy:
            if len(terms_f & key_terms(bl.get("titre", ""))) >= 2:
                # Fusionner les sources
                existing_urls = {s["url"] for s in bl.get("sources", [])}
                for s in fresh.get("sources", []):
                    if s["url"] not in existing_urls:
                        bl.setdefault("sources", []).append(s)
                        existing_urls.add(s["url"])
                # Booster le score (signal multi-source inter-run)
                bl["score"] = round(bl.get("score", 0) + 15, 1)
                fused = True
                merged_count += 1
                break

        if not fused:
            remaining.append(fresh)

    if merged_count:
        print(f"[fetch_backlog] {merged_count} articles frais fusionnés dans des items backlog existants")

    return remaining, backlog_copy


# ─── RSS FETCH ────────────────────────────────────────────────────────────────

def parse_date(entry) -> datetime | None:
    """Extrait la date de publication d'une entrée feedparser."""
    for attr in ("published_parsed", "updated_parsed"):
        t = getattr(entry, attr, None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def is_ai_relevant(titre: str, description: str, filtre_ia: bool) -> bool:
    """Retourne True si l'article est pertinent pour une newsletter IA."""
    if not filtre_ia:
        return True
    text = (titre + " " + description).lower()
    return any(kw in text for kw in AI_KEYWORDS_HIGH + AI_KEYWORDS_MED)


def fetch_feed(source: dict, window_hours: int) -> list[dict]:
    """
    Fetche un flux RSS et retourne les items pertinents sous forme normalisée.
    Si le flux est vide ou inaccessible, tente un fallback via Tavily.
    """
    if not HAS_FEEDPARSER:
        return []

    url       = source["url"]
    nom       = source["nom"]
    fiabilite = source.get("fiabilite", 70)
    filtre_ia = source.get("filtre_ia", True)
    is_relay  = source.get("relay", False)   # True = influenceur / newsletter relais

    print(f"  [RSS] {nom}…", end=" ", flush=True)
    rss_ok = False
    items  = []

    try:
        feed   = feedparser.parse(url, agent=USER_AGENT,
                                  request_headers={"Accept": "application/rss+xml, application/xml"})
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)

        for entry in feed.entries:
            titre       = getattr(entry, "title", "").strip()
            link        = getattr(entry, "link",  "").strip()
            description = getattr(entry, "summary", "") or getattr(entry, "description", "")
            description = clean_html(description)[:300]

            if not titre or not link:
                continue

            # Plateformes non-textuelles (sauf YouTube configuré explicitement)
            if is_non_source_platform(link) and not is_youtube_url(link):
                continue
            # Pages d'accueil ou catégories génériques
            if is_homepage_or_generic(link, titre):
                continue

            published = parse_date(entry)
            if published and published < cutoff:
                continue

            if not is_ai_relevant(titre, description, filtre_ia):
                continue

            # Sources relais : rejeter tout article dont le titre mentionne la source elle-même
            if is_relay and is_relay_self_ref(titre, nom):
                print(f"\n    [relay-filter] ignoré (auto-référence) : {titre[:60]}", end="")
                continue

            freshness = compute_freshness_score(published)
            ai_bonus  = compute_ai_score(titre, description)
            score     = round(freshness + ai_bonus + (fiabilite / 100) * 20, 1)
            cat       = detect_category(titre, description)

            items.append({
                "titre":        titre,
                "url":          link,
                "categorie":    cat,
                "label":        LABEL_MAP.get(cat, "Fonctionnel"),
                "sources":      [{"nom": nom, "url": link}],
                "score":        score,
                "body":         "",
                "_source_nom":  nom,
                "_published":   published.isoformat() if published else None,
                "_description": description,
                "_content":     "",
                "_duplicate":   False,
            })

        rss_ok = len(items) > 0

    except Exception as e:
        print(f"Erreur RSS ({e})", end=" ")

    print(f"{len(items)} articles", end="")

    # ── Fallback Tavily si le flux RSS est vide ou inaccessible ──
    if not rss_ok and HAS_TAVILY and TAVILY_API_KEY:
        print(f" → fallback Tavily…", end=" ", flush=True)
        # Recherche par nom de la source sur les dernières 48h
        domain = url.split("/")[2] if url.startswith("http") else nom
        query  = f'site:{domain} artificial intelligence OR "intelligence artificielle"'
        tavily_results = tavily_search(query, days=2, max_results=5)
        fallback_items = tavily_items_to_backlog(tavily_results, nom, fiabilite, window_hours)
        items.extend(fallback_items)
        print(f"+{len(fallback_items)} via Tavily", end="")

    print()
    return items


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def known_urls_and_titles(backlog: list, historique: list, history_days: int = 7) -> tuple[set, set, list]:
    """
    Retourne :
    - urls   : ensemble des URLs déjà dans le backlog
    - titles : ensemble des titres exacts (backlog + historique récent)
    - topic_sets : liste de frozenset(mots-clés) des titres publiés dans les
                   history_days derniers jours — pour la déduplication thématique
    """
    urls: set[str] = set()
    titles: set[str] = set()
    topic_sets: list[frozenset] = []

    for item in backlog:
        urls.add(item.get("url", ""))
        titles.add(item.get("titre", "").lower())

    for row in historique[:history_days]:
        for t in row.get("titres", []):
            titles.add(t.lower())
            terms = key_terms(t)
            if len(terms) >= 2:
                topic_sets.append(frozenset(terms))

    return urls, titles, topic_sets


def is_topic_already_covered(titre: str, topic_sets: list, threshold: int = 4) -> bool:
    """
    Retourne True si le sujet de l'article chevauche fortement (≥ threshold termes)
    un titre déjà publié dans l'historique récent.
    """
    terms = key_terms(titre)
    if len(terms) < 2:
        return False
    return any(len(terms & hist) >= threshold for hist in topic_sets)


def load_acteurs_sources() -> list[dict]:
    """
    Charge les acteurs IA primaires depuis sources.json (sources_acteurs_ia).
    Pas de filtre auto-référence — leurs propres annonces sont la news.
    Compatible avec l'ancienne clé 'sources_primaires' pour la rétrocompatibilité.
    """
    data = load_json(SOURCES_JSON, {})
    # Nouvelle clé v2 → ancienne clé v1 en fallback
    return data.get("sources_acteurs_ia") or data.get("sources_primaires", [])


def load_relais_sources() -> tuple[list[dict], list[dict]]:
    """
    Charge toutes les sources relais depuis sources.json (sources_relais).
    Retourne (rss_relais, search_relais) — routage selon le champ 'fetch'.
    Le filtre auto-référence est actif sur TOUS les relais sans exception.
    Sources relais :
      - médias     (fetch='rss')   → fetchés via RSS / Tavily fallback
      - influenceurs (fetch='search') → recherche Tavily
    """
    data = load_json(SOURCES_JSON, {})
    relais = data.get("sources_relais", [])

    rss_relais    = [r for r in relais if r.get("fetch") == "rss"]
    search_relais = [r for r in relais if r.get("fetch") == "search"
                     or (r.get("fetch") != "rss" and r.get("recherche_web", "").strip())]
    return rss_relais, search_relais


# Alias de compatibilité pour le code qui appelait load_primaires_sources()
def load_primaires_sources() -> list[dict]:
    return load_acteurs_sources()


def load_youtube_channels() -> list[dict]:
    """
    Charge les chaînes YouTube depuis sources.json (section sources_youtube).
    Chaque entrée contient au minimum : nom + handle (ex: @anthropic-ai) ou url.
    """
    data = load_json(SOURCES_JSON, {})
    return data.get("sources_youtube", [])


def resolve_youtube_channel(handle_or_url: str) -> str | None:
    """
    Résout un handle YouTube (@channelname), un nom ou une URL de chaîne
    en URL de flux RSS (https://www.youtube.com/feeds/videos.xml?channel_id=...).
    Fetche la page de la chaîne et extrait le channelId depuis le HTML.
    """
    raw = handle_or_url.strip()

    # Normaliser en URL complète
    if raw.startswith("http"):
        url = raw
    elif raw.startswith("@"):
        url = f"https://www.youtube.com/{raw}"
    else:
        url = f"https://www.youtube.com/@{raw}"

    html = http_get(url, timeout=10)
    if not html:
        return None

    # Le channelId est présent plusieurs fois dans le HTML de la page
    for pattern in (
        r'"channelId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"',
        r'channel_id=(UC[A-Za-z0-9_-]{22})',
        r'"externalId"\s*:\s*"(UC[A-Za-z0-9_-]{22})"',
    ):
        m = re.search(pattern, html)
        if m:
            channel_id = m.group(1)
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    return None


def fetch_youtube_channel(channel: dict, window_hours: int) -> list[dict]:
    """
    Fetche les vidéos d'une chaîne YouTube configurée dans sources_youtube.
    Résout le channelId au premier appel, utilise le flux RSS, extrait les transcripts.
    """
    nom    = channel.get("nom", "YouTube")
    handle = channel.get("handle") or channel.get("url", "")
    if not handle:
        return []

    print(f"  [YouTube] {nom} ({handle})…", end=" ", flush=True)

    rss_url = resolve_youtube_channel(handle)
    if not rss_url:
        print("impossible de résoudre la chaîne")
        return []

    fiabilite = channel.get("fiabilite", 65)
    feed_source = {
        "nom": nom,
        "url": rss_url,
        "fiabilite": fiabilite,
        "filtre_ia": channel.get("filtre_ia", False),  # On fait confiance aux chaînes IA configurées
    }
    return fetch_feed(feed_source, window_hours)


# Patterns RSS courants à tester quand l'URL d'une source primaire n'est pas
# directement dans sources_rss.json
RSS_PATTERNS = [
    "/feed",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/rss/",
    "/blog/feed",
    "/blog/rss.xml",
    "/news/rss",
    "/index.xml",
    "/atom.xml",
]


def find_rss_for_url(site_url: str, known_rss_feeds: list[dict]) -> str | None:
    """
    Cherche l'URL RSS pour un site :
    1. Si le domaine correspond à un flux déjà dans sources_rss.json → retourne son URL RSS
    2. Sinon teste les patterns RSS courants sur le domaine
    3. Retourne None si aucun flux trouvé
    """
    # Extraire le domaine de l'URL du site
    try:
        domain = site_url.split("//")[1].split("/")[0]  # ex: openai.com
    except IndexError:
        return None

    # 1. Chercher dans les flux RSS déjà configurés
    for feed in known_rss_feeds:
        feed_url = feed.get("url", "")
        if domain in feed_url:
            return feed_url  # flux déjà configuré, pas besoin d'en créer un

    # 2. Tester les patterns RSS courants
    # Utiliser le début de l'URL du site (sans le path spécifique)
    base = site_url.rstrip("/")
    # Garder seulement le domaine + éventuel préfixe de section
    # ex: https://techcrunch.com/category/ai/ → https://techcrunch.com
    base_domain = f"{site_url.split('//')[0]}//{domain}"

    for pattern in RSS_PATTERNS:
        rss_url = base_domain + pattern
        html = http_get(rss_url, timeout=5)
        if html and ("<rss" in html[:500] or "<feed" in html[:500] or "<?xml" in html[:200]):
            print(f"    → RSS trouvé : {rss_url}")
            return rss_url

    return None


def fetch_primaire(source: dict, known_rss_feeds: list[dict],
                   window_hours: int) -> list[dict]:
    """
    Fetche une source primaire :
    - Cherche d'abord un flux RSS (configuré ou découvert automatiquement)
    - Fallback Tavily site:domain si pas de RSS
    """
    nom       = source.get("nom", "Source")
    url       = source.get("url", "")
    fiabilite = round(source.get("score_global", 3.0) * 20)  # 0-5 → 0-100
    is_relay  = source.get("relay", False)  # médias = relay:true, acteurs IA = false

    if not url:
        return []

    print(f"  [Primaire] {nom}…", end=" ", flush=True)

    # 1. Essayer RSS
    rss_url = find_rss_for_url(url, known_rss_feeds)
    if rss_url:
        feed_source = {
            "nom": nom,
            "url": rss_url,
            "fiabilite": fiabilite,
            "filtre_ia": source.get("type") not in ("blog_officiel",),
            "relay": is_relay,
        }
        items = fetch_feed(feed_source, window_hours)
        if items:
            return items

    # 2. Fallback Tavily site:domain
    if HAS_TAVILY and TAVILY_API_KEY:
        try:
            domain = url.split("//")[1].split("/")[0]
        except IndexError:
            domain = url
        query   = f'site:{domain} artificial intelligence OR "intelligence artificielle"'
        results = tavily_search(query, days=2, max_results=5)
        items   = tavily_items_to_backlog(results, nom, fiabilite, window_hours)
        print(f"{len(items)} articles (Tavily)")
        return items

    print("0 articles")
    return []


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", default="briefing-ia", help="Slug de la newsletter (ex: briefing-ia)")
    args = parser.parse_args()
    _init_paths(args.slug)
    print(f"[fetch_backlog] Newsletter : {args.slug}")

    if not HAS_FEEDPARSER:
        raise SystemExit("feedparser requis : pip install feedparser")

    rss_config   = load_json(SOURCES_RSS_JSON, {})
    rss_feeds    = rss_config.get("feeds", [])
    window_hours = rss_config.get("window_heures", 48)
    max_corps    = rss_config.get("max_articles_corps", 20)

    # ── Calcul dynamique du max_backlog ───────────────────────────────────────
    # On lit nb_news_principal, decay et score_minimum depuis config.json,
    # puis on estime combien de jours un article survit avant de passer sous
    # le seuil. Le backlog doit contenir au moins autant d'articles.
    cfg       = load_json(CONFIG_JSON, {})
    nb_main   = int(cfg.get("contenu", {}).get("nb_news_principal", 6))
    decay_pct = cfg.get("scoring", {}).get("decroissance_quotidienne_pct", 15)
    min_s     = cfg.get("scoring", {}).get("score_minimum_backlog", 10)
    # Garde-fous : valeurs extrêmes inutilisables
    decay_pct = max(3.0, min(40.0, float(decay_pct)))   # entre 3 % et 40 %/jour
    min_s     = max(5,   min(30,   int(min_s)))          # entre 5 et 30
    decay     = decay_pct / 100
    avg_score = 50   # score moyen observé d'un article entrant (heuristique)
    # Durée de survie = nb de jours pour passer de avg_score à min_s
    survival_days = math.log(min_s / avg_score) / math.log(1 - decay)
    survival_days = max(3.0, min(30.0, survival_days))
    computed_max  = int(nb_main * survival_days * 1.5)
    max_backlog   = max(50, min(300, computed_max))
    # Permettre un override manuel dans sources_rss.json (optionnel)
    manual_max = rss_config.get("max_articles_backlog")
    if manual_max:
        max_backlog = int(manual_max)
        print(f"[fetch_backlog] max_backlog = {max_backlog} (override manuel sources_rss.json)")
    else:
        print(f"[fetch_backlog] max_backlog = {max_backlog} "
              f"({nb_main} articles/j × {survival_days:.1f}j survie estimée "
              f"à {decay_pct:.0f}%/j, seuil {min_s})")
    # ─────────────────────────────────────────────────────────────────────────

    # Sources depuis l'UI (sources.json) — priorité sur sources_rss.json
    acteurs_ui       = load_acteurs_sources()
    rss_relais_ui, search_relais_ui = load_relais_sources()
    youtube_channels = load_youtube_channels()

    # Fallback : si sources.json v2 non disponible, utiliser sources_rss.json
    has_ui_sources = bool(acteurs_ui or rss_relais_ui or search_relais_ui)
    search_fallback = rss_config.get("search_sources", [])
    search_sources  = search_relais_ui if search_relais_ui else search_fallback

    backlog    = load_json(BACKLOG_JSON, [])
    historique = load_json(HISTORIQUE_JSON, [])
    known_urls, known_titles, hist_topic_sets = known_urls_and_titles(backlog, historique)

    if ANTHROPIC_API_KEY:
        print("[fetch_backlog] API Claude disponible — génération des corps activée")
    else:
        print("[fetch_backlog] ANTHROPIC_API_KEY absente — corps générés sans IA")

    if TAVILY_API_KEY and HAS_TAVILY:
        n_search = len(search_sources)
        src_label = "sources.json (UI)" if search_relais_ui else "sources_rss.json (fallback)"
        print(f"[fetch_backlog] Tavily disponible — {n_search} sources search depuis {src_label}")
    else:
        print("[fetch_backlog] TAVILY_API_KEY absente — sources search désactivées")

    all_items: list[dict] = []

    # 1a. Acteurs IA (sources_acteurs_ia) — PAS de filtre auto-référence
    if acteurs_ui:
        print(f"\n[fetch_backlog] {len(acteurs_ui)} acteurs IA depuis sources.json…")
        for source in acteurs_ui:
            items = fetch_primaire(source, rss_feeds, window_hours)
            all_items.extend(items)
    else:
        # 1b. Fallback : flux RSS configurés statiquement dans sources_rss.json
        print(f"\n[fetch_backlog] Récupération de {len(rss_feeds)} flux RSS (fenêtre {window_hours}h)…")
        for source in rss_feeds:
            items = fetch_feed(source, window_hours)
            all_items.extend(items)

    # 1c. Relais RSS (médias, newsletters) — filtre auto-référence ACTIF
    if rss_relais_ui:
        print(f"\n[fetch_backlog] {len(rss_relais_ui)} sources relais RSS depuis sources.json…")
        for source in rss_relais_ui:
            # Forcer relay=True — tous les relais RSS sont soumis au filtre
            source_with_relay = {**source, "relay": True}
            items = fetch_primaire(source_with_relay, rss_feeds, window_hours)
            all_items.extend(items)

    # 1d. Chaînes YouTube configurées dans sources.json
    if youtube_channels:
        print(f"\n[fetch_backlog] {len(youtube_channels)} chaîne(s) YouTube configurée(s)…")
        for channel in youtube_channels:
            items = fetch_youtube_channel(channel, window_hours)
            all_items.extend(items)

    # 2. Sources relais search (influenceurs, personnalités) via Tavily — filtre auto-référence ACTIF
    if search_sources and HAS_TAVILY and TAVILY_API_KEY:
        print(f"\n[fetch_backlog] Recherche Tavily pour {len(search_sources)} sources relais…")
        for source in search_sources:
            nom       = source.get("nom", "Relais")
            query     = source.get("recherche_web") or source.get("query", "")
            fiabilite = source.get("score_relais") or source.get("fiabilite", 3)
            # Normaliser score_relais (1-5) en score (0-100)
            if isinstance(fiabilite, (int, float)) and fiabilite <= 5:
                fiabilite = int(fiabilite * 20)

            items: list[dict] = []

            if query:
                print(f"  [Relais] {nom}…", end=" ", flush=True)
                results = tavily_search(query, days=2, max_results=5)
                items   = tavily_items_to_backlog(results, nom, fiabilite, window_hours)
                # Tous les relais search : filtre auto-référence systématique
                before = len(items)
                items = [
                    it for it in items
                    if not is_relay_self_ref(it.get("titre", ""), nom)
                ]
                if len(items) < before:
                    print(f" ({before - len(items)} auto-référence(s) filtrée(s))", end="")
                print(f"{len(items)} articles", end="")

            # Fallback YouTube si Tavily ne trouve rien et que la source a un champ youtube
            yt_handle = source.get("youtube", "").strip()
            if not items and yt_handle:
                print(f" → fallback YouTube ({yt_handle})…", end=" ", flush=True)
                yt_channel = {"nom": nom, "handle": yt_handle, "fiabilite": fiabilite}
                yt_items = fetch_youtube_channel(yt_channel, window_hours)
                items.extend(yt_items)
                print(f"+{len(yt_items)} via YouTube", end="")

            if not query and not source.get("youtube"):
                print(f"  [Relais] {nom}… ignoré (pas de query ni de youtube)")
            else:
                print()

            all_items.extend(items)

    print(f"\n[fetch_backlog] {len(all_items)} articles bruts collectés")

    # 2. Filtrer les doublons connus (URL exacte + titre exact)
    fresh_items = [
        x for x in all_items
        if x["url"] not in known_urls
        and x["titre"].lower() not in known_titles
    ]
    print(f"[fetch_backlog] {len(fresh_items)} articles après déduplication exacte (URL/titre)")

    # 2b. Filtrer les sujets déjà couverts dans l'historique récent (≥4 termes communs)
    before = len(fresh_items)
    fresh_items = [
        x for x in fresh_items
        if not is_topic_already_covered(x["titre"], hist_topic_sets, threshold=4)
    ]
    skipped = before - len(fresh_items)
    if skipped:
        print(f"[fetch_backlog] {skipped} article(s) écartés car sujet déjà couvert récemment")
    print(f"[fetch_backlog] {len(fresh_items)} articles nouveaux (après déduplication thématique)")

    # 3. Détecter les articles multi-sources (même run) et booster leur score
    fresh_items = boost_multi_source(fresh_items)
    print(f"[fetch_backlog] {len(fresh_items)} articles après fusion multi-sources (même run)")

    # 3b. Fusionner avec le backlog existant (sujets identiques, runs différents)
    fresh_items, backlog = merge_with_existing_backlog(fresh_items, backlog)
    print(f"[fetch_backlog] {len(fresh_items)} articles vraiment nouveaux après fusion inter-runs")

    # 4. Trier par score, garder les meilleurs
    fresh_items.sort(key=lambda x: x.get("score", 0), reverse=True)
    fresh_items = fresh_items[:max_backlog]

    # 5. Générer les corps via Claude (top max_corps articles)
    if ANTHROPIC_API_KEY:
        print(f"\n[fetch_backlog] Génération des corps via Claude pour les {min(max_corps, len(fresh_items))} meilleurs articles…")
        for i, item in enumerate(fresh_items[:max_corps]):
            print(f"  [{i+1}/{min(max_corps, len(fresh_items))}] {item['titre'][:60]}")
            # Utiliser l'extrait Tavily s'il existe, sinon fetcher le HTML
            article_text = item.get("_content", "")
            if not article_text:
                article_text = fetch_article_text(item["url"])
                time.sleep(0.3)  # politesse réseau

            # Appel Claude
            claude_data = generate_entry_with_claude(
                titre=item["titre"],
                url=item["url"],
                source_nom=item["_source_nom"],
                rss_description=item.get("_description", ""),
                article_text=article_text,
            )

            if claude_data:
                if claude_data.get("titre_fr"):
                    item["titre"] = claude_data["titre_fr"]
                if claude_data.get("body"):
                    item["body"] = claude_data["body"]
                if claude_data.get("categorie") in LABEL_MAP:
                    item["categorie"] = claude_data["categorie"]
                    item["label"] = LABEL_MAP[item["categorie"]]

            time.sleep(0.5)  # pause entre appels API

    # 6. Nettoyer les champs internes avant écriture
    for item in fresh_items:
        item.pop("_source_nom", None)
        item.pop("_published", None)
        item.pop("_description", None)
        item.pop("_content", None)
        item.pop("_duplicate", None)

    # 7. Fusionner avec le backlog existant
    existing_urls = {x.get("url") for x in backlog}
    new_items = [x for x in fresh_items if x["url"] not in existing_urls]
    merged = new_items + backlog
    merged.sort(key=lambda x: x.get("score", 0), reverse=True)
    merged = merged[:max_backlog]

    with open(BACKLOG_JSON, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"\n[fetch_backlog] ✅ {len(new_items)} nouveaux articles ajoutés — backlog total : {len(merged)} articles")


if __name__ == "__main__":
    main()
