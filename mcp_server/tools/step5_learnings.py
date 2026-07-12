"""step5_learnings.py — the step that makes this a literacy tool, not
just a detector. Generates a short educational explanation of the
pattern involved (why this type of scam/misinformation/AI content works)
plus links the user can actually go learn more from."""

from services.llm.gemini_client import get_provider

SYSTEM_PROMPT = (
    "You write short educational material for someone who just had a "
    "piece of content checked for scams/misinformation/AI generation. "
    "Given the findings, explain in 3-5 sentences the general PATTERN at "
    "play (e.g. how this type of scam typically works, why AI-generated "
    "images tend to have certain artifacts, why a claim like this spreads) "
    "so the reader can recognize it themselves next time — teach the "
    "underlying mechanism, not just this one instance. Plain language, "
    "no jargon without explaining it. End with one sentence naming a "
    "credible general resource type (e.g. 'your bank's official app or "
    "hotline', 'the Philippine National Police Anti-Cybercrime Group') "
    "relevant to this pattern."
)

LANGUAGE_INSTRUCTIONS = {
    "taglish": "Write the explanation in casual Taglish.",
    "tagalog": "Write the explanation in conversational Tagalog.",
    "cebuano": "Write the explanation in conversational Cebuano.",
    "ilocano": "Write the explanation in conversational Ilocano.",
}


def generate_learnings(step1_result: dict, step2_result: dict, step3_result: dict,
                        provider: str = "ollama", language: str = "english") -> dict:
    llm = get_provider(provider)
    system_prompt = SYSTEM_PROMPT
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTIONS[language]}"
    context = (
        f"AI insight: {step1_result.get('insight', 'n/a')}\n"
        f"Content analysis verdict: {step2_result.get('verdict', 'n/a')}\n"
        f"Legit-or-fake verdict: {step3_result.get('verdict', 'n/a')}\n"
        f"Legit-or-fake explanation: {step3_result.get('explanation', 'n/a')}\n"
        f"Top sources: {[s.get('url') for s in step3_result.get('sources', [])[:3]]}"
    )
    try:
        material = llm.complete(system_prompt, context)
    except Exception as e:
        return {"learning_material": None, "explanation": f"Learnings unavailable: {e}", "source_links": []}

    source_links = [s["url"] for s in step3_result.get("sources", [])[:3] if s.get("url")]
    return {"learning_material": material, "explanation": material, "source_links": source_links}
