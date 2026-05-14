# Changelog — Newsletter Platform

Toutes les modifications notables de ce projet sont documentées ici.
Les entrées automatiques (génération quotidienne) sont ajoutées par le workflow GitHub Actions.

## [2026-04-30] — génération automatique

- Édition du 2026-04-30 générée et publiée (fetch RSS + Claude)

## [2026-05-01] — génération automatique

- Édition du 2026-05-01 générée et publiée (fetch RSS + Claude)

## [2026-05-05] — génération automatique

- Édition du 2026-05-05 générée et publiée (fetch RSS + Claude)

## [2026-05-10] — génération automatique

- Édition du 2026-05-10 générée et publiée (fetch RSS + Claude)

## [2026-05-11] — génération automatique

- Édition du 2026-05-11 générée et publiée (fetch RSS + Claude)

## [2026-05-12] — génération automatique

- Édition du 2026-05-12 générée et publiée (fetch RSS + Claude)

## [2026-05-13] — génération automatique

- Édition du 2026-05-13 générée et publiée (fetch RSS + Claude)

## [2026-05-14] — génération automatique

- Édition du 2026-05-14 générée et publiée (fetch RSS + Claude)

---

## [2026-04-29]

### Architecture multi-newsletters

- `newsletters/index.json` : registre centralisé des newsletters actives (`9dcedac`)
- `newsletters/briefing-ia/config.json` : ajout des champs identité `slug`, `name`, `status`, `language` (`9dcedac`)
- `scripts/daily_briefing_workflow.py` : argument `--slug` + `_init_paths(slug)` — tous les chemins deviennent dynamiques (`9dcedac`)
- `scripts/fetch_backlog.py` : argument `--slug` + `_init_paths(slug)` — idem (`9dcedac`)
- `.github/workflows/daily-briefing.yml` : `--slug briefing-ia` passé explicitement aux deux scripts (`9dcedac`)
- `newsletters/app.js` : moteur JS déplacé à la racine `newsletters/`, partagé entre toutes les newsletters (`59f168f`)
- `newsletters/briefing-ia/data.js` : injection de `NEWSLETTER_SLUG='briefing-ia'` — mis à jour à chaque génération (`59f168f`)
- `newsletters/briefing-ia/index.html` : charge `../app.js` au lieu de `./app.js` (`59f168f`)
- `newsletters/briefing-ia/app.js` : les 4 chemins GitHub hardcodés remplacés par `${NEWSLETTER_SLUG}` (`59f168f`)
- `index.html` : portail d'accueil dynamique — lit `newsletters/index.json` pour afficher les cards (`4d17f43`)
- `newsletters/briefing-test/` : newsletter de test créée pour valider l'architecture multi-slugs (`1d5eaeb`)

### Interface admin (admin.html)

- Onglet Changelog ajouté : fetch de `CHANGELOG.md`, rendu en grille 4 colonnes type / catégorie / description / commit (`8aff7b7`, `c92a71a`)
- Layout Changelog refait en grille CSS alignée (`7f750a5`)

---

## [2026-04-28]

### Portail
- Titre page d'accueil : "Vos newsletters de veille IA" → "Vos newsletters de veille" (`46338a1`)
- Sous-titre : suppression de la mention "IA" (`230c448`)

### Site public (GitHub Pages)
- Correction page blanche : `re.sub` interprétait les `\n` du JSON comme séquences d'échappement regex — remplacé par des lambdas dans `update_data_js()` (`013aad1`)
- Correction du fichier `data.js` existant (newlines littéraux dans les strings JSON) (`013aad1`)
- Ajout de `.nojekyll` pour désactiver Jekyll sur GitHub Pages (`8c0a969`)

### Qualité newsletter
- Panachage catégories dans `build_today` : plafond max 2 articles par catégorie (calculé dynamiquement : `nb_news ÷ 3`) pour éviter qu'une seule thématique domine (`501b8aa`)

### Workflow automatique
- Cron décalé de 05:10 UTC à 03:00 UTC pour éviter le pic de queue GitHub Actions (`4072203`)
- Timeout du job GitHub Actions fixé à 45 minutes (`4072203`)
- Cache pip ajouté : les dépendances Python ne sont plus réinstallées à chaque run (`4072203`)
- `max_articles_corps` réduit de 30 à 15 dans `sources_rss.json` (`4072203`)
- Timeout 15s sur `YouTubeTranscriptApi.get_transcript()` via `ThreadPoolExecutor` (`4072203`)
- Validation des secrets (ANTHROPIC_API_KEY, TAVILY_API_KEY) en première étape du workflow (`ff27956`)
- `workflow_dispatch` : ajout d'un champ date optionnel pour rejouer une édition manuellement (`ff27956`)

### Divers
- Fix inconnu (message de commit non renseigné) (`988f254`)

---

## [2026-04-27]

### Interface admin (admin.html)
- Réordonnancement des catégories par glisser-déposer HTML5 avec indicateur visuel de position — v2.5 (`c0acc0e`)
- Liste catégories affinée : numéro monospace, taille naturelle des chips, boutons ↑↓ compacts côte à côte — v2.4 (`ab48d2a`)
- Catégories empilées verticalement avec flèches ↑↓ — v2.3 (`351a133`)
- Chips catégories réécrites en DOM API (fin des erreurs silencieuses de template literals). Style aligné avec le site principal — v2.2 (`1fde259`)
- `renderSettings()` protégé par `setTimeout(0)` + try/catch. Indicateur de version dans la nav — v2.1 (`23c6083`)

### Données
- Enregistrement de 5 feedbacks utilisateur (édition 26 avril) (`f619f8a`)
- Génération automatique : édition du 2026-04-27 (`4c915b4`)

---

## [2026-04-26]

### Interface admin (admin.html)
- Design cohérent du backlog : fond sable `--sand-100`, suppression des bordures blanches (`4fa1103`)
- Mise à jour manuelle admin (`a78677f`)
- Cohérence visuelle catégories + contexte sous les titres des articles (`4833b84`)
- Refonte complète : onglets Backlog / Feedback / Paramètres / Sources, cards stats, timeline éditions (`11cd089`)
- Sidebar latérale ajoutée (`15b15c8`)

### Script fetch_backlog.py
- Calcul dynamique de `max_backlog` depuis `config.json` (survie estimée par decay/score_minimum), avec garde-fous min/max (`d11c3fa`)
- Gestion des doublons d'articles (`8306efa`)
- Correction : variable `SOURCES_JSON` non définie (`2db6662`)

### app.js
- Corrections diverses — persistance sources & feedbacks dans localStorage (`a0fc0e2`)
- Correction de la détection de note GitHub (`77fd422`)
- Corrections diverses (`c325f9d`, `4610e2b`, `c2a0597`)

### Données
- Mise à jour manuelle des sources (`aa782ae`, `831be5f`, `ed24430`)
- Enregistrement feedbacks : 3 notes (`3c68821`), 4 notes (`c5fb9de`)
- Ajout du token GitHub pour push depuis l'admin (`050f4f1`)
- Génération automatique : édition du 2026-04-26 (`b9a22a6`)

### Divers
- Footer et baseline ajoutés au portail (`90ba1e4`)
- Corrections workflow daily-briefing.yml (`1fb112c`)
- Mise à jour des boutons de l'interface (`aee33bd`)

---

## [2026-04-25]

### Infrastructure
- Restructuration complète en plateforme multi-newsletters : portail d'accueil, dossier `newsletters/briefing-ia/`, déploiement GitHub Pages (`1f7bb3f`)
- Consolidation de `app.js` dans le dossier `briefing-ia`, suppression du doublon à la racine (`3de50bd`)
- Nettoyage du repo (`a675e58`)

### Données
- Ajout de la clé API Anthropic dans les secrets du repo (`6a8954b`)
- Déploiement GitHub Pages + données `ARCHIVE_FULL` complètes pour toutes les éditions (`0df6460`)
- Complétion de `ARCHIVE_FULL` pour toutes les dates (`bc690a6`)
- Ajout des newsletters manquantes du 15, 16 et 17 avril (`a040e82`, `36fe6ca`)

### Corrections
- Affichage des résumés d'articles dans l'archive (`7f46226`)
- Affichage des archives dans la page HTML (`1f90317`)
- Chemin `newsletters/` manquant dans `openNewsletter()` (`f4e8570`)
- Corrections diverses `app.js` (`0ed2f91`)

---

## [2026-04-23]

### Données
- Génération automatique : édition du 2026-04-23 (`9851982`)

---

## [2026-04-22]

### Données
- Génération automatique : édition du 2026-04-22 (`68f9031`)

---

## [2026-04-21]

### Infrastructure Netlify
- Merge PR #1 : implémentation du workflow quotidien (`6d4eb92`)
- Simplification du point d'entrée Netlify, publication directe depuis `briefing-ia-phil/` (`a5cadf5`)
- Redirection racine vers le briefing pour éviter un 404 (`bd58d5a`)
- Correction du routage Netlify pour que `app.js` soit accessible depuis le briefing (`a9975d7`)
- Correction du répertoire de publication Netlify (`5d601d5`)

---

## [2026-04-20]

### Initialisation workflow
- Ajout du workflow GitHub Actions quotidien (cron 05:10 UTC) pour la génération automatique (`83f3ea2`)
- Mise en place du workflow briefing IA + génération de la première édition (`f775a84`)

---

## [2026-04-19]

### Initialisation
- Commit initial du projet briefing-ia-phil (`7eae69a`)
