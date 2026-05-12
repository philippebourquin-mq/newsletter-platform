#!/usr/bin/env python3
"""
create_newsletter.py — Création complète d'une nouvelle newsletter.

Usage interactif (recommandé) :
  python scripts/create_newsletter.py

Usage CLI :
  python scripts/create_newsletter.py \
    --slug tech-retail \
    --name "Tech & Retail" \
    --description "Veille stratégique · Tech & Retail · Quotidienne" \
    --persona "Tu analyses l'actualité tech pour un directeur digital retail." \
    --categories "tendances:Tendances produit et UX,digital:E-commerce et IA retail,concurrence:Mouvements des enseignes" \
    --icon "🛒"

La commande crée le répertoire, tous les fichiers, met à jour index.json,
valide la structure, puis propose de committer.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT         = Path(__file__).parent.parent
NEWSLETTERS  = ROOT / "newsletters"
TEMPLATE_DIR = NEWSLETTERS / "_template"
INDEX_JSON   = NEWSLETTERS / "index.json"
VALIDATE_PY  = Path(__file__).parent / "validate.py"

# ─── Couleurs ─────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"; YELLOW = "\033[93m"; RED = "\033[91m"
BOLD   = "\033[1m";  RESET  = "\033[0m";  CYAN = "\033[96m"

def ok(m):   print(f"{GREEN}✅ {m}{RESET}")
def warn(m): print(f"{YELLOW}⚠️  {m}{RESET}")
def err(m):  print(f"{RED}❌ {m}{RESET}")
def ask(prompt, default=""):
    suffix = f" [{default}]" if default else ""
    val = input(f"{CYAN}→ {prompt}{suffix} : {RESET}").strip()
    return val or default

# ─── Validation du slug ────────────────────────────────────────────────────────
def validate_slug(slug):
    if not re.match(r'^[a-z][a-z0-9-]{1,30}$', slug):
        return "Le slug doit être en minuscules, sans espaces, avec des tirets (ex: tech-retail)"
    if (NEWSLETTERS / slug).exists():
        return f"Le répertoire newsletters/{slug}/ existe déjà"
    idx = json.loads(INDEX_JSON.read_text())
    if any(n["slug"] == slug for n in idx.get("newsletters", [])):
        return f"Le slug '{slug}' est déjà dans index.json"
    return None

# ─── Parsing des catégories ────────────────────────────────────────────────────
def parse_categories(raw):
    """
    Accepte deux formats :
      "tendances:Tendances produit,digital:E-commerce et IA"  → dict
      '{"tendances":"Tendances produit"}'                       → dict

    La virgule sépare les catégories uniquement quand elle est suivie
    d'un slug valide (mot-clé alphanumérique + tirets) puis de ':'.
    """
    raw = raw.strip()
    if raw.startswith("{"):
        return json.loads(raw)
    # Découper sur ",slug:" — le slug ne contient que [a-z0-9_-]
    parts = re.split(r',\s*(?=[a-z][a-z0-9_-]*:)', raw)
    cats = {}
    for part in parts:
        part = part.strip()
        if ":" in part:
            k, v = part.split(":", 1)
            cats[k.strip()] = v.strip()
        else:
            cats[part] = part.replace("_", " ").title()
    return cats

# ─── Génération du data.js ─────────────────────────────────────────────────────
def render_data_js(slug, name, config_dict):
    """Génère un data.js propre — sans espaces autour de = (compat regex workflow)."""
    config_json = json.dumps(config_dict, ensure_ascii=False, separators=(",", ":"))
    return f"""// ─── {name} — data.js ───────────────────────────────────────────────────────────
// Regénéré automatiquement. Ne pas modifier manuellement.

const NEWSLETTER_SLUG='{slug}';

// ─── DATA ─────────────────────────────────────────────────────────────────────
const TODAY={{}};
const ARCHIVE=[];
const ARCHIVE_FULL={{}};
const CONFIG={config_json};
"""

# ─── Génération du config.json ─────────────────────────────────────────────────
def render_config(slug, name, description, persona, categories, nb_principal=5, nb_radar=5):
    return {
        "slug": slug,
        "name": name,
        "description": description,
        "status": "active",
        "language": "fr",
        "persona": persona,
        "categories": categories,
        "contenu": {
            "nb_news_principal": nb_principal,
            "nb_news_radar": nb_radar
        },
        "scoring": {
            "poids": {
                "fraicheur": 30,
                "reprise_multi_sources": 25,
                "impact_sectoriel": 20,
                "originalite": 15,
                "engagement_potentiel": 10
            },
            "decroissance_quotidienne_pct": 15,
            "bonus_feedback_pts": 10,
            "score_minimum_backlog": 10
        }
    }

# ─── Génération du sources_rss.json ───────────────────────────────────────────
def render_sources_rss():
    return {
        "window_heures": 48,
        "max_articles_corps": 15,
        "feeds": [],
        "search_sources": []
    }

# ─── Patch de l'index.html template ───────────────────────────────────────────
def patch_index_html(template_text, name):
    return template_text.replace("{{NOM_NEWSLETTER}}", name)

# ─── Création des fichiers ─────────────────────────────────────────────────────
def create_newsletter_files(slug, name, description, persona, categories, icon):
    nl_dir = NEWSLETTERS / slug
    nl_dir.mkdir(parents=True, exist_ok=False)
    print(f"\n{BOLD}Création de newsletters/{slug}/{RESET}")

    config_dict = render_config(slug, name, description, persona, categories)

    # config.json
    (nl_dir / "config.json").write_text(
        json.dumps(config_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    ok("config.json")

    # data.js — format strict sans espaces (compat regex workflow)
    (nl_dir / "data.js").write_text(
        render_data_js(slug, name, config_dict), encoding="utf-8")
    ok("data.js (format strict, regex-compatible)")

    # sources_rss.json
    (nl_dir / "sources_rss.json").write_text(
        json.dumps(render_sources_rss(), ensure_ascii=False, indent=2), encoding="utf-8")
    ok("sources_rss.json")

    # sources.json (vide — ancien format pour compat)
    (nl_dir / "sources.json").write_text(
        json.dumps({"sources_primaires": [], "sources_relais": [], "meta": {
            "last_updated": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_sources": 0
        }}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok("sources.json")

    # backlog.json, historique.json, feedback.json, feedback_ui.json
    for fname, content in [
        ("backlog.json",     "[]"),
        ("historique.json",  "[]"),
        ("feedback.json",    "{}"),
        ("feedback_ui.json", "[]"),
    ]:
        (nl_dir / fname).write_text(content, encoding="utf-8")
        ok(fname)

    # index.html — depuis le template, patch du titre
    tpl_html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    (nl_dir / "index.html").write_text(
        patch_index_html(tpl_html, name), encoding="utf-8")
    ok("index.html (depuis _template/index.html)")

    # newsletters/ — répertoire vide pour les fichiers générés
    (nl_dir / "newsletters").mkdir()
    ok("newsletters/ (répertoire prêt)")

    # templates/ — copier depuis _template si présent
    tpl_templates = TEMPLATE_DIR / "templates"
    if tpl_templates.exists():
        shutil.copytree(tpl_templates, nl_dir / "templates")
        ok("templates/ (copiés depuis _template)")
    else:
        (nl_dir / "templates").mkdir()
        ok("templates/ (répertoire vide)")

    return nl_dir

# ─── Mise à jour de index.json ─────────────────────────────────────────────────
def update_index_json(slug, name, description, icon):
    idx = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    idx["newsletters"].append({
        "slug": slug,
        "name": name,
        "description": description,
        "status": "active",
        "language": "fr",
        "icon": icon
    })
    INDEX_JSON.write_text(json.dumps(idx, ensure_ascii=False, indent=2), encoding="utf-8")
    ok(f"index.json mis à jour ({len(idx['newsletters'])} NL)")

# ─── Commit Git ────────────────────────────────────────────────────────────────
def git_commit_push(slug, name):
    print(f"\n{BOLD}Commit & push…{RESET}")
    try:
        subprocess.run(["git", "add",
                        f"newsletters/{slug}/",
                        "newsletters/index.json"],
                       cwd=ROOT, check=True)
        subprocess.run(["git", "commit", "-m",
                        f"feat(newsletter): création {slug} — {name}\n\n"
                        f"Générée par create_newsletter.py — structure complète validée."],
                       cwd=ROOT, check=True)
        subprocess.run(["git", "push"], cwd=ROOT, check=True)
        ok(f"Pushé sur main — newsletters/{slug}/ disponible")
    except subprocess.CalledProcessError as e:
        err(f"Git error : {e}")
        warn("Fichiers créés localement — commit manuel requis.")

# ─── Mode interactif ───────────────────────────────────────────────────────────
def interactive_mode():
    print(f"\n{BOLD}{'═'*60}")
    print("  CRÉATION D'UNE NOUVELLE NEWSLETTER")
    print(f"{'═'*60}{RESET}\n")

    # Slug
    while True:
        slug = ask("Slug (ex: tech-retail, beauty-pro)")
        e = validate_slug(slug)
        if e: err(e)
        else: break

    # Nom
    name = ask("Nom affiché (ex: Tech & Retail)")
    if not name:
        err("Le nom est requis"); sys.exit(1)

    # Description (sous-titre dans l'interface)
    default_desc = f"Veille stratégique · {name} · Quotidienne"
    description = ask("Description courte", default_desc)

    # Icône
    icon = ask("Icône emoji", "📰")

    # Persona
    print(f"\n{YELLOW}Persona — décris le lecteur cible et ce qu'il cherche dans cette veille :{RESET}")
    persona = ask("Persona")
    if not persona:
        err("Le persona est requis"); sys.exit(1)

    # Catégories
    print(f"\n{YELLOW}Catégories — format slug:Description (séparées par des virgules){RESET}")
    print(f"  {CYAN}Exemple : tendances:Tendances produit,digital:E-commerce et IA,concurrence:Mouvements enseignes{RESET}")
    cats_raw = ask("Catégories")
    if not cats_raw:
        err("Au moins une catégorie est requise"); sys.exit(1)
    try:
        categories = parse_categories(cats_raw)
    except Exception as e:
        err(f"Format catégories invalide : {e}"); sys.exit(1)

    print(f"\n{BOLD}Catégories parsées :{RESET}")
    for k, v in categories.items():
        print(f"  {CYAN}{k}{RESET} → {v}")

    confirm = ask("\nCréer la newsletter ?", "oui")
    if confirm.lower() not in ("oui", "o", "yes", "y"):
        print("Annulé."); sys.exit(0)

    return slug, name, description, persona, categories, icon

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Crée une nouvelle newsletter")
    parser.add_argument("--slug")
    parser.add_argument("--name")
    parser.add_argument("--description")
    parser.add_argument("--persona")
    parser.add_argument("--categories", help="slug:Desc,slug:Desc ou JSON")
    parser.add_argument("--icon", default="📰")
    parser.add_argument("--no-push", action="store_true", help="Ne pas pusher sur git")
    args = parser.parse_args()

    # Mode interactif si paramètres manquants
    if not (args.slug and args.name and args.persona and args.categories):
        slug, name, description, persona, categories, icon = interactive_mode()
    else:
        slug        = args.slug
        name        = args.name
        description = args.description or f"Veille stratégique · {name} · Quotidienne"
        persona     = args.persona
        icon        = args.icon
        e = validate_slug(slug)
        if e: err(e); sys.exit(1)
        try:
            categories = parse_categories(args.categories)
        except Exception as ex:
            err(f"Format catégories invalide : {ex}"); sys.exit(1)

    # ── Création ──
    try:
        create_newsletter_files(slug, name, description, persona, categories, icon)
        update_index_json(slug, name, description, icon)
    except Exception as e:
        err(f"Erreur création : {e}")
        # Nettoyage si répertoire partiellement créé
        nl_dir = NEWSLETTERS / slug
        if nl_dir.exists():
            shutil.rmtree(nl_dir)
            warn(f"Répertoire newsletters/{slug}/ supprimé (rollback)")
        sys.exit(1)

    # ── Validation ──
    print(f"\n{BOLD}Validation de la structure créée…{RESET}")
    result = subprocess.run(
        [sys.executable, str(VALIDATE_PY), "--slug", slug],
        cwd=ROOT
    )
    if result.returncode != 0:
        warn("Des problèmes ont été détectés — vérifier avant de pusher")

    # ── Git ──
    if not args.no_push:
        do_push = ask("\nCommitter et pusher sur main ?", "oui")
        if do_push.lower() in ("oui", "o", "yes", "y"):
            git_commit_push(slug, name)
        else:
            warn("Fichiers créés localement — commit manuel requis.")

    print(f"\n{GREEN}{BOLD}✅ Newsletter '{slug}' prête !{RESET}")
    print(f"   → newsletters/{slug}/")
    print(f"   → Ajouter des sources dans sources_rss.json")
    print(f"   → Lancer : python scripts/fetch_backlog.py --slug {slug}")
    print(f"   → Générer : python scripts/daily_briefing_workflow.py --slug {slug}\n")


if __name__ == "__main__":
    main()
