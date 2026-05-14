#!/usr/bin/env python3
"""
scripts/generate_dashboard.py — Génère newsletters/status.html

Dashboard de santé de la plateforme newsletter :
- Statut de chaque newsletter (OK / PÉRIMÉ / ABSENT)
- Dernière édition connue
- Lien vers la newsletter

Usage :
    python3 scripts/generate_dashboard.py
    python3 scripts/generate_dashboard.py --date 2026-05-14  # vérifier une date spécifique

Le fichier status.html est écrit dans newsletters/ et peut être servi
directement via GitHub Pages ou un serveur statique.
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
STATUS_HTML = ROOT / "newsletters" / "status.html"
TZ_PARIS = ZoneInfo("Europe/Paris")


def get_today(date_override: str | None = None) -> str:
    if date_override:
        return date_override
    return datetime.now(tz=TZ_PARIS).strftime("%Y-%m-%d")


def extract_today_date(data_js: Path) -> str | None:
    if not data_js.exists():
        return None
    content = data_js.read_text(encoding="utf-8")
    m = re.search(r'"date"\s*:\s*"(\d{4}-\d{2}-\d{2})"', content)
    return m.group(1) if m else None


def count_editions(newsletters_dir: Path) -> int:
    if not newsletters_dir.exists():
        return 0
    return len(list(newsletters_dir.glob("newsletter-*.html")))


def build_results(newsletters: list[dict], expected: str) -> list[dict]:
    results = []
    for nl in newsletters:
        slug = nl["slug"]
        nl_dir = ROOT / "newsletters" / slug
        data_js = nl_dir / "data.js"
        newsletters_dir = nl_dir / "newsletters"

        found = extract_today_date(data_js)
        nb_editions = count_editions(newsletters_dir)

        if found is None:
            health = "ABSENT"
        elif found == expected:
            health = "OK"
        else:
            health = "PÉRIMÉ"

        results.append({
            "slug":        slug,
            "name":        nl.get("name", slug),
            "icon":        nl.get("icon", "📰"),
            "description": nl.get("description", ""),
            "nl_status":   nl.get("status", "active"),
            "health":      health,
            "found_date":  found or "—",
            "nb_editions": nb_editions,
            "url":         f"./{slug}/index.html",
        })
    return results


def render_html(results: list[dict], expected: str, generated_at: str) -> str:
    ok_count    = sum(1 for r in results if r["health"] == "OK")
    total_count = sum(1 for r in results if r["nl_status"] == "active")
    overall_ok  = ok_count == total_count

    def badge(health: str) -> str:
        if health == "OK":
            return '<span class="badge ok">✓ À JOUR</span>'
        if health == "PÉRIMÉ":
            return '<span class="badge stale">⚠ PÉRIMÉ</span>'
        return '<span class="badge absent">✗ ABSENT</span>'

    def status_dot(nl_status: str) -> str:
        if nl_status == "active":
            return '<span class="dot active" title="Active"></span>'
        return '<span class="dot test" title="Test"></span>'

    rows = ""
    for r in results:
        rows += f"""
        <tr class="{'ok-row' if r['health'] == 'OK' else 'fail-row'}">
          <td class="name-cell">
            <span class="icon">{r['icon']}</span>
            <span class="nl-name">{r['name']}</span>
            {status_dot(r['nl_status'])}
          </td>
          <td class="desc-cell">{r['description']}</td>
          <td class="date-cell">{r['found_date']}</td>
          <td class="editions-cell">{r['nb_editions']}</td>
          <td class="badge-cell">{badge(r['health'])}</td>
          <td class="link-cell">
            <a href="{r['url']}" class="view-link">Voir →</a>
          </td>
        </tr>"""

    summary_class = "summary-ok" if overall_ok else "summary-fail"
    summary_text = (
        f"✓ Toutes les newsletters actives sont à jour ({ok_count}/{total_count})"
        if overall_ok
        else f"⚠ {total_count - ok_count} newsletter(s) en retard sur {total_count} actives"
    )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>📊 Dashboard newsletters</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #0f1117;
      color: #e2e8f0;
      min-height: 100vh;
      padding: 2rem;
    }}
    .container {{ max-width: 960px; margin: 0 auto; }}

    h1 {{
      font-size: 1.6rem;
      font-weight: 700;
      color: #f8fafc;
      margin-bottom: 0.25rem;
    }}
    .subtitle {{
      font-size: 0.85rem;
      color: #64748b;
      margin-bottom: 1.5rem;
    }}

    .summary {{
      padding: 0.75rem 1rem;
      border-radius: 8px;
      font-weight: 600;
      font-size: 0.9rem;
      margin-bottom: 1.5rem;
    }}
    .summary-ok   {{ background: #052e16; color: #4ade80; border: 1px solid #166534; }}
    .summary-fail {{ background: #2d1515; color: #f87171; border: 1px solid #7f1d1d; }}

    table {{
      width: 100%;
      border-collapse: collapse;
      background: #1e2130;
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 2px 8px rgba(0,0,0,0.4);
    }}
    thead th {{
      background: #262c40;
      color: #94a3b8;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 0.75rem 1rem;
      text-align: left;
    }}
    tbody tr {{
      border-top: 1px solid #2a3042;
      transition: background 0.15s;
    }}
    tbody tr:hover {{ background: #252a3a; }}
    td {{ padding: 0.8rem 1rem; vertical-align: middle; }}

    .name-cell {{ display: flex; align-items: center; gap: 0.5rem; min-width: 180px; }}
    .icon {{ font-size: 1.2rem; }}
    .nl-name {{ font-weight: 600; color: #f1f5f9; }}
    .dot {{
      width: 7px; height: 7px; border-radius: 50%;
      display: inline-block; margin-left: 4px;
    }}
    .dot.active {{ background: #22c55e; box-shadow: 0 0 5px #22c55e88; }}
    .dot.test   {{ background: #f59e0b; }}

    .desc-cell  {{ color: #94a3b8; font-size: 0.82rem; max-width: 260px; }}
    .date-cell  {{ font-family: monospace; font-size: 0.88rem; color: #cbd5e1; }}
    .editions-cell {{ color: #64748b; font-size: 0.85rem; text-align: center; }}
    .badge-cell {{ }}

    .badge {{
      display: inline-block;
      padding: 0.25rem 0.6rem;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 700;
      letter-spacing: 0.04em;
    }}
    .badge.ok     {{ background: #052e16; color: #4ade80; border: 1px solid #166534; }}
    .badge.stale  {{ background: #1c1408; color: #fbbf24; border: 1px solid #78350f; }}
    .badge.absent {{ background: #2d1515; color: #f87171; border: 1px solid #7f1d1d; }}

    .view-link {{
      color: #818cf8;
      text-decoration: none;
      font-size: 0.85rem;
      font-weight: 500;
    }}
    .view-link:hover {{ color: #a5b4fc; text-decoration: underline; }}

    .footer {{
      margin-top: 1.25rem;
      font-size: 0.78rem;
      color: #334155;
      text-align: right;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>📊 Dashboard newsletters</h1>
    <p class="subtitle">Date de référence : <strong>{expected}</strong> · Généré le {generated_at}</p>

    <div class="summary {summary_class}">{summary_text}</div>

    <table>
      <thead>
        <tr>
          <th>Newsletter</th>
          <th>Description</th>
          <th>Dernière édition</th>
          <th style="text-align:center">Éditions</th>
          <th>Statut</th>
          <th></th>
        </tr>
      </thead>
      <tbody>{rows}
      </tbody>
    </table>

    <p class="footer">Généré par scripts/generate_dashboard.py · Newsletter Platform</p>
  </div>
</body>
</html>"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Génère newsletters/status.html")
    parser.add_argument("--date", default=None, help="Date de référence YYYY-MM-DD (défaut: aujourd'hui Paris)")
    args = parser.parse_args()

    expected = get_today(args.date)
    generated_at = datetime.now(tz=TZ_PARIS).strftime("%d/%m/%Y à %H:%M")

    data = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    newsletters = data.get("newsletters", [])

    results = build_results(newsletters, expected)
    html = render_html(results, expected, generated_at)
    STATUS_HTML.write_text(html, encoding="utf-8")

    ok_count = sum(1 for r in results if r["health"] == "OK")
    print(f"[dashboard] status.html généré → {STATUS_HTML}")
    print(f"[dashboard] {ok_count}/{len(results)} newsletters à jour pour {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
