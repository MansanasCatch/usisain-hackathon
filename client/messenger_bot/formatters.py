"""formatters.py — turns the aggregated pipeline result into a sequence of
short chat messages (Messenger has no concept of "progressive UI", so this
is the bot's equivalent: one message per step, sent in order as they'd
have appeared on screen in the extension/webapp)."""


def format_step_messages(results: dict) -> list[str]:
    messages = []

    step1 = results.get("step1") or {}
    if step1.get("insight"):
        messages.append(f"🔍 AI Insights\n{step1['insight']}")

    step2 = results.get("step2") or {}
    if step2.get("applicable") is False:
        pass  # text-only content, nothing meaningful to show for this step
    elif step2:
        messages.append(
            f"📊 Content Analyser\n"
            f"{step2.get('real_pct', '?')}% real · {step2.get('edited_pct', '?')}% edited · "
            f"{step2.get('ai_generated_pct', '?')}% AI-generated\n\n{step2.get('explanation', '')}"
        )

    step3 = results.get("step3") or {}
    if step3:
        verdict_emoji = {"likely_true": "✅", "flagged": "⚠️", "inconclusive": "❓"}.get(step3.get("verdict"), "❓")
        messages.append(
            f"{verdict_emoji} Legit or Fake — {step3.get('verdict', 'unknown')} "
            f"(score {step3.get('score', '?')}/100)\n\n{step3.get('explanation', '')}"
        )

    step4 = results.get("step4") or {}
    if step4.get("actions"):
        actions_text = "\n".join(f"• {a}" for a in step4["actions"])
        messages.append(f"📝 Actionable Items\n{actions_text}")

    step5 = results.get("step5") or {}
    if step5.get("learning_material"):
        links_text = "\n".join(step5.get("source_links", [])) or "(no source links found)"
        messages.append(f"🎓 Learnings\n{step5['learning_material']}\n\nSources:\n{links_text}")

    return messages or ["Sorry, I couldn't complete the analysis. Please try again."]
