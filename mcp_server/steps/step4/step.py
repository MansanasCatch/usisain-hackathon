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
        if language in LANGUAGE_INSTRUCTIONS:
            system_prompt = f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTIONS[language]}"
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
            return Step4Output(actions=[])
        actions = [
            line.strip("-•1234567890. ").strip()
            for line in actions_text.splitlines()
            if line.strip()
        ]
        return Step4Output(actions=actions)
