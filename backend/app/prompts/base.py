"""Shared system-prompt scaffolding.

Two parts, by design: the code-fixed technical rules (output format, card and
signal fields, reply language) come first; everything about how to talk —
the common principles, the stage's instructions and admins' own blocks, all
editable in the admin UI — comes last and takes priority over anything
before it except those technical rules. The project's behaviour is meant to
be shaped by the admins' prompt, not by code; code only decides which stage
is current (app/services/flow.py) and keeps the safety and data rules.
Nothing here should be the sole enforcement of a safety-critical rule (risk
screening and consent gating happen in app/services/safety.py and the API
layer, in code) — this is tone/behavior guidance for the model, not a guard.
Which candidate cards may reach the user at all is enforced in code too
(app/services/dialogue_state.py), not just asked for here.
"""

from app.models.enums import Language
from app.prompts import stages

# Machine-facing rules (candidate field/type names the frontend renders) are
# kept out of the admin-editable text above, so non-technical admins only
# ever see plain-language guidance. They're appended here, in code, and so
# can't be lost by an edit. Each flow module has its own FORMAT_RULES too.
FORMAT_RULES: dict[Language, str] = {
    Language.ZH: (
        "【系统格式要求】\n"
        "- candidates 默认给空数组，只有下面明确写到的情况才可以放内容。需要给用户几个选项参考时，直接写在 reply_text 里。"
    ),
    Language.KO: (
        "[시스템 형식 요구사항]\n"
        "- candidates는 기본적으로 빈 배열로 두고, 아래에 명시된 경우에만 내용을 넣으세요. 사용자에게 참고할 선택지를 줄 때는 reply_text에 바로 쓰세요."
    ),
}


# The user can switch language mid-conversation (sidebar setting). Without
# this the model keeps mirroring the language of the earlier messages, so
# the chosen language is stated explicitly — fixed in code, not editable.
REPLY_LANGUAGE: dict[Language, str] = {
    Language.ZH: "- 无论之前的对话或用户输入用的是什么语言，reply_text 和候选项都必须用简体中文。",
    Language.KO: "- 이전 대화나 사용자의 입력이 어떤 언어이든, reply_text와 후보 항목은 반드시 한국어로 작성하세요.",
}


_ADMIN_HEADER: dict[Language, str] = {
    Language.ZH: (
        "【对话说明（管理员设置，优先于以上所有内容）】\n"
        "下面是你在这次对话中怎么说话、怎么提问的全部说明。除了上面的输出格式和字段要求必须遵守之外，"
        "如果与其他任何内容冲突，都以下面的说明为准。"
    ),
    Language.KO: (
        "[대화 안내 (관리자 설정, 위의 모든 내용보다 우선)]\n"
        "아래는 이 대화에서 어떻게 말하고 질문할지에 대한 모든 안내예요. 위의 출력 형식과 필드 요구사항은 반드시 지키되, "
        "그 밖의 어떤 내용과 충돌하더라도 아래 안내를 따르세요."
    ),
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
    # (admin-added "其他" blocks) are the admin-editable part (see
    # app/prompts/registry.py) and go last; the technical rules come first
    # and are never overridable. The fixed part is also identical across a
    # stage's turns, which keeps the prompt prefix cacheable.
    sections = [s for s in (rules_text, flow_instructions, other_text) if s.strip()]
    return (
        f"{FORMAT_RULES[language]}\n{flow_format}"
        f"\n{stages.signal_rules(flow_key, language)}"
        f"\n{REPLY_LANGUAGE[language]}"
        f"\n\n---\n{_ADMIN_HEADER[language]}\n\n"
        + "\n\n---\n".join(sections)
    )
