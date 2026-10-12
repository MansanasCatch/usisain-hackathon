from mcp_server.prompts.step4_prompts import (
    LANGUAGE_INSTRUCTIONS,
    SECURITY_GUARDRAIL,
    SYSTEM_PROMPT,
)
from mcp_server.services.llm import get_provider
from mcp_server.steps.base import BaseStep, Step4Input, Step4Output


class Step4ActionableItems(BaseStep):
    step_number = 4
    name = "actionable_items"

    async def run(self, input_data: Step4Input) -> Step4Output:
        step1_result = input_data.step1_result
        step2_result = input_data.step2_result
        step3_result = input_data.step3_result
        provider = input_data.provider
        language = input_data.language
        llm = get_provider(provider)
        system_prompt = SYSTEM_PROMPT
        lang_key = (language or "english").strip().lower()
        lang_inst = LANGUAGE_INSTRUCTIONS.get(lang_key, LANGUAGE_INSTRUCTIONS.get("english", ""))
        if lang_inst:
            system_prompt = f"{SYSTEM_PROMPT} {lang_inst}"
        system_prompt = f"{system_prompt} {SECURITY_GUARDRAIL}"
        verdict = step3_result.get("verdict") or "unknown"
        insight = (step1_result.get("insight") or "")[:180]
        step3_exp = (step3_result.get("explanation") or "")[:180]
        step2_applicable = step2_result.get("applicable", True)
        step2_info = ""
        if step2_applicable:
            step2_info = f"Content breakdown: real {step2_result.get('real_pct') or 0}%, edited {step2_result.get('edited_pct') or 0}%, AI-generated {step2_result.get('ai_generated_pct') or 0}%. "
        context = f"Verdict: {verdict}\nInsight: {insight}\n{step2_info}Fact-check: {step3_exp}"
        try:
            actions_text = await llm.complete(system_prompt, context, max_tokens=256)
        except Exception:
            actions_text = ""
        actions = []
        for line in actions_text.splitlines():
            cleaned = line.strip("-•1234567890. ").strip()
            if cleaned and cleaned not in ("0", ".", "null"):
                actions.append(cleaned)
        if not actions:
            if verdict == "flagged":
                actions = [
                    "Do not share or amplify this post until confirmed by reputable news organizations.",
                    "Verify the claims against official announcements or trusted fact-checking portals.",
                    "Report unverified or deceptive claims to the platform moderators.",
                ]
            else:
                actions = [
                    "Cross-reference key claims with primary sources before sharing.",
                    "Verify the original publishing date, publisher, and context.",
                ]
        return Step4Output(actions=actions)
