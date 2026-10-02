"""Shared system-prompt scaffolding (design principles 8.1, 8.3, 10.1-10.3;
role tone and depth per documents/Modified_Log.md "AI 角色规则细化").

Every flow-specific prompt in this package is composed on top of the common
principles in principles.py (one section per area of documents/指导意见2.md).
Nothing here should be the sole enforcement of a safety-critical rule (risk
screening and consent gating happen in app/services/safety.py and the API
layer, in code) — this is tone/behavior guidance for the model, not a guard.
The disclaimer itself is sent deterministically by
app/services/dialogue_state.py, not by this prompt, so it never depends on
the model actually saying it.
"""

from app.models.enums import Language

# Machine-facing rules (candidate field/type names the frontend renders) are
# kept out of the admin-editable text above, so non-technical admins only
# ever see plain-language guidance. They're appended here, in code, and so
# can't be lost by an edit. Each flow module has its own FORMAT_RULES too.
FORMAT_RULES: dict[Language, str] = {
    Language.ZH: (
        "【系统格式要求】\n"
        "- 需要给用户挑选的候选项（情绪词、策略、文案、小结等）都放进 candidates 字段，"
        "不要在 reply_text 正文里堆砌选项列表。"
    ),
    Language.KO: (
        "[시스템 형식 요구사항]\n"
        "- 사용자에게 고르게 할 후보(감정 단어, 전략, 문구, 요약 등)는 모두 candidates 필드에 넣고, "
        "reply_text 본문에 목록으로 나열하지 마세요."
    ),
}


def build_system_prompt(rules_text: str, flow_instructions: str, language: Language, flow_format: str) -> str:
    # rules_text (the common principles, see principles.build_rules_text) and
    # flow_instructions are passed in because admins can override them (see
    # app/prompts/registry.py); the format rules are never overridable.
    return f"{rules_text}\n\n---\n{flow_instructions}\n\n---\n{FORMAT_RULES[language]}\n{flow_format}"
