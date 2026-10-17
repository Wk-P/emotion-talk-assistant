"""A step's text in three parts (admin page: 目标 / 问法 / 示例 boxes).

Stored as a single PromptVersion content so versions, rollback and "reset to
default" keep working unchanged: plain text is the "goal" part alone (all
text written before the split, and every code default); once an admin fills
another box, the content is MARK followed by a JSON object.
app/prompts/router.py sends the parts under their headings (system texts
"system.part_*", admin-editable).
"""

import json

PARTS = ("goal", "ask", "example")
MARK = "⟦step-parts⟧\n"


def split(content: str) -> dict[str, str]:
    if content.startswith(MARK):
        try:
            value = json.loads(content[len(MARK) :])
        except ValueError:
            value = None
        if isinstance(value, dict):
            return {part: str(value.get(part) or "") for part in PARTS}
    return {"goal": content, "ask": "", "example": ""}


def is_empty(content: str) -> bool:
    return not any(p.strip() for p in split(content).values())


def compose(content: str, sys: dict[str, str]) -> str:
    """The text sent for one block: plain text as is; split text with each
    filled part under its heading."""

    if not content.startswith(MARK):
        return content.strip()
    p = split(content)
    return "\n\n".join(
        "\n".join(x for x in (sys[f"system.part_{part}"], p[part].strip()) if x) for part in PARTS if p[part].strip()
    )
