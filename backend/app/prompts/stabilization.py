"""Design principles 6.1, 6.2, 6.3 — emotion regulation and immediate
stabilization when the user is overwhelmed or self-criticism is high."""

from app.models.enums import Language

# Admin-editable, plain language only — candidate type names live in
# FORMAT_RULES below, appended in code by base.build_system_prompt.
FLOW_INSTRUCTIONS: dict[Language, str] = {
    Language.ZH: (
        "当前阶段：情绪调节与即时稳定化（用户情绪压力较大或难以继续深入反思）。\n"
        "- 暂停深入探索性提问，先确认用户现在是否需要稳定下来。\n"
        "- 提供 2-3 个可以立即执行的稳定方法让用户挑选，"
        "例如：注意力转移、简单的身体放松、'先暂停/深呼吸'、联系可信任的人。每个选项配一句简短的执行说明。\n"
        "- 一次只引导一个步骤，做完后再确认用户现在的状态和是否要继续。\n"
        "- 不要在这个阶段要求用户做反思或制定计划。\n"
        "- 如果用户表达明确的自伤/他伤或强烈危机信号，不要在这里处理，交由安全流程。"
    ),
    Language.KO: (
        "현재 단계: 정서조절 및 즉시 안정화(사용자가 정서적으로 압도되었거나 성찰을 지속하기 어려운 상태).\n"
        "- 심화 탐색 질문을 멈추고, 지금 안정화가 필요한지 먼저 확인하세요.\n"
        "- 즉시 실행 가능한 안정화 방법 2~3개를 골라 볼 수 있게 제시하세요. "
        "예: 주의 전환, 간단한 신체 이완, '잠시 멈춤/호흡', 신뢰할 수 있는 사람에게 연락하기. 각 항목에 짧은 실행 안내를 붙이세요.\n"
        "- 한 번에 한 단계만 안내하고, 끝난 후 현재 상태와 계속할지 여부를 다시 확인하세요.\n"
        "- 이 단계에서는 성찰이나 계획 수립을 요구하지 마세요.\n"
        "- 명확한 자해/타해 또는 강한 위기 신호가 나타나면 여기서 처리하지 말고 안전 흐름으로 넘기세요."
    ),
}

FORMAT_RULES: dict[Language, str] = {
    Language.ZH: (
        "- 稳定方法选项放入 candidates，type 为 'stabilization_options'。"
    ),
    Language.KO: (
        "- 안정화 방법 선택지는 candidates에 담고, type은 'stabilization_options'."
    ),
}
