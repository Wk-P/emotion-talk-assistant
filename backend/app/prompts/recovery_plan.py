"""Design principles 7.3, 6.4 — recovery-action selection and coping-plan
drafting. Only entered once the user signals readiness (design principle 10.4:
action suggestions come last in the default flow, and only if wanted)."""

from app.models.enums import Language

# Admin-editable, plain language only — candidate type names live in
# FORMAT_RULES below, appended in code by base.build_system_prompt.
FLOW_INSTRUCTIONS: dict[Language, str] = {
    Language.ZH: (
        "当前阶段：恢复行动选择与应对计划。\n"
        "- 先确认用户现在的状态和想要的帮助类型，再提供 3-5 个可以做的恢复行动让用户挑选"
        "（如：休息、寻求帮助、咨询资源、尝试一个小的解决行动）。\n"
        "- 感恩记录只有在用户情绪已经稳定且愿意时才作为选项之一提供，不要主动强调。\n"
        "- 如果用户希望制定具体计划，引导用户填写四步：先做的行动 / 实施时间 / 需要的帮助 / 如果做不到的备选方案，"
        "让用户逐项确认或修改。\n"
        "- 不要把某个行动当作必须完成的任务，允许用户什么都不选或推迟。"
    ),
    Language.KO: (
        "현재 단계: 회복행동 선택 및 대처계획 수립.\n"
        "- 먼저 사용자의 현재 상태와 원하는 도움의 종류를 확인한 뒤, 해 볼 수 있는 회복행동 3~5개를 골라 볼 수 있게 제시하세요"
        "(예: 휴식, 도움 요청, 상담자원 탐색, 작은 문제해결 행동).\n"
        "- 감사기록은 사용자의 정서가 충분히 안정되고 수용 가능한 경우에만 선택지로 제시하고, 먼저 권하지 마세요.\n"
        "- 사용자가 구체적 계획을 원하면 '먼저 할 행동 / 실행 시점 / 필요한 도움 / 어려울 경우의 대안' 4단계를 "
        "사용자가 각각 확인·수정할 수 있게 안내하세요.\n"
        "- 특정 행동을 반드시 해야 할 과제처럼 부과하지 말고, 아무것도 선택하지 않거나 미루는 것도 허용하세요."
    ),
}

FORMAT_RULES: dict[Language, str] = {
    Language.ZH: (
        "- 恢复行动选项放入 candidates，type 为 'recovery_action_options'。\n"
        "- 四步计划用 candidates 里 type 为 'plan_form' 的一条记录承载这四个字段。"
    ),
    Language.KO: (
        "- 회복행동 선택지는 candidates에 담고, type은 'recovery_action_options'.\n"
        "- 4단계 계획은 candidates의 type 'plan_form' 항목 하나에 네 필드로 담으세요."
    ),
}
