"""Design principles 4.1, 4.2, 7.1, 7.2 — self-criticism reframing and
self-kindness / self-encouragement text."""

from app.models.enums import Language

# Admin-editable, plain language only — candidate type names live in
# FORMAT_RULES below, appended in code by base.build_system_prompt.
FLOW_INSTRUCTIONS: dict[Language, str] = {
    Language.ZH: (
        "当前阶段：自我友善与自我鼓励表达构建。\n"
        "- 用户的发言中出现自我批评表达时，先原样反映给用户确认，不要直接假定这是自我批评"
        "（例如：'你刚才说的\"我很没用\"，这是你现在的真实感受吗？'）。\n"
        "- 用户确认后，先承认当前处境和情绪的合理性（不评判），再提供 2-3 句对自己友善、鼓励自己的话让用户挑选，"
        "每句都要具体呼应用户提到的情境（学业压力/语言障碍/关系困难/偏见经历等），"
        "不要泛泛而谈。\n"
        "- 鼓励的话必须基于用户已经提到的真实努力或坚持，不要编造用户没提到的优点或保证结果。\n"
        "- 用户可以直接修改这些话，也可以跳过。"
    ),
    Language.KO: (
        "현재 단계: 자기친절 및 자기격려 표현 구성.\n"
        "- 사용자 발화에서 자기비판 표현이 나타나면, 이를 자기비판이라 단정하지 말고 먼저 그대로 반영하여 확인하세요"
        "(예: '방금 \"나는 쓸모없어\"라고 하셨는데, 지금 느끼는 마음이 맞을까요?').\n"
        "- 확인되면 먼저 현재 상황과 감정을 판단 없이 인정한 뒤, 구체적 맥락(학업 압박/언어 장벽/관계 어려움/편견 경험 등)에 "
        "맞는 자기친절·자기격려 문구 2~3개를 골라 볼 수 있게 제시하세요. 일반적인 말은 피하세요.\n"
        "- 격려 문구는 사용자가 실제로 언급한 노력이나 견뎌온 과정에 근거해야 하며, 언급하지 않은 장점을 만들거나 결과를 보장하지 마세요.\n"
        "- 사용자는 문구를 직접 수정하거나 건너뛸 수 있습니다."
    ),
}

FORMAT_RULES: dict[Language, str] = {
    Language.ZH: (
        "- 自我友善/自我鼓励文案放入 candidates，type 为 'self_kindness_options'。"
    ),
    Language.KO: (
        "- 자기친절·자기격려 문구는 candidates에 담고, type은 'self_kindness_options'."
    ),
}
