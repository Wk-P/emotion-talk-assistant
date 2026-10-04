"""Text the program adds to every prompt around the admins' own blocks —
output format, card and progress-signal fields, the priority header, and
the short progress notes for the current conversation. Admin-editable like
every other block (admin page group "程序附加说明"), each with its default
here; app/prompts/router.py and app/services/dialogue_state.py decide when
each one is sent.

Some of these name JSON fields the program reads (reply_text, candidates,
stage_done, user_request, self_criticism, seb_summary/plan_form fields).
Rewording is fine; renaming a field breaks what reads it. Placeholders in
{curly braces} are filled in by the program.
"""

from app.models.enums import Language

# (key suffix, {language: title}, {language: default body})
_SECTIONS: list[tuple[str, dict[Language, str], dict[Language, str]]] = [
    (
        "priority_header",
        {Language.ZH: "管理员说明的开头", Language.KO: "관리자 안내 머리말"},
        {
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
        },
    ),
    (
        "stage_heading",
        {Language.ZH: "当前步骤的标题", Language.KO: "현재 단계 제목"},
        {Language.ZH: "【当前步骤：{name}】", Language.KO: "[현재 단계: {name}]"},
    ),
    (
        "reply_language",
        {Language.ZH: "回复语言", Language.KO: "답변 언어"},
        {
            Language.ZH: "- 无论之前的对话或用户输入用的是什么语言，reply_text 和候选项都必须用简体中文。",
            Language.KO: "- 이전 대화나 사용자의 입력이 어떤 언어이든, reply_text와 후보 항목은 반드시 한국어로 작성하세요.",
        },
    ),
    (
        "output_json",
        {Language.ZH: "输出格式（JSON）", Language.KO: "출력 형식(JSON)"},
        {
            lang: (
                "输出格式 / Output format: 只返回一个 JSON 对象 / return exactly one JSON object, "
                '{"reply_text": string, "candidates": [{"type": string, "items": [{"id": string, "label": string}]?, '
                '"fields": object?}]}. reply_text 是给用户看的回复；candidates 是可选的结构化建议，'
                "没有则给空数组。不要在 JSON 之外输出任何文字。"
            )
            for lang in Language
        },
    ),
    (
        "format",
        {Language.ZH: "卡片的总规则", Language.KO: "카드 공통 규칙"},
        {
            Language.ZH: (
                "【系统格式要求】\n"
                "- candidates 默认给空数组，只有下面明确写到的情况才可以放内容。需要给用户几个选项参考时，直接写在 reply_text 里。"
            ),
            Language.KO: (
                "[시스템 형식 요구사항]\n"
                "- candidates는 기본적으로 빈 배열로 두고, 아래에 명시된 경우에만 내용을 넣으세요. 사용자에게 참고할 선택지를 줄 때는 reply_text에 바로 쓰세요."
            ),
        },
    ),
    (
        "card_listen",
        {Language.ZH: "小结卡片（听用户讲述困扰）", Language.KO: "정리 카드(고민 듣기)"},
        {
            Language.ZH: (
                "- 只有在要给出上面说的那份总结时，才在 candidates 里放一条 type 为 'seb_summary' 的记录，"
                "fields 固定用三个键：situation（发生了什么）、emotion（当时的感受）、behavior（当时怎么应对，没有就留空字符串）；"
                "只写用户实际说过的内容。每次对话只生成一次。其余时候 candidates 一律给空数组。"
            ),
            Language.KO: (
                "- 위에서 말한 정리를 보여 줄 때에만 candidates에 type 'seb_summary' 항목 하나를 넣으세요. "
                "fields는 세 키로 고정: situation(무슨 일이 있었는지), emotion(그때의 감정), behavior(그때 어떻게 대처했는지, 없으면 빈 문자열). "
                "사용자가 실제로 말한 내용만 쓰고, 대화당 한 번만 생성하세요. 그 외에는 candidates를 항상 빈 배열로 두세요."
            ),
        },
    ),
    (
        "card_act",
        {Language.ZH: "小计划卡片（小恢复行动）", Language.KO: "작은 계획 카드(작은 회복 행동)"},
        {
            Language.ZH: (
                "- 只有在把整理好的小计划交给用户确认时，才在 candidates 里放一条 type 为 'plan_form' 的记录，"
                "fields 固定用四个键：action（先做的行动）、when（实施时间）、support（需要的帮助）、backup（做不到时的备选方案）；"
                "每次对话只生成一次。其余时候 candidates 一律给空数组。"
            ),
            Language.KO: (
                "- 정리한 작은 계획을 사용자에게 확인받을 때에만 candidates에 type 'plan_form' 항목 하나를 넣으세요. "
                "fields는 네 키로 고정: action(먼저 할 행동), when(실행 시점), support(필요한 도움), backup(어려울 경우의 대안). "
                "대화당 한 번만 생성하세요. 그 외에는 candidates를 항상 빈 배열로 두세요."
            ),
        },
    ),
    (
        "no_cards",
        {Language.ZH: "其他步骤不出卡片", Language.KO: "다른 단계는 카드 없음"},
        {
            Language.ZH: "- 本阶段 candidates 一律给空数组。",
            Language.KO: "- 이 단계에서는 candidates를 항상 빈 배열로 두세요.",
        },
    ),
    (
        "signals",
        {Language.ZH: "进度信号", Language.KO: "진행 신호"},
        {
            Language.ZH: (
                "- JSON 里另外加两个字段（用户看不到，只供程序判断进度）："
                "stage_done —— 当前阶段的目标已经基本达到、可以进入下一阶段时给 true，否则给 false；"
                "user_request —— 用户这一句明确表示想直接要办法（如「告诉我怎么办」）时给 \"to_action\"，"
                "明确表示今天想结束（如「今天先到这里」）时给 \"end_today\"，否则给 null。"
            ),
            Language.KO: (
                "- JSON에 필드 두 개를 더 넣으세요(사용자에게 보이지 않고 진행 판단에만 쓰여요): "
                "stage_done — 현재 단계의 목표가 거의 이루어져 다음 단계로 넘어가도 되면 true, 아니면 false; "
                "user_request — 사용자가 이번 말에서 바로 방법을 원한다고 분명히 말하면(예: \"어떻게 해야 할지 알려 주세요\") \"to_action\", "
                "오늘은 끝내고 싶다고 분명히 말하면(예: \"오늘은 여기까지 할게요\") \"end_today\", 아니면 null."
            ),
        },
    ),
    (
        "self_check_signal",
        {Language.ZH: "自我批评程度信号", Language.KO: "자기비판 정도 신호"},
        {
            Language.ZH: (
                "- 再加一个字段 self_criticism：用户已经回答了关于自我批评的确认问题时，按他的回答给 \"strong\"（较强）、"
                "\"weak\"（较弱）或 \"none\"（没有）；还没回答时给 null。"
            ),
            Language.KO: (
                "- 필드 self_criticism도 넣으세요: 사용자가 자기비판에 대한 확인 질문에 답했으면 그 답에 따라 \"strong\"(강함), "
                "\"weak\"(약함), \"none\"(없음) 중 하나를, 아직 답하지 않았으면 null을 주세요."
            ),
        },
    ),
    (
        "note_header",
        {Language.ZH: "「当前进度」标题", Language.KO: "'현재 진행 상황' 제목"},
        {Language.ZH: "【当前进度】", Language.KO: "[현재 진행 상황]"},
    ),
    (
        "note_summary_shown",
        {Language.ZH: "进度：小结已给过", Language.KO: "진행: 정리를 이미 보여 줌"},
        {
            Language.ZH: "本次对话已经给用户看过「发生了什么—感受—应对」小结了，不要再整理小结，也不要在回复里提到小结。",
            Language.KO: "이번 대화에서 '상황-감정-대처' 요약은 이미 보여 주었어요. 다시 요약하지 말고, 답변에서 요약을 언급하지도 마세요.",
        },
    ),
    (
        "note_plan_shown",
        {Language.ZH: "进度：小计划已给过", Language.KO: "진행: 작은 계획을 이미 보여 줌"},
        {
            Language.ZH: "本次对话已经给用户看过整理好的小计划了，不要再生成计划，也不要在回复里说「下面是计划」。",
            Language.KO: "이번 대화에서 정리한 작은 계획은 이미 보여 주었어요. 다시 만들지 말고, 답변에서 '아래 계획'이라고 말하지 마세요.",
        },
    ),
    (
        "note_listen_confirm",
        {Language.ZH: "进度：等用户确认小结（下一步是确认目的）", Language.KO: "진행: 정리 확인 대기(다음은 목적 확인)"},
        {
            Language.ZH: (
                "用户这句话如果是在确认小结（觉得准确、没有要补充），stage_done 给 true，回复只简短回应，"
                "然后问用户现在最需要什么样的帮助（目的选项会以按钮显示在回复下面，不用列出）。"
                "如果用户在补充或修改，就按他的话更新理解，简短再确认一次，stage_done 给 false。"
            ),
            Language.KO: (
                "사용자의 이번 말이 정리를 확인하는 것이라면(정확하고 덧붙일 것이 없다면) stage_done을 true로 하고, 짧게 반응한 뒤 "
                "지금 가장 필요한 도움이 무엇인지 물어보세요(목적 선택지는 답변 아래 버튼으로 나오니 나열하지 마세요). "
                "사용자가 보충하거나 고치는 것이라면 그 말대로 이해를 고치고 짧게 다시 확인한 뒤 stage_done을 false로 하세요."
            ),
        },
    ),
    (
        "note_listen_confirm_other",
        {Language.ZH: "进度：等用户确认小结（下一步不是确认目的）", Language.KO: "진행: 정리 확인 대기(다음이 목적 확인이 아닐 때)"},
        {
            Language.ZH: (
                "用户这句话如果是在确认小结（觉得准确、没有要补充），stage_done 给 true，回复只简短回应，然后进入下一步。"
                "如果用户在补充或修改，就按他的话更新理解，简短再确认一次，stage_done 给 false。"
            ),
            Language.KO: (
                "사용자의 이번 말이 정리를 확인하는 것이라면(정확하고 덧붙일 것이 없다면) stage_done을 true로 하고, 짧게 반응한 뒤 다음 단계로 넘어가세요. "
                "사용자가 보충하거나 고치는 것이라면 그 말대로 이해를 고치고 짧게 다시 확인한 뒤 stage_done을 false로 하세요."
            ),
        },
    ),
    (
        "note_purpose",
        {Language.ZH: "进度：用户选的对话目的", Language.KO: "진행: 사용자가 고른 대화 목적"},
        {
            Language.ZH: "用户这次对话的目的：{purpose}。根据这个目的调整后续问题的深度与顺序。",
            Language.KO: "이번 대화에서 사용자의 목적: {purpose}. 이 목적에 맞게 이후 질문의 깊이와 순서를 조정하세요.",
        },
    ),
    (
        "note_branch_strong",
        {Language.ZH: "进度：自我批评较强", Language.KO: "진행: 자기비판이 강함"},
        {
            Language.ZH: "用户确认自我批评较强：进行自我接纳、人类共同性、正念与情绪距离化，以及自我友善活动。",
            Language.KO: "사용자가 자기비판이 강하다고 확인했어요: 자기수용, 보편적 인간성, 마음챙김과 감정 거리두기, 자기친절 활동을 진행하세요.",
        },
    ),
    (
        "note_branch_weak",
        {Language.ZH: "进度：自我批评较弱或没有", Language.KO: "진행: 자기비판이 약하거나 없음"},
        {
            Language.ZH: "用户的自我批评较弱或没有：只简短进行自我接纳和人类共同性，不要反复进行自我友善活动。",
            Language.KO: "사용자의 자기비판이 약하거나 없어요: 자기수용과 보편적 인간성만 짧게 다루고, 자기친절 활동을 반복하지 마세요.",
        },
    ),
]

KEY_PREFIX = "system."
KEYS: list[str] = [KEY_PREFIX + suffix for suffix, _, _ in _SECTIONS]
TITLES: dict[str, dict[Language, str]] = {KEY_PREFIX + suffix: titles for suffix, titles, _ in _SECTIONS}
DEFAULTS: dict[str, dict[Language, str]] = {KEY_PREFIX + suffix: bodies for suffix, _, bodies in _SECTIONS}
