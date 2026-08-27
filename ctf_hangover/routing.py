"""Smart model routing — heuristics to pick the best models per category."""

from __future__ import annotations

# Category → preferred model order. Index 0 = best fit.
_CATEGORY_PREFERENCE: dict[str, list[str]] = {
    "pwn": [
        "claude-opus-4-6", "gpt-5.4", "gpt-5.3-codex", "gpt-5.4-mini",
    ],
    "rev": [
        "gpt-5.3-codex", "claude-opus-4-6", "gpt-5.4", "gpt-5.4-mini",
    ],
    "crypto": [
        "gpt-5.4", "claude-opus-4-6", "gpt-5.3-codex", "gpt-5.4-mini",
    ],
    "forensics": [
        "gpt-5.4-mini", "gpt-5.4", "claude-opus-4-6", "gemini-3-flash-preview",
    ],
    "web": [
        "gpt-5.4-mini", "gpt-5.4", "gemini-3-flash-preview", "claude-opus-4-6",
    ],
    "misc": [
        "gpt-5.4-mini", "gemini-3-flash-preview", "gpt-5.4", "claude-opus-4-6",
    ],
    "stego": [
        "gemini-3-flash-preview", "gpt-5.4-mini", "gpt-5.4", "claude-opus-4-6",
    ],
    "osint": [
        "gemini-3-flash-preview", "gpt-5.4", "gpt-5.4-mini", "claude-opus-4-6",
    ],
}


def route_models(
    category: str,
    available: list[str],
    max_models: int = 4,
) -> list[str]:
    """Pick the top-N available models for a challenge category.

    Falls back to "misc" ordering for unknown categories.
    """
    pref = _CATEGORY_PREFERENCE.get(category.lower(), _CATEGORY_PREFERENCE["misc"])
    picked: list[str] = []
    for m in pref:
        if m in available and len(picked) < max_models:
            picked.append(m)
    # Fill remaining slots with whatever is left
    for m in available:
        if m not in picked and len(picked) < max_models:
            picked.append(m)
    return picked
