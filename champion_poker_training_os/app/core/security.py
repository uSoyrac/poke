from __future__ import annotations


def redact_sensitive_text(text: str) -> str:
    """Tiny local redactor used before logging coach prompts."""
    redacted = text.replace("\n", " ")
    for token in ("api_key", "password", "secret"):
        redacted = redacted.replace(token, "[redacted]")
    return redacted[:500]

