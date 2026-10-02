"""Purpose question sent (by code, not the model) right after the user's
first message and before any LLM turn — design principle 10.1; per the
flowchart the user describes their situation first, then picks a purpose.
The option labels themselves stay in app/services/dialogue_state.py since
their ids drive routing."""

from app.models.enums import Language

TEXT: dict[Language, str] = {
    Language.ZH: "谢谢你愿意说出来。为了更好地陪你，想先确认一下：你现在最需要的是什么？",
    Language.KO: "이야기해 주셔서 고마워요. 더 잘 함께하기 위해 먼저 여쭤볼게요. 지금 가장 필요한 게 무엇인가요?",
}
