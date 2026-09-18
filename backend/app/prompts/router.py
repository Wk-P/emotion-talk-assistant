from app.models.enums import DialogueIntent, Language
from app.prompts import emotion_exploration, recovery_plan, self_kindness, stabilization
from app.prompts.base import build_system_prompt

_FLOW_MAP = {
    DialogueIntent.VENT: emotion_exploration.FLOW_INSTRUCTIONS,
    DialogueIntent.ORGANIZE: emotion_exploration.FLOW_INSTRUCTIONS,
    DialogueIntent.STABILIZE: stabilization.FLOW_INSTRUCTIONS,
    DialogueIntent.METHOD: recovery_plan.FLOW_INSTRUCTIONS,
}

# Information requests are answered directly by the safety/resource endpoint,
# not by the general LLM flow (design principle 8.4: resource info comes from
# a verified table, never AI-generated) — no prompt module needed here.


def flow_instructions_for(intent: DialogueIntent, language: Language, self_criticism_level: float) -> str:
    # Design principle 4 / 9.3: strong self-criticism preempts the routed flow
    # in favor of acceptance support.
    if self_criticism_level >= 0.5 and intent != DialogueIntent.STABILIZE:
        return self_kindness.FLOW_INSTRUCTIONS[language]

    instructions = _FLOW_MAP.get(intent, emotion_exploration.FLOW_INSTRUCTIONS)
    return instructions[language]


def build_prompt(intent: DialogueIntent, language: Language, self_criticism_level: float) -> str:
    return build_system_prompt(language, flow_instructions_for(intent, language, self_criticism_level))
