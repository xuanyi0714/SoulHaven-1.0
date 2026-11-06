"""Read the existing Markdown transcript for display when the structured archive is unavailable.

This module never writes files or restores the model's summarized context.
"""
from pathlib import Path
import re

_ROLE = re.compile(r"^# (user|assistant|system)[ \t]*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")


def read_markdown_messages(path: Path) -> list[dict[str, str]] | None:
    """Parse writer-produced # user / # assistant blocks, respecting fenced code."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return None
    messages = []
    role = None
    lines = []
    fence = None

    def flush():
        content = "\n".join(lines).strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    for line in text.splitlines():
        marker = _FENCE.match(line)
        if fence:
            lines.append(line)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = None
            continue
        heading = _ROLE.fullmatch(line)
        if heading:
            flush()
            role, lines = heading[1], []
        else:
            if role:
                lines.append(line)
                if marker:
                    fence = marker[1]
    flush()
    return messages or None


def complete_display_history(structured, markdown):
    """Use a longer Markdown archive only when all JSON records still align in order.

    This also handles a JSON file recreated after it was lost, keeping older MD
    rounds visible after the next successful chat. Structured metadata is retained.
    """
    if not markdown:
        return structured
    if not structured:
        return markdown
    if len(markdown) <= len(structured):
        return structured
    matched = 0
    merged = []
    for message in markdown:
        if matched < len(structured) and (
            message.get("role") == structured[matched].get("role")
            and message.get("content", "").strip() == structured[matched].get("content", "").strip()
        ):
            merged.append(structured[matched])
            matched += 1
        else:
            merged.append(message)
    return merged if matched == len(structured) else structured
