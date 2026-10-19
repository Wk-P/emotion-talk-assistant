from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import Language
from app.prompts.registry import MAX_CONTENT_LENGTH, MAX_MODULE_NAME_LENGTH
from app.schemas.chat import CandidateCard


class PromptItem(BaseModel):
    key: str
    language: Language
    version: int  # 0 = code default, nothing saved yet
    content: str
    default_content: str
    updated_at: str | None
    updated_by: str | None
    # A saved-but-not-published edit ("暂存"), if any.
    draft_content: str | None = None
    draft_updated_at: str | None = None
    draft_updated_by: str | None = None


class PromptModuleItem(BaseModel):
    key: str
    group: Literal["rules", "flow", "other", "system"]
    built_in: bool
    enabled: bool
    # Admin-set names by language; a missing language shows the default
    # name (built-in blocks) or the other language's name (added blocks).
    names: dict[str, str]
    flow_key: str | None
    # A conversation step (built-in, or added as a step of its own) rather
    # than a block attached to one.
    is_stage: bool = False


class PromptOverview(BaseModel):
    items: list[PromptItem]
    # Every block in display order (see registry.load_modules).
    modules: list[PromptModuleItem]
    # Built-in blocks admins deleted (can be restored).
    deleted: list[str] = []
    # Most characters one block may hold (the editor's counter shows it).
    max_content_length: int = MAX_CONTENT_LENGTH
    # Read-only: appended after every system prompt by app/services/llm.py.
    output_format: str


class PromptVersionItem(BaseModel):
    version: int
    content: str
    note: str | None
    created_at: str
    created_by: str | None


class PromptSaveRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)
    note: str | None = Field(default=None, max_length=200)


class PromptDraftRequest(BaseModel):
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)


class FlowOrder(BaseModel):
    # Every step, in order (turned-off ones too).
    order: list[str] = Field(max_length=100)


class FlowConfigPayload(BaseModel):
    # Per step: [minimum, maximum] user turns (see app/services/flow_config.py).
    limits: dict[str, tuple[int, int]]
    history_turns: int
    # Rules the program applies (see app/services/flow_config.py). Optional
    # so an older admin page that doesn't send them keeps the saved values.
    weak_kindness: tuple[int, int] = (1, 2)
    # "crisis" / "watch" / "self_criticism" -> words.
    keywords: dict[str, list[str]] = Field(default_factory=dict)
    # By language value ("zh"/"ko"); empty = the built-in text.
    crisis_reply: dict[str, str] = Field(default_factory=dict)
    # Self-criticism scoring, 0-100: "up", "down", "strong".
    criticism: dict[str, int] = Field(default_factory=lambda: {"up": 25, "down": 5, "strong": 50})
    to_action_step: str | None = "flow.act"
    # Steps where "tell me what to do" is not acted on.
    to_action_skip: list[str] = Field(default_factory=list, max_length=100)
    # Ask the user first; jump only if they still want advice next turn.
    to_action_confirm: bool = True
    end_today_enabled: bool = True
    crisis_country: str = "KR"
    # Which step answers "enough for today" / an overwhelmed user / the end
    # button (None = none); the last two are left out of the order.
    closing_step: str | None = "flow.closing"
    stabilize_step: str | None = "flow.stabilization"
    ending_step: str | None = "flow.ending"
    # Steps the admin page marks as safety-related (a warning only).
    safety_steps: list[str] = Field(
        default_factory=lambda: ["flow.closing", "flow.stabilization", "flow.ending"], max_length=100
    )


class FlowConfigOverview(FlowConfigPayload):
    defaults: FlowConfigPayload


class PromptModuleCreateRequest(BaseModel):
    group: Literal["rules", "flow", "other"]
    name: str = Field(min_length=1, max_length=MAX_MODULE_NAME_LENGTH)
    # Required for group "flow": which built-in flow the block belongs to.
    flow_key: str | None = None


class PromptModuleUpdateRequest(BaseModel):
    # Rename in one language; an empty name goes back to the default.
    language: Language | None = None
    name: str | None = Field(default=None, max_length=MAX_MODULE_NAME_LENGTH)
    enabled: bool | None = None


class PreviewMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class PromptPreviewRequest(BaseModel):
    language: Language
    # The stage to test (a built-in flow key, app/prompts/stages.py).
    stage: str = "flow.listen"
    # Unsaved draft text per prompt key, used instead of the saved version.
    overrides: dict[str, str] = {}
    history: list[PreviewMessage] = Field(default=[], max_length=40)
    message: str = Field(min_length=1, max_length=4000)


class PromptPreviewResponse(BaseModel):
    reply_text: str
    candidates: list[CandidateCard]
    system_prompt: str
    prompt_versions: dict[str, int]
