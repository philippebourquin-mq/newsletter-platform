# Workflow quotidien — Briefing IA Phil

## Exécution locale
```bash
python scripts/daily_briefing_workflow.py --validate-only
python scripts/daily_briefing_workflow.py
```

## Ce que fait le script
- calcule `DATE` et `DATE_LONGUE` en timezone Europe/Paris,
- lit/crée les fichiers de config et suivi (`config.json`, `historique.json`, `backlog.json`, `feedback.json`, `sources.json`),
- traite les `retour-YYYY-MM-DD.json` en attente,
- génère:
  - `briefing-ia-phil/newsletters/newsletter-$DATE.md`
  - `briefing-ia-phil/newsletters/newsletter-$DATE.html`
  - `briefing-ia-phil/retour-$DATE.json`
- met à jour `briefing-ia-phil/data.js` uniquement sur `TODAY`, `ARCHIVE`, `ARCHIVE_FULL`.

## Exécution GitHub Actions
Le workflow `.github/workflows/daily-briefing.yml` exécute le script tous les jours, puis commit/push les changements si nécessaire.

## Points d’attention
- Le script nécessite un `backlog.json` non vide pour construire la sélection du jour.
- Les résumés sont construits automatiquement à partir des entrées backlog (à remplacer par votre collecte éditoriale quotidienne si besoin).
