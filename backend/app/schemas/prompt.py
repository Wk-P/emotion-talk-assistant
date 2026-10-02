from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import DialogueIntent, Language
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


class PromptModuleItem(BaseModel):
    key: str
    group: Literal["rules", "flow", "other"]
    built_in: bool
    enabled: bool
    # Admin-set names by language; a missing language shows the default
    # name (built-in blocks) or the other language's name (added blocks).
    names: dict[str, str]
    flow_key: str | None


class PromptOverview(BaseModel):
    items: list[PromptItem]
    # Every block in display order (see registry.load_modules).
    modules: list[PromptModuleItem]
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
    intent: DialogueIntent = DialogueIntent.VENT
    # Forces the self-kindness flow, as a high self-criticism level would.
    self_kindness: bool = False
    # Unsaved draft text per prompt key, used instead of the saved version.
    overrides: dict[str, str] = {}
    history: list[PreviewMessage] = Field(default=[], max_length=40)
    message: str = Field(min_length=1, max_length=4000)


class PromptPreviewResponse(BaseModel):
    reply_text: str
    candidates: list[CandidateCard]
    system_prompt: str
    prompt_versions: dict[str, int]
