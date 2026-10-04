"""Admin tools for checking the prompts as a whole (admin page "AI 对话设置"):

  - check: the model reads every block in effect and lists, in plain words,
    places where two instructions contradict each other. Only reports.
  - scripts: a few saved user-side conversations admins rerun after an edit
    to compare replies with the previous version.
  - run-turn: one turn of such a run through the real conversation code
    (stages, notes, cards), in a transaction that is rolled back — nothing
    is stored. The browser keeps the state between turns, so each request
    stays short.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin_required
from app.db.session import get_db
from app.models.app_setting import AppSetting
from app.models.enums import Language, MessageRole
from app.models.message import Message
from app.models.session import ConversationSession
from app.models.user import User
from app.prompts import registry
from app.services.dialogue_state import handle_turn
from app.services.llm import LLMUnavailable, _complete_json
from app.services.model_settings import current_effort, current_model

router = APIRouter(prefix="/api/admin/prompt-tools", tags=["admin-prompts"])

# ---- check for contradictions ----

_CHECK_INSTRUCTIONS = {
    Language.ZH: (
        "你是帮管理员检查 AI 对话说明的助手。下面是管理员为一个对话 AI 写的全部说明，按段落列出。"
        "请找出互相矛盾、要求相反、或者会让 AI 不知道该听哪一条的地方（同一段内或不同段之间都算）。"
        "只报告真正的冲突，不要评价写得好不好，不要提改进文风的建议。"
        "用简单的中文写，给不懂技术的人看。"
        '只返回 JSON：{"conflicts": [{"where": "涉及哪几段（用段落名称）", "problem": "哪里冲突，引用原话", '
        '"suggestion": "可以怎么改（一句话）"}]}。没有冲突就给空数组。'
    ),
    Language.KO: (
        "당신은 관리자가 쓴 AI 대화 안내를 점검하는 도우미예요. 아래는 관리자가 대화 AI에게 준 모든 안내를 단락별로 나열한 거예요. "
        "서로 모순되거나, 요구가 반대이거나, AI가 어느 쪽을 따라야 할지 모를 곳을 찾아 주세요(같은 단락 안이든 단락 사이든). "
        "실제 충돌만 알려 주고, 잘 썼는지 평가하거나 문체 개선을 제안하지 마세요. 기술을 모르는 사람이 읽을 수 있게 쉬운 한국어로 쓰세요. "
        'JSON만 돌려주세요: {"conflicts": [{"where": "관련 단락(단락 이름)", "problem": "어디가 충돌하는지, 원문 인용", '
        '"suggestion": "어떻게 고치면 좋을지(한 문장)"}]}. 충돌이 없으면 빈 배열.'
    ),
}


class CheckRequest(BaseModel):
    language: Language


class Conflict(BaseModel):
    where: str = ""
    problem: str = ""
    suggestion: str = ""


@router.post("/check", response_model=list[Conflict])
async def check_conflicts(
    payload: CheckRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin_required),
) -> list[Conflict]:
    modules = [m for m in await registry.load_modules(db) if m.enabled and m.group != "system"]
    resolved = await registry.resolve(db, [m.key for m in modules], payload.language)
    parts = [
        f"=== {m.title(payload.language)} ===\n{resolved[m.key].content.strip()}"
        for m in modules
        if resolved[m.key].content.strip()
    ]
    messages = [
        {"role": "system", "content": _CHECK_INSTRUCTIONS[payload.language]},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
    try:
        parsed = await _complete_json(messages, await current_model(db), await current_effort(db))
    except LLMUnavailable as e:
        raise HTTPException(status_code=503, detail=f"ai service unavailable: {e.reason}") from e
    items = parsed.get("conflicts") if isinstance(parsed, dict) else None
    return [Conflict(**{k: str(c.get(k) or "") for k in ("where", "problem", "suggestion")}) for c in items or [] if isinstance(c, dict)]


# ---- saved test conversations ----

SCRIPTS_SETTING = "test_scripts"
DEFAULT_SCRIPTS: list[dict[str, Any]] = [
    {
        "id": "presentation",
        "name": "发表没讲好（自责较强）",
        "language": "zh",
        "lines": [
            "这周课上发表，我讲得很差，结巴了好几次",
            "同学好像在笑，教授也没说什么，我觉得很丢脸",
            "下课我就直接回宿舍了，晚饭也没吃",
            "对，就是这样",
            "我想整理自己的情绪",
            "丢脸，还有点生自己的气",
            "我觉得别人都可以，只有我不行，都是我准备得不够",
            "是的，我一直在骂自己",
            "我会跟朋友说没关系，第一次都会紧张",
            "好像也不是只有我会这样",
            "今天先到这里吧",
        ],
    },
    {
        "id": "roommate",
        "name": "和室友有矛盾（自责较弱）",
        "language": "zh",
        "lines": [
            "室友总是很晚回来，开灯吵醒我",
            "我跟她说过一次，她说知道了，但还是这样",
            "我现在每天都睡不好，上课没精神",
            "对，差不多是这样",
            "我想一起想想接下来怎么办",
            "我觉得不是我的问题，是她不顾别人",
            "可能再找她好好谈一次",
        ],
    },
    {
        "id": "just_talk",
        "name": "只想说说",
        "language": "zh",
        "lines": [
            "最近说不清楚为什么，就是很累",
            "每天上课、打工，回到房间什么都不想做",
            "也没有特别的事，就是累",
            "嗯，是这样",
            "我只是想说一说",
            "说出来好像好一点了",
        ],
    },
]


class Script(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=60)
    language: Language
    lines: list[str] = Field(min_length=1, max_length=30)


@router.get("/scripts", response_model=list[Script])
async def get_scripts(
    db: AsyncSession = Depends(get_db), _admin: User = Depends(get_current_admin_required)
) -> list[Script]:
    row = await db.get(AppSetting, SCRIPTS_SETTING)
    try:
        saved = json.loads(row.value) if row and row.value else None
    except ValueError:
        saved = None
    return [Script(**s) for s in (saved if isinstance(saved, list) else DEFAULT_SCRIPTS)]


@router.put("/scripts", response_model=list[Script])
async def save_scripts(
    scripts: list[Script],
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> list[Script]:
    if len(scripts) > 10:
        raise HTTPException(status_code=422, detail="at most 10 scripts")
    row = await db.get(AppSetting, SCRIPTS_SETTING) or AppSetting(key=SCRIPTS_SETTING, value="")
    row.value = json.dumps([s.model_dump(mode="json") for s in scripts], ensure_ascii=False)
    row.updated_by_id = admin.id
    db.add(row)
    await db.commit()
    return scripts


# ---- one turn of a test run ----


class RunMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    meta: dict[str, Any] = {}


class RunState(BaseModel):
    flow_state: dict[str, Any] = {}
    confirmed_context: dict[str, Any] = {}
    self_criticism_level: float = 0.0


class RunTurnRequest(BaseModel):
    language: Language
    message: str = Field(min_length=1, max_length=4000)
    history: list[RunMessage] = Field(default=[], max_length=80)
    state: RunState = RunState()


class RunTurnResponse(BaseModel):
    reply_text: str
    candidates: list[dict[str, Any]]
    stage: str | None
    state: RunState


@router.post("/run-turn", response_model=RunTurnResponse)
async def run_turn(
    payload: RunTurnRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin_required),
) -> RunTurnResponse:
    session = ConversationSession(
        id=str(uuid.uuid4()),
        user_id=admin.id,
        language=payload.language,
        flow_state=payload.state.flow_state,
        confirmed_context=payload.state.confirmed_context,
        self_criticism_level=payload.state.self_criticism_level,
        consent={},
    )
    db.add(session)
    # Explicit, increasing times: the conversation code orders by them.
    start = datetime.now(timezone.utc) - timedelta(seconds=len(payload.history) + 1)
    for i, m in enumerate([*payload.history, RunMessage(role="user", content=payload.message)]):
        db.add(
            Message(
                session_id=session.id,
                role=MessageRole(m.role),
                content=m.content,
                meta=m.meta,
                created_at=start + timedelta(seconds=i),
            )
        )
    try:
        result = await handle_turn(db, session, payload.message, None)
        state = RunState(
            flow_state=dict(session.flow_state or {}),
            confirmed_context=dict(session.confirmed_context or {}),
            self_criticism_level=session.self_criticism_level,
        )
    except LLMUnavailable as e:
        raise HTTPException(status_code=503, detail=f"ai service unavailable: {e.reason}") from e
    finally:
        await db.rollback()  # a rehearsal: nothing from it is kept
    return RunTurnResponse(reply_text=result.reply_text, candidates=result.candidates, stage=result.stage, state=state)
