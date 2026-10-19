"""Which conversation stage a session is in, and when it moves on — decided
here in code. The ORDER of the stages is the admins' (admin page "对话流程顺序",
app/prompts/registry.flow_order); the default follows
documents/01_研究资料/애플리케이션 플로우차트.png and the project lead's STEP 1-5
(documents/02_内容与需求/对话运行Prompt_负责人.md):

  listen → purpose → explore → self_check → self_kindness → regulate → act → closing

Some built-in stages carry behaviour of their own, wherever they are placed:
  - purpose ends on the user's answer;
  - self_check ends on the user's answer and sets a branch: strong → full
    self_kindness; weak / none → self_kindness kept brief. Regulate follows
    either way (the lead's STEP 4 A/B);
  - closing is always last; admins may turn it off (the conversation then
    stays in the last step).
Every other stage (including stages admins add) ends when the model reports
its goal reached (stage_done) after a minimum number of user turns, or at a
maximum — both admin-set per step (app/services/flow_config.py). The toolbar "跳过" skips the current stage; "告诉我怎么办" / "今天先到这里"
(reported by the model as user_request) jump to act / closing; where those
two requests lead is admin-set too (flow_config). There are no cards inside
the conversation any more — the conversation card comes from
app/services/summary_card.py, at fixed times.

A turn screened as overwhelmed (RiskLevel.WATCH) is answered with the
stabilization prompt without changing the stage.
"""

from typing import Any

from app.models.enums import Language
from app.models.session import ConversationSession
from app.prompts import stages
from app.services.flow_config import FlowConfig

# Stages that end on something the user does, not on the model's stage_done.
_USER_ENDED = {stages.PURPOSE, stages.SELF_CHECK}


def _user_ended(cfg: FlowConfig) -> set[str]:
    # The admin-chosen closing step waits for the user to leave.
    return _USER_ENDED | ({cfg.closing_step} if cfg.closing_step else set())



def state(session: ConversationSession, cfg: FlowConfig) -> dict[str, Any]:
    order = cfg.order

    s = dict(session.flow_state or {})
    stage = s.get("stage")
    if not stage:
        # New conversation, or one from before stages existed: past the
        # summary means past listening.
        seb = (session.confirmed_context or {}).get("seb_entries")
        s = {"stage": order[0], "turns": 0}
        if seb and order[0] == stages.LISTEN:
            _advance(s, cfg)
    elif stage not in order:
        # The admins turned this stage off or removed it mid-conversation.
        if stage in stages.ORDER:
            _advance(s, cfg)
        else:
            _enter(s, next((k for k in order if k not in (stages.LISTEN, stages.PURPOSE)), order[-1]))
    return s


def _enter(s: dict[str, Any], stage: str) -> None:
    s["stage"] = stage
    s["turns"] = 0
    s.pop("jump_asked", None)


def _after(stage: str, order: list[str]) -> list[str]:
    if stage in order:
        return order[order.index(stage) + 1 :]
    # Not in the order (turned off): what followed it in the default order.
    later = stages.ORDER[stages.ORDER.index(stage) + 1 :] if stage in stages.ORDER else []
    return [k for k in order if k in later] or order[-1:]


# A decision log for admins (shown with the reply in the admin transcript):
# each entry is (zh, ko); "{k:<step key>}" is replaced by the step's name.
Log = list[tuple[str, str]] | None


_WORDS = {
    "strong": ("强", "강함"), "weak": ("弱", "약함"), "none": ("没有", "없음"),
    "end_today": ("今天先到这里", "오늘은 여기까지"), "to_action": ("告诉我怎么办", "어떻게 하면 좋을지"),
}


def _w(value: Any, i: int, empty: tuple[str, str]) -> str:
    if not value:
        return empty[i]
    return _WORDS.get(str(value), (str(value), str(value)))[i]


def _note(log: Log, zh: str, ko: str) -> None:
    if log is not None:
        log.append((zh, ko))


def _advance(s: dict[str, Any], cfg: FlowConfig, log: Log = None) -> None:
    stage = s["stage"]
    rest = _after(stage, cfg.order)
    if rest:
        _enter(s, rest[0])
        _note(log, f"进入下一步：{{k:{rest[0]}}}", f"다음 단계로: {{k:{rest[0]}}}")
    else:
        # Nothing left: stay in the last step.
        _note(log, "已经是最后一步，停在这里", "마지막 단계라 그대로 머물러요")


def _limits(s: dict[str, Any], cfg: FlowConfig) -> tuple[int, int | None]:
    stage = s["stage"]
    if stage == stages.SELF_KINDNESS and s.get("branch") in ("weak", "none"):
        # Weak or no self-criticism: brief acceptance only, admin-set
        # ("自我批评不强时，不要反复进行自我友善活动").
        return cfg.weak_kindness
    if stage == stages.PURPOSE or stage == cfg.closing_step:
        return 1, None
    return cfg.limits_for(stage)


def before_reply(
    session: ConversationSession,
    user_text: str | None,
    confirmation: dict[str, Any] | None,
    self_criticism_level: float,
    cfg: FlowConfig,
    log: Log = None,
) -> dict[str, Any]:
    """Applies what the user just did; returns the state the reply is
    written in (also saved on the session)."""

    s = state(session, cfg)
    card = (confirmation or {}).get("card_type")
    stage = s["stage"]
    _note(log, f"回复前所在步骤：{{k:{stage}}}（这一步已聊 {s.get('turns', 0)} 轮）", f"답하기 전 단계: {{k:{stage}}} (이 단계에서 {s.get('turns', 0)}번 대화함)")

    if card == "skip":
        _note(log, "用户点了「跳过」", "사용자가 \"건너뛰기\"를 눌렀어요")
        if stage == stages.SELF_CHECK:
            s["branch"] = "none"
        if stage != cfg.closing_step:
            _advance(s, cfg, log)
        else:
            _note(log, "收尾步骤不能跳过，留在原地", "마무리 단계는 건너뛸 수 없어 그대로예요")
    elif stage == stages.PURPOSE and user_text:
        _note(log, "用户没有点选项，直接打字回答了目的", "사용자가 선택지 대신 직접 목적을 입력했어요")
        s["purpose"] = "other"
        _advance(s, cfg, log)
    elif user_text:
        s["turns"] = s.get("turns", 0) + 1
        least, most = _limits(s, cfg)
        _note(
            log,
            f"这一步第 {s['turns']} 轮（最少 {least} 轮，最多 {most if most is not None else '不限'} 轮）",
            f"이 단계 {s['turns']}번째 (최소 {least}, 최대 {most if most is not None else '제한 없음'})",
        )
        if most is not None and s["turns"] >= most:
            _note(log, "已到最多轮数，自动进入下一步", "최대 횟수에 도달해 다음 단계로 넘어가요")
            if stage == stages.SELF_CHECK and not s.get("branch"):
                # No clear answer: fall back on the code-side keyword signal.
                s["branch"] = (
                    "strong" if self_criticism_level * 100 >= cfg.criticism["strong"] else "weak" if self_criticism_level > 0 else "none"
                )
            _advance(s, cfg, log)

    session.flow_state = s
    return s


def after_reply(
    session: ConversationSession, signals: dict[str, Any], cfg: FlowConfig, log: Log = None
) -> None:
    """Applies the model's progress signals for the next turn."""

    s = state(session, cfg)
    stage, turns = s["stage"], s.get("turns", 0)
    request = signals.get("user_request")
    # Set when the last turn's "tell me what to do" was held back to check
    # with the user; only good for the very next turn.
    asked = s.pop("jump_asked", False)
    closing = cfg.closing_step
    _note(
        log,
        f"AI 的判断：这一步{'已完成' if signals.get('stage_done') is True else '还没完成'}；用户请求：{_w(request, 0, ('无', '없음'))}；自我批评：{_w(signals.get('self_criticism'), 0, ('未判断', '판단 없음'))}",
        f"AI 판단: 이 단계 {'완료' if signals.get('stage_done') is True else '미완료'}; 사용자 요청: {_w(request, 1, ('无', '없음'))}; 자기비판: {_w(signals.get('self_criticism'), 1, ('未判断', '판단 없음'))}",
    )
    if request == "end_today" and cfg.end_today_enabled and closing and stage != closing and closing in cfg.order:
        _note(log, f"用户说今天先到这里，跳到收尾：{{k:{closing}}}", f"사용자가 오늘은 여기까지라고 해 마무리로: {{k:{closing}}}")
        _enter(s, closing)
    elif request == "to_action" and cfg.to_action_step and stage in cfg.to_action_skip:
        _note(log, "用户似乎想知道怎么办，但这一步设置为不跳转", "사용자가 방법을 원하는 것 같지만 이 단계에서는 이동하지 않도록 설정돼 있어요")
        _after_signals(s, stage, turns, signals, cfg, log)
    elif request == "to_action" and cfg.to_action_step and cfg.to_action_step not in _after(stage, cfg.order):
        _note(log, f"用户似乎想知道怎么办，但目标步骤（{{k:{cfg.to_action_step}}}）已停用或不在当前步骤后面，不跳转", f"사용자가 방법을 원하는 것 같지만 목표 단계({{k:{cfg.to_action_step}}})가 꺼져 있거나 현재 단계 뒤에 없어 이동하지 않아요")
        _after_signals(s, stage, turns, signals, cfg, log)
    elif request == "to_action" and cfg.to_action_step and cfg.to_action_confirm and not asked:
        _note(log, "用户似乎想知道怎么办：先不跳，下一轮让 AI 跟用户确认", "사용자가 방법을 원하는 것 같아요: 바로 이동하지 않고 다음 번에 AI가 확인해요")
        s["jump_asked"] = True
        _after_signals(s, stage, turns, signals, cfg, log)
    elif request == "to_action" and cfg.to_action_step:
        _note(log, f"用户想知道怎么办，跳到：{{k:{cfg.to_action_step}}}", f"사용자가 방법을 원해 이동: {{k:{cfg.to_action_step}}}")
        _enter(s, cfg.to_action_step)
    else:
        _after_signals(s, stage, turns, signals, cfg, log)
    session.flow_state = s


def _after_signals(
    s: dict[str, Any], stage: str, turns: int, signals: dict[str, Any], cfg: FlowConfig, log: Log
) -> None:
    """The ordinary progress rules, when no user request moved the step."""

    if stage == stages.SELF_CHECK:
        level = signals.get("self_criticism")
        if turns >= 1 and level in ("strong", "weak", "none"):
            _note(log, f"自我批评程度判断为：{_w(level, 0, ('', ''))}", f"자기비판 정도: {_w(level, 1, ('', ''))}")
            s["branch"] = level
            _advance(s, cfg, log)
    elif stage not in _user_ended(cfg) and signals.get("stage_done") is True and turns >= _limits(s, cfg)[0]:
        _note(log, "AI 判断完成且已到最少轮数", "AI가 완료로 판단했고 최소 횟수도 채웠어요")
        _advance(s, cfg, log)
    elif signals.get("stage_done") is True:
        _note(log, "AI 判断完成，但还没到最少轮数（或这一步要等用户操作），留在原地", "AI는 완료로 봤지만 최소 횟수 전이거나 사용자 조작을 기다리는 단계라 그대로예요")


def purpose_note(s: dict[str, Any], language: Language, cfg: FlowConfig, sys: dict[str, str]) -> str:
    """For the prompt: what the user said they want from this conversation."""

    pid = s.get("purpose")
    if not pid or not sys["system.note_purpose"]:
        return ""
    what = "见用户上一句话" if language == Language.ZH else "사용자의 앞선 말 참고"
    return sys["system.note_purpose"].replace("{purpose}", what)


def jump_note(s: dict[str, Any], sys: dict[str, str]) -> str:
    """For the prompt: last turn looked like "tell me what to do" and was held back."""

    return sys["system.note_confirm_jump"] if s.get("jump_asked") else ""


def branch_note(s: dict[str, Any], sys: dict[str, str]) -> str:
    if s["stage"] != stages.SELF_KINDNESS:
        return ""
    return sys["system.note_branch_strong" if s.get("branch") == "strong" else "system.note_branch_weak"]
