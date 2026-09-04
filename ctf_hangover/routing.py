"""Smart model routing — heuristics to pick the best models per category."""

from __future__ import annotations

# Category → preferred model order. Index 0 = best fit.
# Models must match those returned by 9Router /v1/models.
_CATEGORY_PREFERENCE: dict[str, list[str]] = {
    "pwn": [
        "Sx-AI/anthropic/claude-opus-4.8",
        "Sx-AI/openai/gpt-5.6-terra",
        "Sx-AI/anthropic/claude-opus-4.7",
        "ctf-reverse",
    ],
    "rev": [
        "ctf-reverse",
        "Sx-AI/anthropic/claude-opus-4.8",
        "Sx-AI/openai/gpt-5.6-terra",
        "Sx-AI/anthropic/claude-opus-4.7",
    ],
    "crypto": [
        "ctf-crypto",
        "Sx-AI/openai/gpt-5.6-terra",
        "Sx-AI/anthropic/claude-opus-4.8",
        "Sx-AI/anthropic/claude-opus-4.7",
    ],
    "forensics": [
        "ctf-forensics",
        "Sx-AI/openai/gpt-5.6-terra",
        "Sx-AI/anthropic/claude-opus-4.7",
        "ctf-reasoning",
    ],
    "web": [
        "ctf-web",
        "Sx-AI/openai/gpt-5.6-terra",
        "Sx-AI/anthropic/claude-opus-4.8",
        "Sx-AI/anthropic/claude-sonnet-5",
    ],
    # SOC / SIEM / Wazuh Elasticsearch query analysis.
    # CTF Cyber Academy style: log forensics + sysmon + MITRE ATT&CK + KQL DSL.
    # ctf-reasoning strongest at structured log analysis; opus + terra as backup.
    "soc": [
        "ctf-reasoning",
        "kr/deepseek-3.2-thinking-agentic",
        "Sx-AI/openai/gpt-5.6-terra",
        "Sx-AI/anthropic/claude-opus-4.8",
    ],
    # Services / network exploitation.
    # CVEs + port scan + hydra + exploit chaining. Strong code-reasoning models
    # (deepseek-thinking, qwen3-coder) outperform on EDB scripts.
    "services": [
        "Sx-AI/openai/gpt-5.6-terra",
        "kr/deepseek-3.2-thinking-agentic",
        "kr/qwen3-coder-next-agentic",
        "Sx-AI/anthropic/claude-opus-4.8",
    ],
    "misc": [
        "ctf-reasoning",
        "Sx-AI/openai/gpt-5.6-terra",
        "Sx-AI/anthropic/claude-opus-4.8",
        "Critical-Judgement",
    ],
    "stego": [
        "ctf-forensics",
        "Sx-AI/anthropic/claude-opus-4.8",
        "Sx-AI/openai/gpt-5.6-terra",
        "ctf-reasoning",
    ],
    # Platform category is "Steganografi" (Indonesian). route_models lowercases
    # the category, so this must be its own key (not just "stego").
    "steganografi": [
        "ctf-forensics",
        "Sx-AI/anthropic/claude-opus-4.8",
        "Sx-AI/openai/gpt-5.6-terra",
        "ctf-reasoning",
    ],
    # "Website" (Indonesian) == web; route_models lowercases so keep a key too.
    "website": [
        "ctf-web",
        "Sx-AI/openai/gpt-5.6-terra",
        "Sx-AI/anthropic/claude-opus-4.8",
        "Sx-AI/anthropic/claude-sonnet-5",
    ],
    "osint": [
        "ctf-reasoning",
        "Sx-AI/openai/gpt-5.6-terra",
        "Sx-AI/anthropic/claude-sonnet-5",
        "Critical-Judgement",
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
