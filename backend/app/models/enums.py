import enum


class Language(str, enum.Enum):
    ZH = "zh"
    KO = "ko"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConsentCategory(str, enum.Enum):
    """Matches PRD 8.5/8.6: user decides per-category whether to store/reuse data.

    DIALOGUE_HISTORY: raw conversation turns.
    EMOTION_RECORDS: structured situation-emotion-need-belief / SEB entries.
    CULTURE_ADAPTATION_INFO: acculturation problem-type tags, recurring-pressure context.
    PERSONALIZATION: whether any stored, consented data may be reused to tailor
        future turns (design principle 9). Independent of whether data is stored at all.
    """

    DIALOGUE_HISTORY = "dialogue_history"
    EMOTION_RECORDS = "emotion_records"
    CULTURE_ADAPTATION_INFO = "culture_adaptation_info"
    PERSONALIZATION = "personalization"


class RecordType(str, enum.Enum):
    SITUATION_EMOTION_BEHAVIOR = "situation_emotion_behavior"
    CAUSE_INTERPRETATION = "cause_interpretation"
    VALUE_GOAL = "value_goal"
    SELF_KINDNESS = "self_kindness"
    SELF_ENCOURAGEMENT = "self_encouragement"
    RECOVERY_PLAN = "recovery_plan"
    WEEKLY_REFLECTION = "weekly_reflection"


class DialogueIntent(str, enum.Enum):
    """What the user currently needs — design principle 10.1 / 10.4."""

    VENT = "vent"                 # 倾诉 / 토로
    ORGANIZE = "organize"         # 整理情绪 / 정리
    STABILIZE = "stabilize"       # 稳定状态 / 안정화
    INFORMATION = "information"   # 寻求信息 / 정보
    METHOD = "method"             # 寻找方法 / 대처 방법


class RiskLevel(str, enum.Enum):
    NONE = "none"
    WATCH = "watch"       # elevated distress, no explicit danger signal
    CRISIS = "crisis"     # self-harm / harm-to-others / acute crisis language


class UserRole(str, enum.Enum):
    """ADMIN/SUPERADMIN can read de-identified conversation content for
    research analysis (see app/api/admin.py) — everyone starts as USER.
    There's no in-app role management; promoting someone is a direct DB
    update, on purpose, since it's rare and should stay a deliberate,
    out-of-band action rather than something reachable from the UI."""

    USER = "user"
    ADMIN = "admin"
    SUPERADMIN = "superadmin"
