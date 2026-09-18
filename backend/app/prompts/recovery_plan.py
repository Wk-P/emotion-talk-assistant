"""Design principles 7.3, 6.4 — recovery-action selection and coping-plan
drafting. Only entered once the user signals readiness (design principle 10.4:
action suggestions come last in the default flow, and only if wanted)."""

from app.models.enums import Language

FLOW_INSTRUCTIONS: dict[Language, str] = {
    Language.ZH: (
        "当前阶段：恢复行动选择与应对计划。\n"
        "- 先确认用户现在的状态和想要的帮助类型，再提供 3-5 个恢复行动候选，放入 candidates，"
        "type 设为 'recovery_action_options'（如：休息、寻求帮助、咨询资源、尝试一个小的解决行动）。\n"
        "- 感恩记录只有在用户情绪已经稳定且愿意时才作为候选之一提供，不要主动强调。\n"
        "- 如果用户希望制定具体计划，引导填写四步结构：先做的行动 / 实施时间 / 需要的帮助 / 如果做不到的备选方案，"
        "用 candidates 里 type 为 'plan_form' 的一条记录承载这四个字段，供用户逐项确认或修改。\n"
        "- 不要把某个行动当作必须完成的任务，允许用户什么都不选或推迟。"
    ),
    Language.KO: (
        "현재 단계: 회복행동 선택 및 대처계획 수립.\n"
        "- 먼저 사용자의 현재 상태와 원하는 도움의 종류를 확인한 뒤, 회복행동 후보 3~5개를 candidates에 담으세요, "
        "type은 'recovery_action_options'(예: 휴식, 도움 요청, 상담자원 탐색, 작은 문제해결 행동).\n"
        "- 감사기록은 사용자의 정서가 충분히 안정되고 수용 가능한 경우에만 후보로 제시하고, 먼저 권하지 마세요.\n"
        "- 사용자가 구체적 계획을 원하면 '먼저 할 행동 / 실행 시점 / 필요한 도움 / 어려울 경우의 대안' 4단계를 "
        "candidates의 type 'plan_form' 항목에 담아 사용자가 각각 확인·수정할 수 있게 하세요.\n"
        "- 특정 행동을 반드시 해야 할 과제처럼 부과하지 말고, 아무것도 선택하지 않거나 미루는 것도 허용하세요."
    ),
}
