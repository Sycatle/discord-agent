"""Human-readable formatting for ``discord.HTTPException``.

Discord error responses carry two distinct codes:

- ``status`` — the HTTP status (403, 404, 429, 5xx);
- ``code`` — the Discord-specific JSON error code (50013, 10003, ...).

The raw text returned by the API is rarely informative on its own
(``"Missing Permissions"`` doesn't say *which* permission). This module
maps the codes we hit most often to a short, actionable French sentence
with an emoji prefix so the user can tell at a glance what to do next.
Unknown codes fall back to a category derived from ``status``.
"""

from __future__ import annotations

import discord

# Mapping from Discord-specific error code to (emoji, message).
# Source: https://discord.com/developers/docs/topics/opcodes-and-status-codes
_CODE_MAP: dict[int, tuple[str, str]] = {
    # Permissions / access
    50013: ("🔒", "Permissions manquantes — vérifier les droits du bot sur ce channel"),
    50001: ("🔒", "Accès refusé — le bot n'est pas membre du channel ou serveur"),
    50007: ("✉", "Impossible d'envoyer un DM à cet utilisateur"),
    # Target not found / wrong target
    10003: ("❓", "Channel inconnu (peut-être supprimé entre preview et exec)"),
    10011: ("❓", "Rôle inconnu"),
    10013: ("❓", "Utilisateur inconnu"),
    10062: ("❓", "Interaction inconnue ou expirée"),
    # Wrong type / invalid form body
    50024: ("⚠", "Type de channel incompatible avec cette opération"),
    50028: ("⚠", "Rôle invalide pour cette action"),
    50035: ("⚠", "Paramètres invalides dans le payload"),
    # Limits reached
    30005: ("📊", "Limite atteinte : 250 rôles par serveur"),
    30013: ("📊", "Limite atteinte : 500 channels par serveur"),
    30007: ("📊", "Limite de webhooks atteinte pour ce channel"),
    30030: ("📊", "Limite atteinte : trop de règles AutoMod du même type"),
    # Rate-limit (rare — usually surfaced as status 429)
    20012: ("⏳", "Action trop fréquente — Discord impose un backoff"),
    # AutoMod
    240000: ("⚠", "Message AutoMod — texte trop long pour le pattern"),
}


# Discord error codes that yield reusable lessons for the agent. The string
# is appended to GuildContext.learned_constraints, surfaced in the system
# prompt on subsequent turns so the LLM doesn't repeat the same mistake.
_LEARNABLE_CODES: dict[int, str] = {
    50013: "Le bot manque de permissions sur certaines cibles — toujours vérifier `check_bot_permissions` ou la hiérarchie de rôles avant d'agir.",
    50024: "Certaines actions échouent par incompatibilité de type de channel — toujours valider le type avant `create_thread` / `edit_channel`.",
    50028: "Certains rôles sont invalides pour `assign_role` ou les overrides — vérifier la hiérarchie (rôle cible doit être sous le top role du bot).",
    30005: "Ce serveur approche la limite de 250 rôles — éviter de créer des rôles ; préférer `edit_role`.",
    30013: "Ce serveur approche la limite de 500 channels — éviter `create_*_channel` ; préférer `edit_channel` ou `delete_channel` d'abord.",
    30007: "Ce channel a atteint sa limite de webhooks — supprimer un webhook avant d'en créer un nouveau.",
    30030: "Limite atteinte pour ce type de règle AutoMod — éviter `create_automod_rule` du même trigger.",
}


def extract_learned_constraint(exc: discord.HTTPException) -> str | None:
    """Return a learnable constraint string for known Discord error codes."""
    code = getattr(exc, "code", 0) or 0
    return _LEARNABLE_CODES.get(code)


def format_discord_error(exc: discord.HTTPException, tool_name: str) -> str:
    """Return a short, user-friendly message for a discord.HTTPException.

    Strategy: prefer the Discord ``code`` mapping when known, otherwise
    derive a category from ``status``. The original ``e.text`` is appended
    after a separator so power users still see the underlying message.
    """
    code = getattr(exc, "code", 0) or 0
    status = getattr(exc, "status", 0) or 0
    raw_text = str(getattr(exc, "text", "") or "").strip()

    if code in _CODE_MAP:
        emoji, message = _CODE_MAP[code]
    elif status == 429:
        emoji, message = "⏳", "Rate-limited by Discord — réessayer plus tard"
    elif 500 <= status < 600:
        emoji, message = "🔧", "Discord temporairement indisponible — réessayer"
    elif status == 403:
        emoji, message = "🔒", "Permission refusée par Discord"
    elif status == 404:
        emoji, message = "❓", "Cible introuvable côté Discord"
    elif status == 400:
        emoji, message = "⚠", "Requête refusée par Discord (payload invalide)"
    else:
        emoji, message = "❌", "Erreur Discord"

    parts = [f"{emoji} {message}", f"sur `{tool_name}`"]
    if code:
        parts.append(f"(code {code})")
    elif status:
        parts.append(f"(status {status})")
    out = " ".join(parts)
    if raw_text and raw_text.lower() not in message.lower():
        out += f" — {raw_text}"
    return out
