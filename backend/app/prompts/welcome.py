"""Fixed welcome message shown when a new chat opens, before the user has
said anything (documents/首选提示题建议.md; flowchart step "현재 경험 및 고민
입력" comes before the purpose question). Sent by code, not the model.
Admin-editable via registry.ASSISTANT_WELCOME. The clickable starter
options under it live in app/services/dialogue_state.py."""

from app.models.enums import Language

TEXT: dict[Language, str] = {
    Language.ZH: (
        "欢迎你来到这里。今天想从哪里开始聊呢？可以说说最近让你有些在意、烦恼，或者一直放在心里的事情。"
        "不一定是什么大事，学业、生活、人际关系、家庭，或者某种说不上来的情绪，都可以慢慢说。"
    ),
    Language.KO: (
        "여기까지 와 주셔서 반가워요. 오늘은 어디서부터 이야기해 볼까요? 요즘 신경 쓰이거나 고민되는 일, "
        "혹은 마음속에 계속 담아 두었던 일을 이야기해 주셔도 좋아요. 꼭 큰일이 아니어도 괜찮아요. "
        "학업, 생활, 인간관계, 가족, 또는 뭐라고 설명하기 어려운 감정도 천천히 이야기해 주세요."
    ),
}
