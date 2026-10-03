"""Shared system-prompt scaffolding (design principles 8.1, 8.3, 10.1-10.3;
role tone and depth per documents/02_内容与需求/Modified_Log.md "AI 角色规则细化").

Every flow-specific prompt in this package is composed on top of the common
principles in principles.py (one section per area of documents/03_技术文档/指导意见2.md).
Nothing here should be the sole enforcement of a safety-critical rule (risk
screening and consent gating happen in app/services/safety.py and the API
layer, in code) — this is tone/behavior guidance for the model, not a guard.
Which candidate cards may reach the user at all is enforced in code too
(app/services/dialogue_state.py), not just asked for here.
"""

from app.models.enums import Language
from app.prompts import framework

# Machine-facing rules (candidate field/type names the frontend renders) are
# kept out of the admin-editable text above, so non-technical admins only
# ever see plain-language guidance. They're appended here, in code, and so
# can't be lost by an edit. Each flow module has its own FORMAT_RULES too.
FORMAT_RULES: dict[Language, str] = {
    Language.ZH: (
        "【系统格式要求】\n"
        "- candidates 默认给空数组。不要生成任何让用户点选的选项（情绪词、方法、文案等），"
        "也不要在 reply_text 正文里列出选项；只有下面明确写到的情况才可以放内容。"
    ),
    Language.KO: (
        "[시스템 형식 요구사항]\n"
        "- candidates는 기본적으로 빈 배열로 두세요. 사용자가 눌러서 고르는 선택지(감정 단어, 방법, 문구 등)는 만들지 말고, "
        "reply_text 본문에도 선택지를 나열하지 마세요. 아래에 명시된 경우에만 내용을 넣을 수 있습니다."
    ),
}


# The user can switch language mid-conversation (sidebar setting). Without
# this the model keeps mirroring the language of the earlier messages, so
# the chosen language is stated explicitly — fixed in code, not editable.
REPLY_LANGUAGE: dict[Language, str] = {
    Language.ZH: "- 无论之前的对话或用户输入用的是什么语言，reply_text 和候选项都必须用简体中文。",
    Language.KO: "- 이전 대화나 사용자의 입력이 어떤 언어이든, reply_text와 후보 항목은 반드시 한국어로 작성하세요.",
}


def build_system_prompt(
    rules_text: str,
    flow_instructions: str,
    language: Language,
    flow_key: str,
    flow_format: str,
    other_text: str = "",
) -> str:
    # rules_text (the common principles), flow_instructions and other_text
    # (admin-added "其他" blocks) are passed in because admins edit them (see
    # app/prompts/registry.py); the format rules and the research framework
    # are never overridable. The framework goes last so it wins any conflict
    # with admin text (see app/prompts/framework.py).
    sections = [s for s in (rules_text, flow_instructions, other_text) if s.strip()]
    return (
        framework.EDITABLE_HEADER[language]
        + "\n\n"
        + "\n\n---\n".join(sections)
        + f"\n\n---\n{FORMAT_RULES[language]}\n{flow_format}"
        f"\n{REPLY_LANGUAGE[language]}"
        f"\n\n---\n{framework.framework_text(flow_key, language)}"
    )
