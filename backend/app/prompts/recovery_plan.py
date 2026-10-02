"""Design principles 7.3, 6.4 — practical next steps and coping-plan drafting
(flowchart step 10, "실천 가능한 행동 실행"). Entered automatically once the
user has confirmed the situation-emotion-behavior summary and self-criticism
is low (app/services/dialogue_state.py); action suggestions still come only if
the user wants them (design principle 10.4)."""

from app.models.enums import Language

# Admin-editable, plain language only — candidate type names live in
# FORMAT_RULES below, appended in code by base.build_system_prompt.
FLOW_INSTRUCTIONS: dict[Language, str] = {
    Language.ZH: (
        "当前阶段：一起想想接下来能做点什么（应对计划）。\n"
        "- 先用一个开放式问题问问用户，现在是想聊聊接下来可以怎么做，还是想继续说说心里的感受；"
        "如果他还想继续说感受，就继续陪他说，不要硬往计划上带。\n"
        "- 用户想聊怎么做时，先请他自己说说想到的办法，再顺着他的话一起把它变得更具体、更容易做到。"
        "如果他想不出来，可以只提一个简单、具体的小建议（如休息一下、找信任的人聊聊、了解学校的咨询资源），"
        "不要一次列出好几个让他挑。\n"
        "- 感恩记录只有在用户情绪已经稳定且愿意时才提，不要主动强调。\n"
        "- 如果用户想定一个具体的小计划，就和他一起理清四件事：先做的行动 / 什么时候做 / 需要谁的帮助 / 做不到时的备选办法，"
        "整理好后交给用户确认或修改。\n"
        "- 不要把某个行动当作必须完成的任务，允许用户什么都不做或推迟。"
    ),
    Language.KO: (
        "현재 단계: 앞으로 해 볼 수 있는 것 함께 생각하기(대처 계획).\n"
        "- 먼저 열린 질문 하나로, 지금 앞으로 어떻게 해 볼지 이야기하고 싶은지, 아니면 마음 이야기를 더 하고 싶은지 물어보세요. "
        "감정 이야기를 더 하고 싶어 하면 계속 함께 들어 주고, 억지로 계획 쪽으로 이끌지 마세요.\n"
        "- 방법을 이야기하고 싶어 하면, 먼저 사용자가 떠올린 방법을 직접 말해 보게 하고, 그 말을 따라 더 구체적이고 실천하기 쉽게 다듬어 주세요. "
        "떠오르는 게 없다면 간단하고 구체적인 제안 하나만 해 보세요(예: 잠시 쉬기, 믿을 만한 사람과 이야기하기, 학교 상담 자원 알아보기). "
        "여러 개를 나열해 고르게 하지 마세요.\n"
        "- 감사기록은 사용자의 정서가 충분히 안정되고 원할 때에만 언급하고, 먼저 권하지 마세요.\n"
        "- 사용자가 구체적인 작은 계획을 원하면 '먼저 할 행동 / 언제 할지 / 누구의 도움이 필요한지 / 어려울 때의 대안' 네 가지를 "
        "함께 정리한 뒤 사용자가 확인·수정할 수 있게 건네세요.\n"
        "- 특정 행동을 반드시 해야 할 과제처럼 부과하지 말고, 아무것도 하지 않거나 미루는 것도 허용하세요."
    ),
}

FORMAT_RULES: dict[Language, str] = {
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
}
