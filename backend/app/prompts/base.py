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


# Fixed conversation rules, set by the research team — not admin-editable and
# placed last so they win over any example wording in the editable text
# (e.g. "比如……还是……" in a flow description).
FIXED_CONVERSATION_RULES: dict[Language, str] = {
    Language.ZH: (
        "【固定对话规则（优先于以上所有说明）】\n"
        "- 提问时只问开放式问题，不要在问题里给出选项或列举可能的答案让用户挑选"
        "（例如不要说「是 A、B，还是 C？」「比如 X、Y、Z」）。\n"
        "- 默认用户会主动继续输入更多内容：每次回复简短回应，最多提一个开放式问题，"
        "不要急着追问，也不要替用户补充或猜测还没说的内容，留出空间让用户自己继续说。"
    ),
    Language.KO: (
        "[고정 대화 규칙 (위의 모든 안내보다 우선)]\n"
        "- 질문할 때는 열린 질문만 하고, 질문 안에 선택지나 예상 답변을 나열해 고르게 하지 마세요"
        "(예: 「A인가요, B인가요, 아니면 C인가요?」「예를 들면 X, Y, Z」 같은 표현 금지).\n"
        "- 사용자가 스스로 더 많은 내용을 입력할 것이라고 기본적으로 가정하세요: 답변은 짧게 반응하고 "
        "열린 질문은 최대 하나만 하며, 서둘러 추가 질문을 하거나 사용자가 아직 말하지 않은 내용을 "
        "대신 채우거나 추측하지 말고, 사용자가 스스로 이어서 말할 여지를 남겨 두세요."
    ),
}


def build_system_prompt(rules_text: str, flow_instructions: str, language: Language, flow_format: str) -> str:
    # rules_text (the common principles, see principles.build_rules_text) and
    # flow_instructions are passed in because admins can override them (see
    # app/prompts/registry.py); the format rules are never overridable.
    return (
        f"{rules_text}\n\n---\n{flow_instructions}\n\n---\n{FORMAT_RULES[language]}\n{flow_format}"
        f"\n{REPLY_LANGUAGE[language]}"
        f"\n\n---\n{FIXED_CONVERSATION_RULES[language]}"
    )
