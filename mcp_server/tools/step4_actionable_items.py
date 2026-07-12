"""step4_actionable_items.py — turns the findings from steps 1-3 into
concrete, specific next steps. This is what makes the tool useful in the
moment, not just informative after the fact."""

from services.llm.gemini_client import get_provider

SYSTEM_PROMPT = (
    "You generate concrete, specific action items for someone who just "
    "had a piece of content checked for scams/misinformation/AI "
    "generation. Given the findings, list 3-5 short, specific next steps "
    "(not generic advice like 'be careful online'). If it's a financial "
    "scam pattern, mention concrete steps like verifying directly through "
    "the official app/hotline, not the link/number in the message. If "
    "it's misinformation, suggest specific ways to verify. If it looks "
    "legitimate, say so plainly and give one step to double-check anyway. "
    "Output as a short list, one action per line, no preamble."
)

LANGUAGE_INSTRUCTIONS = {
    "taglish": "Write each action item in casual Taglish.",
    "tagalog": "Write each action item in conversational Tagalog.",
    "cebuano": "Write each action item in conversational Cebuano.",
    "ilocano": "Write each action item in conversational Ilocano.",
}


def generate_actions(step1_result: dict, step2_result: dict, step3_result: dict,
                      provider: str = "ollama", language: str = "english") -> dict:
    llm = get_provider(provider)
    system_prompt = SYSTEM_PROMPT
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTIONS[language]}"
    context = (
        f"AI insight: {step1_result.get('insight', 'n/a')}\n"
        f"Content analysis: {step2_result.get('verdict', 'n/a')} "
        f"(real {step2_result.get('real_pct', '?')}%, edited {step2_result.get('edited_pct', '?')}%, "
        f"AI-generated {step2_result.get('ai_generated_pct', '?')}%)\n"
        f"Legit-or-fake verdict: {step3_result.get('verdict', 'n/a')}, score {step3_result.get('score', '?')}\n"
        f"Legit-or-fake explanation: {step3_result.get('explanation', 'n/a')}"
    )
    try:
        actions_text = llm.complete(system_prompt, context)
    except Exception as e:
        return {"actions": [], "explanation": f"Action generation unavailable: {e}"}

    actions = [line.strip("-• ").strip() for line in actions_text.splitlines() if line.strip()]
    return {"actions": actions, "explanation": actions_text}
