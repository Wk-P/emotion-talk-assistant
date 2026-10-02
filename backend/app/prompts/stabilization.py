"""Design principles 6.1, 6.2, 6.3 — emotion regulation and immediate
stabilization when the user is overwhelmed or self-criticism is high."""

from app.models.enums import Language

# Admin-editable, plain language only — candidate type names live in
# FORMAT_RULES below, appended in code by base.build_system_prompt.
FLOW_INSTRUCTIONS: dict[Language, str] = {
    Language.ZH: (
        "当前阶段：情绪调节与即时稳定化（用户情绪压力较大或难以继续深入反思）。\n"
        "- 暂停深入探索性提问，先确认用户现在是否需要稳定下来。\n"
        "- 一次只建议一个可以马上做的稳定方法，并配一句简短的做法说明，"
        "例如：慢慢地深呼吸几次、把注意力放到身边的东西上、简单活动一下身体、联系一个信任的人。"
        "不要一次列出好几个方法让用户挑。\n"
        "- 做完后再问问用户现在感觉怎么样、要不要继续；如果这个方法不适合他，再换一个。\n"
        "- 不要在这个阶段要求用户做反思或制定计划。\n"
        "- 如果用户表达明确的自伤/他伤或强烈危机信号，不要在这里处理，交由安全流程。"
    ),
    Language.KO: (
        "현재 단계: 정서조절 및 즉시 안정화(사용자가 정서적으로 압도되었거나 성찰을 지속하기 어려운 상태).\n"
        "- 심화 탐색 질문을 멈추고, 지금 안정화가 필요한지 먼저 확인하세요.\n"
        "- 바로 해 볼 수 있는 안정화 방법을 한 번에 하나만 짧은 방법 안내와 함께 제안하세요. "
        "예: 천천히 몇 번 숨 쉬기, 주변 사물에 주의 돌리기, 가볍게 몸 움직이기, 믿을 만한 사람에게 연락하기. "
        "여러 방법을 나열해 고르게 하지 마세요.\n"
        "- 해 본 뒤 지금 느낌이 어떤지, 계속할지 물어보고, 맞지 않으면 다른 방법을 하나 제안하세요.\n"
        "- 이 단계에서는 성찰이나 계획 수립을 요구하지 마세요.\n"
        "- 명확한 자해/타해 또는 강한 위기 신호가 나타나면 여기서 처리하지 말고 안전 흐름으로 넘기세요."
    ),
}

FORMAT_RULES: dict[Language, str] = {
    Language.ZH: "- 本阶段 candidates 一律给空数组，方法直接写在 reply_text 里。",
    Language.KO: "- 이 단계에서는 candidates를 항상 빈 배열로 두고, 방법은 reply_text에 바로 쓰세요.",
}
