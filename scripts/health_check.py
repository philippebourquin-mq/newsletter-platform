#!/usr/bin/env python3
"""
scripts/health_check.py — Vérifie que chaque newsletter active a été générée aujourd'hui.

Lit newsletters/index.json, parcourt les newsletters à status "active",
et vérifie que TODAY.date dans data.js correspond à la date du jour (Paris).

Usage :
    python3 scripts/health_check.py                  # vérifie toutes les actives
    python3 scripts/health_check.py --date 2026-05-14  # vérifie une date spécifique
    python3 scripts/health_check.py --slug briefing-ia # vérifie un slug seulement

Codes de sortie :
    0  — toutes les newsletters vérifiées sont à jour
    1  — une ou plusieurs newsletters sont manquantes ou périmées
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
INDEX_JSON = ROOT / "newsletters" / "index.json"
TZ_PARIS = ZoneInfo("Europe/Paris")


def get_today(date_override: str | None = None) -> str:
    """Retourne la date attendue au format YYYY-MM-DD."""
    if date_override:
        return date_override
    return datetime.now(tz=TZ_PARIS).strftime("%Y-%m-%d")


def extract_today_date(data_js: Path) -> str | None:
    """
    Extrait la valeur de TODAY.date depuis data.js.
    Recherche le pattern : date:"YYYY-MM-DD" ou date: "YYYY-MM-DD"
    """
    if not data_js.exists():
        return None
    content = data_js.read_text(encoding="utf-8")
    # Matche: "date":"YYYY-MM-DD" ou date: "YYYY-MM-DD"
    m = re.search(r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2})"', content)
    return m.group(1) if m else None


def check_newsletters(slugs: list[str], expected_date: str) -> list[dict]:
    """
    Vérifie chaque slug et retourne la liste des résultats.
    Chaque résultat : {"slug", "status", "found_date", "ok"}
    """
    results = []
    for slug in slugs:
        data_js = ROOT / "newsletters" / slug / "data.js"
        found = extract_today_date(data_js)
        ok = found == expected_date
        results.append({
            "slug":       slug,
            "status":     "OK" if ok else ("ABSENT" if found is None else "PÉRIMÉ"),
            "found_date": found or "—",
            "ok":         ok,
        })
    return results


def load_active_slugs(slug_filter: str | None = None) -> list[str]:
    """Charge les slugs actifs depuis index.json."""
    data = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    slugs = [
        n["slug"] for n in data.get("newsletters", [])
        if n.get("status") == "active"
    ]
    if slug_filter:
        slugs = [s for s in slugs if s == slug_filter]
    return slugs


def main() -> int:
    parser = argparse.ArgumentParser(description="Vérifie la génération des newsletters du jour.")
    parser.add_argument("--date",  default=None, help="Date attendue YYYY-MM-DD (défaut: aujourd'hui Paris)")
    parser.add_argument("--slug",  default=None, help="Vérifier un seul slug")
    args = parser.parse_args()

    expected = get_today(args.date)
    slugs = load_active_slugs(args.slug)

    if not slugs:
        print(f"[health_check] Aucun slug actif trouvé{' pour ' + args.slug if args.slug else ''}.")
        return 1

    print(f"[health_check] Date attendue : {expected}")
    print(f"[health_check] Newsletters vérifiées : {', '.join(slugs)}")
    print()

    results = check_newsletters(slugs, expected)

    ok_count = 0
    fail_count = 0
    for r in results:
        icon = "✓" if r["ok"] else "✗"
        print(f"  {icon}  {r['slug']:<20}  {r['status']:<8}  (trouvé: {r['found_date']})")
        if r["ok"]:
            ok_count += 1
        else:
            fail_count += 1

    print()
    if fail_count == 0:
        print(f"[health_check] Toutes les newsletters sont à jour ({ok_count}/{len(results)}). ✓")
        return 0
    else:
        print(f"[health_check] {fail_count} newsletter(s) manquante(s) ou périmée(s) ! ✗")
        print(f"[health_check] Vérifier les logs GitHub Actions pour les slugs en échec.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
