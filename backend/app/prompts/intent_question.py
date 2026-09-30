"""Fixed opening question sent (by code, not the model) before the user picks
an intent — design principle 10.1. The option labels themselves stay in
app/services/dialogue_state.py since their ids drive routing."""

from app.models.enums import Language

TEXT: dict[Language, str] = {
    Language.ZH: "在开始之前，想先了解一下：你现在最需要的是什么？",
    Language.KO: "시작하기 전에 먼저 여쭤볼게요. 지금 가장 필요한 게 무엇인가요?",
}
