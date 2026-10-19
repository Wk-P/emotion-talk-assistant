"""Text the program adds to every prompt around the admins' own blocks —
output format, card and progress-signal fields, the priority header, and
the short progress notes for the current conversation. Admin-editable like
every other block (admin page group "程序附加说明"), each with its default
here; app/prompts/router.py and app/services/dialogue_state.py decide when
each one is sent.

Some of these name JSON fields the program reads (reply_text, candidates,
stage_done, user_request, self_criticism, the conversation card's summary/plan/kindness).
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
        "part_goal",
        {Language.ZH: "步骤「目标」的标题", Language.KO: "단계 \"목표\" 제목"},
        {Language.ZH: "【这一步要达成什么】", Language.KO: "[이 단계의 목표]"},
    ),
    (
        "part_ask",
        {Language.ZH: "步骤「问法」的标题", Language.KO: "단계 \"질문 방식\" 제목"},
        {Language.ZH: "【怎么问】", Language.KO: "[질문 방식]"},
    ),
    (
        "part_example",
        {Language.ZH: "步骤「示例」的标题", Language.KO: "단계 \"예시\" 제목"},
        {Language.ZH: "【示例】", Language.KO: "[예시]"},
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
        "no_cards",
        {Language.ZH: "对话中不出卡片", Language.KO: "대화 중에는 카드 없음"},
        {
            Language.ZH: "- candidates 一律给空数组。",
            Language.KO: "- candidates는 항상 빈 배열로 두세요.",
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
        "note_purpose",
        {Language.ZH: "进度：用户选的对话目的", Language.KO: "진행: 사용자가 고른 대화 목적"},
        {
            Language.ZH: "用户这次对话的目的：{purpose}。根据这个目的调整后续问题的深度与顺序。",
            Language.KO: "이번 대화에서 사용자의 목적: {purpose}. 이 목적에 맞게 이후 질문의 깊이와 순서를 조정하세요.",
        },
    ),
    (
        "note_no_purpose_buttons",
        {Language.ZH: "进度：确认目的时用文字提问", Language.KO: "진행: 목적은 글로 묻기"},
        {
            Language.ZH: "回复下面没有任何按钮。问用户现在最需要什么帮助时，用一两句话自然地给出几个方向，让用户直接用文字回答；忽略「目的会以按钮显示」之类的说法。",
            Language.KO: "답변 아래에는 버튼이 없어요. 지금 가장 필요한 도움을 물을 때 몇 가지 방향을 한두 문장으로 자연스럽게 제시하고, 사용자가 글로 답하게 하세요. '목적이 버튼으로 나온다' 같은 안내는 무시하세요.",
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
    (
        "note_confirm_jump",
        {Language.ZH: "进度：确认用户是否想直接要办法", Language.KO: "진행: 바로 방법을 원하는지 확인"},
        {
            Language.ZH: (
                "用户上一句可能是想直接要办法。这一轮先回应用户的话，再简短问一句是否现在就聊具体怎么做；"
                "只有用户这一句明确表示要办法时，user_request 才给 \"to_action\"。"
            ),
            Language.KO: (
                "사용자가 앞선 말에서 바로 방법을 원했을 수 있어요. 이번에는 먼저 사용자의 말에 답한 뒤, 지금 바로 구체적인 방법을 이야기할지 짧게 물어보세요. "
                "사용자가 이번 말에서 분명히 방법을 원할 때만 user_request를 \"to_action\"으로 주세요."
            ),
        },
    ),
    (
        "summary_card",
        {Language.ZH: "对话小卡（回顾 / 结束时）", Language.KO: "대화 카드(돌아왔을 때 / 끝낼 때)"},
        {
            Language.ZH: (
                "你要根据下面的对话，为用户写一张对话小卡。只返回一个 JSON 对象，固定三个键：\n"
                "- summary：对话小结，用两三句话写清楚发生了什么、用户有什么感受、当时怎么应对。只写用户实际说过的内容，不要推测。\n"
                "- plan：对话里用户确认或提到的小计划、小行动；对话里没有谈到计划时给空字符串 \"\"，不要自己编。\n"
                "- kindness：一句用户可以对自己说的友善的话。尽量用用户自己的说法；对话里没有时，根据对话内容写一句温和、不评判、不说教的话。\n"
                "用第二人称「你」来写，语气温和、简短。全部用简体中文。"
            ),
            Language.KO: (
                "아래 대화를 바탕으로 사용자에게 줄 대화 카드를 작성하세요. JSON 객체 하나만 반환하고, 키는 세 개로 고정이에요:\n"
                "- summary: 대화 정리. 무슨 일이 있었는지, 사용자가 어떤 감정이었는지, 그때 어떻게 대처했는지 두세 문장으로 쓰세요. 사용자가 실제로 말한 내용만 쓰고 추측하지 마세요.\n"
                "- plan: 대화에서 사용자가 확인했거나 말한 작은 계획·행동. 계획 이야기가 없었으면 빈 문자열 \"\"을 주고, 지어내지 마세요.\n"
                "- kindness: 사용자가 자신에게 건넬 수 있는 따뜻한 말 한마디. 가능하면 사용자의 표현을 쓰고, 없으면 대화 내용에 맞게 부드럽고 평가하지 않는 말로 쓰세요.\n"
                "2인칭(\"당신\" 대신 자연스러운 존댓말)으로 짧고 부드럽게 쓰세요. 모두 한국어로 쓰세요."
            ),
        },
    ),
]

KEY_PREFIX = "system."
KEYS: list[str] = [KEY_PREFIX + suffix for suffix, _, _ in _SECTIONS]
TITLES: dict[str, dict[Language, str]] = {KEY_PREFIX + suffix: titles for suffix, titles, _ in _SECTIONS}
DEFAULTS: dict[str, dict[Language, str]] = {KEY_PREFIX + suffix: bodies for suffix, _, bodies in _SECTIONS}
