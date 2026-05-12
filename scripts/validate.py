#!/usr/bin/env python3
"""
validate.py — Validation complète de la plateforme newsletter.

Usage :
  python scripts/validate.py                    # toutes les NL actives
  python scripts/validate.py --slug mode-luxe   # une seule NL
  python scripts/validate.py --all              # y compris status=test
  python scripts/validate.py --strict           # exit 1 si au moins un WARNING

Codes de sortie :
  0  tout OK
  1  au moins un ERREUR
  2  au moins un WARNING (uniquement avec --strict)
"""

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).parent.parent
NEWSLETTERS_DIR = ROOT / "newsletters"

# ─── Couleurs terminal ─────────────────────────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}✅ {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}⚠️  {msg}{RESET}")
def err(msg):  print(f"  {RED}❌ {msg}{RESET}")
def info(msg): print(f"  {BLUE}ℹ  {msg}{RESET}")

# ─── Helpers ───────────────────────────────────────────────────────────────────
def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"Fichier introuvable : {path.relative_to(ROOT)}"
    except json.JSONDecodeError as e:
        return None, f"JSON invalide dans {path.relative_to(ROOT)} : {e}"

def extract_js_var(text, var_name):
    """Extrait la valeur d'une const JS (objet, tableau ou chaîne) depuis du texte."""
    # Gère : const FOO = {...}; ou const FOO={...};
    pattern = rf"const {var_name}\s*=\s*('([^']*)'|\"([^\"]*)\"|(\{{.*?\}})|(\[.*?\])|\{{.*?\}});"
    m = re.search(pattern, text, re.S)
    if not m:
        return None, f"const {var_name} introuvable"
    raw = m.group(1)
    if raw.startswith("'") or raw.startswith('"'):
        return raw.strip("'\""), None
    try:
        return json.loads(raw), None
    except json.JSONDecodeError as e:
        return None, f"const {var_name} JSON invalide : {e}"

def is_valid_url(url):
    try:
        r = urlparse(url)
        return r.scheme in ("http", "https") and bool(r.netloc)
    except Exception:
        return False

def is_recent_date(date_str, max_days=3):
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return abs((datetime.utcnow() - dt).days) <= max_days
    except Exception:
        return False

# ─── Résultats ─────────────────────────────────────────────────────────────────
errors = []
warnings = []

def E(slug, msg):
    errors.append(f"[{slug}] {msg}")
    err(msg)

def W(slug, msg):
    warnings.append(f"[{slug}] {msg}")
    warn(msg)

def OK(msg):
    ok(msg)

# ══════════════════════════════════════════════════════════════════════════════
# BLOC 1 — Structure plateforme (index.json, admin.html, app.js)
# ══════════════════════════════════════════════════════════════════════════════
def validate_platform():
    print(f"\n{BOLD}── Plateforme ───────────────────────────────────────────{RESET}")

    # index.json
    idx, e = load_json(NEWSLETTERS_DIR / "index.json")
    if e:
        E("platform", e); return []
    OK("index.json valide")

    slugs_in_index = [n["slug"] for n in idx.get("newsletters", [])]
    active_slugs   = [n["slug"] for n in idx.get("newsletters", []) if n.get("status") == "active"]

    # Doublons dans index.json
    if len(slugs_in_index) != len(set(slugs_in_index)):
        E("platform", "Slugs dupliqués dans index.json")
    else:
        OK(f"index.json — {len(slugs_in_index)} NL ({len(active_slugs)} actives)")

    # Répertoires présents pour chaque slug
    for slug in slugs_in_index:
        d = NEWSLETTERS_DIR / slug
        if not d.is_dir():
            E("platform", f"Répertoire manquant pour slug '{slug}'")
        else:
            OK(f"Répertoire newsletters/{slug}/ présent")

    # Répertoires orphelins (présents mais absents de index.json)
    for d in NEWSLETTERS_DIR.iterdir():
        if d.is_dir() and not d.name.startswith("_") and d.name not in slugs_in_index:
            W("platform", f"Répertoire '{d.name}' présent mais absent de index.json")

    # admin.html
    admin = NEWSLETTERS_DIR / "admin.html"
    if not admin.exists():
        E("platform", "admin.html introuvable")
    else:
        content = admin.read_text(encoding="utf-8")
        for token in ["ADMIN_SLUG", "loadSourcesAdmin", "switchNewsletter", "loadBacklogAdmin"]:
            if token not in content:
                W("platform", f"admin.html : token '{token}' absent (régression possible)")
        OK("admin.html présent et tokens clés détectés")

    # app.js partagé
    app = NEWSLETTERS_DIR / "app.js"
    if not app.exists():
        E("platform", "app.js partagé introuvable")
    else:
        content = app.read_text(encoding="utf-8")
        for fn in ["showTab", "openNewsletter", "closeNewsletter", "renderSources",
                   "renderArchive", "pushSourcesToGitHub", "_pushRssSourcesToGitHub",
                   "deleteSource", "deleteRssSource", "confirmAddSource"]:
            if fn not in content:
                W("platform", f"app.js : fonction '{fn}' absente (régression possible)")
        for api in ["history.pushState", "history.replaceState", "popstate"]:
            if api not in content:
                W("platform", f"app.js : '{api}' absent — navigation back peut être cassée")
        OK("app.js partagé présent et fonctions clés détectées")

    return active_slugs

# ══════════════════════════════════════════════════════════════════════════════
# BLOC 2 — Config d'une newsletter
# ══════════════════════════════════════════════════════════════════════════════
def validate_config(slug, nl_dir):
    print(f"\n{BOLD}  [config.json]{RESET}")
    cfg, e = load_json(nl_dir / "config.json")
    if e:
        E(slug, e); return None

    required = ["slug", "name", "description", "status", "language", "contenu", "scoring"]
    for field in required:
        if field not in cfg:
            E(slug, f"config.json : champ '{field}' manquant")

    if cfg.get("slug") != slug:
        E(slug, f"config.json : slug '{cfg.get('slug')}' ≠ répertoire '{slug}'")
    else:
        OK(f"slug cohérent : {slug}")

    # Deux schémas coexistent : nouveau (categories top-level) / ancien (contenu.categories_actives)
    cats = cfg.get("categories", {})
    cats_legacy = cfg.get("contenu", {}).get("categories_actives", [])
    if cats:
        OK(f"{len(cats)} catégories définies : {', '.join(cats.keys())}")
    elif cats_legacy:
        info(f"Schéma legacy : {len(cats_legacy)} catégories dans contenu.categories_actives")
    else:
        W(slug, "config.json : aucune catégorie définie (ni 'categories' ni contenu.categories_actives)")

    contenu = cfg.get("contenu", {})
    for k in ["nb_news_principal", "nb_news_radar"]:
        if k not in contenu:
            W(slug, f"config.json : contenu.{k} manquant")

    return cfg

# ══════════════════════════════════════════════════════════════════════════════
# BLOC 3 — data.js
# ══════════════════════════════════════════════════════════════════════════════
def validate_data_js(slug, nl_dir, config):
    print(f"\n{BOLD}  [data.js]{RESET}")
    path = nl_dir / "data.js"
    if not path.exists():
        E(slug, "data.js introuvable"); return

    text = path.read_text(encoding="utf-8")

    # ── NEWSLETTER_SLUG ──
    slug_val, e = extract_js_var(text, "NEWSLETTER_SLUG")
    if e:
        E(slug, f"data.js : {e}")
    elif slug_val != slug:
        E(slug, f"data.js : NEWSLETTER_SLUG='{slug_val}' ≠ '{slug}'")
    else:
        OK(f"NEWSLETTER_SLUG = '{slug}'")

    # ── TODAY ──
    today, e = extract_js_var(text, "TODAY")
    if e:
        E(slug, f"data.js TODAY : {e}"); today = {}
    else:
        today_date = today.get("date", "")
        if not today_date:
            # Normal pour une NL fraîchement créée, pas encore générée
            W(slug, "data.js : TODAY vide — premier workflow pas encore lancé")
        elif not is_recent_date(today_date, max_days=3):
            W(slug, f"data.js : TODAY.date={today_date} — plus de 3 jours (workflow en retard ?)")
        else:
            OK(f"TODAY.date = {today_date}")

        if not today.get("chapeau"):
            W(slug, "data.js : TODAY.chapeau vide")
        else:
            OK(f"TODAY.chapeau présent ({len(today['chapeau'])} car.)")

        news = today.get("news", [])
        nb_expected = config.get("contenu", {}).get("nb_news_principal", 5) if config else 5
        if len(news) < nb_expected:
            W(slug, f"data.js : TODAY.news = {len(news)} articles (attendu ≥ {nb_expected})")
        else:
            OK(f"TODAY.news = {len(news)} articles")

        for i, art in enumerate(news):
            for field in ["id", "titre", "body", "categorie", "label"]:
                if not art.get(field):
                    E(slug, f"data.js : TODAY.news[{i}] champ '{field}' vide ou manquant")
            if art.get("body") and len(art["body"]) < 50:
                W(slug, f"data.js : TODAY.news[{i}].body très court ({len(art['body'])} car.)")
            if not art.get("sources"):
                W(slug, f"data.js : TODAY.news[{i}] aucune source")

    # ── ARCHIVE ──
    archive, e = extract_js_var(text, "ARCHIVE")
    is_fresh = not today or not today.get("date")  # NL jamais générée
    if e:
        E(slug, f"data.js ARCHIVE : {e}"); archive = []
    elif not archive:
        if is_fresh:
            info("ARCHIVE vide — normal avant le premier workflow")
        else:
            E(slug, "data.js : ARCHIVE est vide — le workflow ne met pas à jour les archives")
    else:
        OK(f"ARCHIVE = {len(archive)} édition(s)")
        latest = archive[0]
        if today and latest.get("date") != today.get("date"):
            W(slug, f"data.js : ARCHIVE[0].date={latest.get('date')} ≠ TODAY.date={today.get('date')}")
        for i, entry in enumerate(archive):
            for field in ["date", "date_longue", "fichier", "news"]:
                if not entry.get(field):
                    E(slug, f"data.js : ARCHIVE[{i}] champ '{field}' manquant")
            fichier = entry.get("fichier", "")
            if fichier:
                html_path = nl_dir / "newsletters" / fichier
                if not html_path.exists():
                    W(slug, f"data.js : ARCHIVE[{i}] fichier '{fichier}' absent du repo")
                else:
                    OK(f"ARCHIVE[{i}] ({entry.get('date')}) → {fichier} ✓")

    # ── ARCHIVE_FULL ──
    af, e = extract_js_var(text, "ARCHIVE_FULL")
    if e:
        E(slug, f"data.js ARCHIVE_FULL : {e}"); af = {}
    elif not af:
        E(slug, "data.js : ARCHIVE_FULL est vide — les résumés d'archives ne s'afficheront pas")
    else:
        OK(f"ARCHIVE_FULL = {len(af)} édition(s)")
        for date, content in af.items():
            articles = content.get("articles", [])
            if not articles:
                W(slug, f"data.js : ARCHIVE_FULL[{date}] aucun article")
                continue
            bodies_ok = sum(1 for a in articles if len(a.get("body", "")) > 50)
            if bodies_ok < len(articles):
                W(slug, f"data.js : ARCHIVE_FULL[{date}] — {len(articles)-bodies_ok}/{len(articles)} articles sans body")
            sources_ok = sum(1 for a in articles if a.get("sources"))
            if sources_ok < len(articles):
                W(slug, f"data.js : ARCHIVE_FULL[{date}] — {len(articles)-sources_ok}/{len(articles)} articles sans sources")
            else:
                OK(f"ARCHIVE_FULL[{date}] — {len(articles)} articles complets")

    # ── Cohérence CONFIG dans data.js ──
    js_config, e = extract_js_var(text, "CONFIG")
    if e:
        W(slug, f"data.js CONFIG : {e}")
    elif config and isinstance(js_config, dict):
        cfg_slug = js_config.get("slug")
        cfg_name = js_config.get("name")
        if cfg_slug and cfg_slug != config.get("slug"):
            W(slug, f"data.js CONFIG.slug='{cfg_slug}' ≠ config.json slug='{config.get('slug')}'")
        if cfg_name and cfg_name != config.get("name"):
            W(slug, f"data.js CONFIG.name='{cfg_name}' ≠ config.json name='{config.get('name')}'")
        if cfg_slug and cfg_name:
            OK(f"CONFIG cohérent entre data.js et config.json")

# ══════════════════════════════════════════════════════════════════════════════
# BLOC 4 — Sources
# ══════════════════════════════════════════════════════════════════════════════
def validate_sources(slug, nl_dir):
    print(f"\n{BOLD}  [sources]{RESET}")

    # sources_rss.json (nouveau format)
    rss, e = load_json(nl_dir / "sources_rss.json")
    if e:
        W(slug, f"sources_rss.json : {e}")
    else:
        feeds = rss.get("feeds", [])
        searches = rss.get("search_sources", [])

        if not feeds and not searches:
            W(slug, "sources_rss.json : aucun flux RSS ni recherche Tavily configuré")
        else:
            OK(f"sources_rss.json : {len(feeds)} flux RSS, {len(searches)} recherches Tavily")

        for i, feed in enumerate(feeds):
            if not feed.get("nom"):
                E(slug, f"sources_rss.json : feeds[{i}] champ 'nom' manquant")
            url = feed.get("url", "")
            if not url:
                E(slug, f"sources_rss.json : feeds[{i}] champ 'url' manquant")
            elif not is_valid_url(url):
                W(slug, f"sources_rss.json : feeds[{i}] URL invalide : {url}")
            if feed.get("fiabilite") is None:
                W(slug, f"sources_rss.json : feeds[{i}] champ 'fiabilite' manquant")
            elif not (0 <= feed["fiabilite"] <= 100):
                W(slug, f"sources_rss.json : feeds[{i}] fiabilite={feed['fiabilite']} hors plage [0-100]")

        for i, src in enumerate(searches):
            if not src.get("nom"):
                E(slug, f"sources_rss.json : search_sources[{i}] champ 'nom' manquant")
            if not src.get("query"):
                W(slug, f"sources_rss.json : search_sources[{i}] champ 'query' manquant")

    # sources.json (ancien format — briefing-ia ou héritage)
    src_path = nl_dir / "sources.json"
    if src_path.exists():
        src, e = load_json(src_path)
        if e:
            W(slug, f"sources.json : {e}")
        else:
            primaires = src.get("sources_primaires", [])
            relais = src.get("sources_relais", [])
            OK(f"sources.json : {len(primaires)} sources primaires, {len(relais)} sources relais")
            for i, s in enumerate(primaires):
                if not s.get("nom"):
                    E(slug, f"sources.json : sources_primaires[{i}] champ 'nom' manquant")
                if s.get("url") and not is_valid_url(s["url"]):
                    W(slug, f"sources.json : sources_primaires[{i}] URL invalide : {s['url']}")

# ══════════════════════════════════════════════════════════════════════════════
# BLOC 5 — Backlog & Historique
# ══════════════════════════════════════════════════════════════════════════════
def validate_backlog_historique(slug, nl_dir):
    print(f"\n{BOLD}  [backlog & historique]{RESET}")

    # backlog.json
    bl, e = load_json(nl_dir / "backlog.json")
    if e:
        E(slug, f"backlog.json : {e}")
    else:
        articles = bl if isinstance(bl, list) else []
        if not articles:
            W(slug, "backlog.json vide — le prochain workflow pourrait générer une édition vide")
        else:
            scored = [a for a in articles if a.get("score", 0) > 0]
            OK(f"backlog.json : {len(articles)} articles ({len(scored)} avec score > 0)")

    # historique.json
    hist, e = load_json(nl_dir / "historique.json")
    if e:
        E(slug, f"historique.json : {e}")
    else:
        nb = len(hist) if isinstance(hist, list) else 0
        OK(f"historique.json : {nb} entrée(s)")

# ══════════════════════════════════════════════════════════════════════════════
# BLOC 6 — Fichiers générés (HTML/MD)
# ══════════════════════════════════════════════════════════════════════════════
def validate_generated_files(slug, nl_dir):
    print(f"\n{BOLD}  [fichiers générés]{RESET}")
    nl_subdir = nl_dir / "newsletters"
    if not nl_subdir.exists():
        E(slug, "Répertoire newsletters/ absent"); return

    html_files = sorted(nl_subdir.glob("newsletter-*.html"), reverse=True)
    md_files   = sorted(nl_subdir.glob("newsletter-*.md"),   reverse=True)

    if not html_files:
        info("Aucun fichier généré — normal avant le premier workflow")
        return
    OK(f"{len(html_files)} fichiers HTML, {len(md_files)} fichiers MD")

    # Vérifier cohérence HTML ↔ MD
    html_dates = {f.stem.replace("newsletter-", "") for f in html_files}
    md_dates   = {f.stem.replace("newsletter-", "") for f in md_files}
    orphan_html = html_dates - md_dates
    orphan_md   = md_dates - html_dates
    if orphan_html:
        W(slug, f"HTML sans MD correspondant : {orphan_html}")
    if orphan_md:
        W(slug, f"MD sans HTML correspondant : {orphan_md}")
    if not orphan_html and not orphan_md:
        OK("HTML et MD cohérents (paires complètes)")

    # Dernière édition : vérifier que le MD est non vide et parseable
    latest_md = md_files[0] if md_files else None
    if latest_md:
        content = latest_md.read_text(encoding="utf-8")
        if len(content) < 200:
            W(slug, f"{latest_md.name} très court ({len(content)} car.) — génération incomplète ?")
        h2_count = len(re.findall(r"^## \d+\.", content, re.M))
        if h2_count == 0:
            W(slug, f"{latest_md.name} : aucun article H2 détecté (## N. Titre)")
        else:
            OK(f"{latest_md.name} : {h2_count} articles parsés")

# ══════════════════════════════════════════════════════════════════════════════
# BLOC 7 — index.html de la newsletter
# ══════════════════════════════════════════════════════════════════════════════
def validate_index_html(slug, nl_dir):
    print(f"\n{BOLD}  [index.html]{RESET}")
    path = nl_dir / "index.html"
    if not path.exists():
        E(slug, "index.html introuvable"); return

    content = path.read_text(encoding="utf-8")
    checks = [
        ("../app.js",          "référence à app.js partagé"),
        ("data.js",            "référence à data.js"),
        ("tab-today",          "onglet Today"),
        ("tab-archive",        "onglet Archive"),
        ("tab-sources",        "onglet Sources"),
        ("nl-overlay",         "overlay newsletter"),
        ("modal-sources",      "modal ajout source"),
    ]
    for token, label in checks:
        if token not in content:
            W(slug, f"index.html : '{token}' absent — {label} manquant")
    OK("index.html : tokens clés présents")

# ══════════════════════════════════════════════════════════════════════════════
# ENTRÉE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════
def validate_newsletter(slug, include_all=False):
    nl_dir = NEWSLETTERS_DIR / slug
    if not nl_dir.is_dir():
        print(f"{RED}❌ Répertoire introuvable : newsletters/{slug}{RESET}")
        return

    print(f"\n{'═'*60}")
    print(f"{BOLD}{BLUE}  Newsletter : {slug}{RESET}")
    print(f"{'═'*60}")

    config = validate_config(slug, nl_dir)
    validate_data_js(slug, nl_dir, config)
    validate_sources(slug, nl_dir)
    validate_backlog_historique(slug, nl_dir)
    validate_generated_files(slug, nl_dir)
    validate_index_html(slug, nl_dir)


def main():
    parser = argparse.ArgumentParser(description="Validation complète de la plateforme newsletter")
    parser.add_argument("--slug",   help="Valider une seule newsletter")
    parser.add_argument("--all",    action="store_true", help="Inclure les NL status=test")
    parser.add_argument("--strict", action="store_true", help="Exit 1 si au moins un WARNING")
    args = parser.parse_args()

    print(f"\n{BOLD}{'═'*60}")
    print(f"  VALIDATION PLATEFORME NEWSLETTER")
    print(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'═'*60}{RESET}")

    active_slugs = validate_platform()

    if args.slug:
        validate_newsletter(args.slug, include_all=args.all)
    else:
        idx, _ = load_json(NEWSLETTERS_DIR / "index.json")
        if idx:
            all_nls = idx.get("newsletters", [])
            targets = all_nls if args.all else [n for n in all_nls if n.get("status") == "active"]
            for nl in targets:
                validate_newsletter(nl["slug"], include_all=args.all)

    # ── Rapport final ──────────────────────────────────────────────────────────
    print(f"\n{'═'*60}")
    print(f"{BOLD}  RAPPORT FINAL{RESET}")
    print(f"{'═'*60}")
    if not errors and not warnings:
        print(f"\n{GREEN}{BOLD}  ✅ Tout est OK — aucune erreur, aucun warning{RESET}\n")
    else:
        if errors:
            print(f"\n{RED}{BOLD}  ❌ {len(errors)} ERREUR(S) :{RESET}")
            for e in errors:
                print(f"    {RED}• {e}{RESET}")
        if warnings:
            print(f"\n{YELLOW}{BOLD}  ⚠️  {len(warnings)} WARNING(S) :{RESET}")
            for w in warnings:
                print(f"    {YELLOW}• {w}{RESET}")

    print()
    if errors:
        sys.exit(1)
    if warnings and args.strict:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
