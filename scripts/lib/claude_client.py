"""
scripts/lib/claude_client.py
Wrapper unique pour l'API Claude — partagé par fetch_backlog.py et daily_briefing_workflow.py.

Usage :
    from scripts.lib.claude_client import call_claude

    text = call_claude("Résume cet article...", max_tokens=500)
    text = call_claude("Génère un titre...", system="Tu es un éditeur IA.")
"""
from __future__ import annotations

import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
_MODEL = "claude-haiku-4-5-20251001"


def call_claude(prompt: str, max_tokens: int = 500, system: str = "") -> str:
    """
    Appelle l'API Claude et retourne le texte généré.

    Retourne "" si :
    - ANTHROPIC_API_KEY n'est pas définie
    - anthropic n'est pas installé
    - une erreur API se produit (loggée mais non propagée)

    Args:
        prompt:     Contenu du message utilisateur.
        max_tokens: Limite de tokens en sortie (défaut 500).
        system:     Message système optionnel (ignoré si vide).
    """
    if not ANTHROPIC_API_KEY:
        print("[Claude API] ANTHROPIC_API_KEY non définie — génération IA désactivée.")
        return ""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        kwargs: dict = {
            "model": _MODEL,
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
