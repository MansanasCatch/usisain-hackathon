"""
step1_ai_insights.py — the fastest useful thing the pipeline can produce:
a single LLM call giving an initial contextual read of the content before
any deeper (and slower) analysis runs. This is what shows up on screen
first while steps 2-5 are still working.
"""

from services.llm.gemini_client import get_provider

SYSTEM_PROMPT = (
    "You are the first-pass reviewer in a scam and misinformation detection "
    "tool used by Filipino internet users. Given a piece of content (a "
    "claim, caption, or description of an image/video), give a short "
    "initial read: what is this content claiming or showing, what stands "
    "out about it (urgency language, unofficial links, emotional framing, "
    "unusual formatting), and what would be worth checking further. "
    "2-4 sentences. Do not make a final judgment — that comes later in the "
    "pipeline. Be plain and direct, no hedging filler."
)

# Appended to the system prompt based on the client's requested language.
# "english" adds nothing — the base prompt is already plain English.
LANGUAGE_INSTRUCTIONS = {
    "taglish": "Write your response in casual Taglish, the way a Filipino "
               "user would actually text a friend — not formal English.",
    "tagalog": "Write your response in conversational Tagalog.",
    "cebuano": "Write your response in conversational Cebuano.",
    "ilocano": "Write your response in conversational Ilocano.",
}


def generate_insight(content_summary: str, provider: str = "ollama", language: str = "english") -> dict:
    llm = get_provider(provider)
    system_prompt = SYSTEM_PROMPT
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTIONS[language]}"
    try:
        insight = llm.complete(system_prompt, content_summary)
    except Exception as e:
        return {
            "insight": None,
            "explanation": f"AI insight unavailable: {e}",
            "error": str(e),
        }

    return {"insight": insight, "explanation": insight}
