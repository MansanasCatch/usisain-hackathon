"""step4_actionable_items.py — turns findings from steps 1-3 into
concrete, specific next steps. Kept short and focused so the LLM
returns quickly with a tight list the user can act on immediately."""

from services.llm.gemini_client import get_provider

SYSTEM_PROMPT = (
    "You are a security and digital safety advisor. Based on the findings of Step 1 (AI Insights), "
    "Step 2 (Content Analyser visual breakdown), and Step 3 (Legit or Fake Authentictity fact-check), list 3-5 short, concrete "
    "action items for the user. "
    "CRITICAL: Do NOT mention specific social media handles, usernames, names of individuals, pages, or accounts (do not use '@username' or name specific individuals). Keep suggestions generic and applicable to the platform in general (e.g., use 'the posting account' instead of '@username', and 'the page that posted this' instead of naming specific organizations). "
    "CRITICAL: Tailor the recommendations based on the Verdict:\n"
    "- If the Verdict is 'likely_true' (LEGIT), the content is verified as legitimate. Do NOT recommend blocking, unfollowing, or reporting the account. Instead, recommend safe ways to engage, verifying official links, and general security hygiene (like not sharing personal/sensitive info).\n"
    "- If the Verdict is 'flagged' (FAKE), recommend defensive safety measures such as blocking the posting account, unfollowing, reporting the content, and warning others.\n"
    "- If the Verdict is 'inconclusive' (QUESTIONABLE), recommend caution, verifying information through other sources, and waiting for official confirmation before sharing.\n"
    "Keep each item brief and practical. Output ONLY the numbered list, no intro text, no extra explanation. "
    "Use natural, clear Filipino/English only. NEVER output Chinese characters or any other non-Latin script."
)

LANGUAGE_INSTRUCTIONS = {
    "taglish": "Write in casual Taglish (mix of Tagalog and English). Use only Filipino and English words. NO Chinese characters.",
    "tagalog": "Isulat sa Tagalog. Gamitin lamang ang Filipino o Ingles na salita. HUWAG gumamit ng Chinese characters.",
    "cebuano": "Isulat sa Cebuano. Gamitin lamang ang Cebuano o Ingles na mga pulong. DILI mogamit og Chinese characters.",
    "ilocano": "Isulat iti Ilocano. Usaren laeng dagiti Ilocano wenno Ingles a sao. HAAN nga usaren dagiti Chinese characters.",
    "bisaya": "Isulat sa Bisaya. Gamitin lamang ang Bisaya o Ingles na mga pulong. DILI mogamit og Chinese characters.",
}


async def generate_actions(step1_result: dict, step2_result: dict, step3_result: dict,
                     provider: str = "ollama", language: str = "english") -> dict:
    llm = get_provider(provider)
    system_prompt = SYSTEM_PROMPT
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTIONS[language]}"

    # Distill only what the LLM needs — keeps context short for speed
    verdict = step3_result.get("verdict") or "unknown"
    score = step3_result.get("score", "?")
    insight = (step1_result.get("insight") or "")[:180]
    step3_exp = (step3_result.get("explanation") or "")[:180]

    step2_applicable = step2_result.get("applicable", True)
    step2_info = ""
    if step2_applicable:
        step2_info = (
            f"Content breakdown: real {step2_result.get('real_pct') or 0}%, "
            f"edited {step2_result.get('edited_pct') or 0}%, "
            f"AI-generated {step2_result.get('ai_generated_pct') or 0}%. "
        )

    context = (
        f"Verdict: {verdict}\n"
        f"Insight: {insight}\n"
        f"{step2_info}"
        f"Fact-check: {step3_exp}"
    )

    try:
        actions_text = await llm.complete(system_prompt, context, max_tokens=256)
    except Exception as e:
        return {"actions": [], "explanation": f"Action generation unavailable: {e}"}

    actions = [line.strip("-•1234567890. ").strip() for line in actions_text.splitlines() if line.strip()]
    return {"actions": actions, "explanation": actions_text}
