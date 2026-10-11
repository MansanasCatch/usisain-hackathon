def compute_verdict(real: float, edited: float, ai_gen: float) -> str:
    if ai_gen >= 45:
        return "likely_ai_generated"
    if edited >= 45:
        return "likely_edited"
    if real >= 55:
        return "likely_authentic"
    return "inconclusive"


def format_static_explanation(
    real: float, edited: float, ai_gen: float, signals: dict
) -> str:
    ela = signals.get("ela_suspicion", 0)
    freq = signals.get("frequency", {})
    meta = signals.get("metadata", {})
    ratio = freq.get("ratio", 0)
    has_meta = meta.get("has_camera_metadata", False)
    flagged = meta.get("flagged_software")

    software_part = (
        f", editing software detected ({flagged})."
        if flagged
        else "."
    )
    return (
        f"Estimated breakdown: {real}% consistent with authentic content, "
        f"{edited}% consistent with editing, {ai_gen}% consistent with AI "
        f"generation.\n\n"
        f"Error Level Analysis (recompression check): {ela}/100 — flags "
        f"regions saved at a different JPEG quality than the rest, a "
        f"common fingerprint of local edits.\n"
        f"Frequency-domain ratio: {ratio} — real camera sensors "
        f"add natural high-frequency noise; AI-generated images are often "
        f"unusually smooth or show unnaturally regular fine detail.\n"
        f"Camera metadata: {'found' if has_meta else 'not found'}"
        f"{software_part}\n\nThese are heuristic signals, not proof — a starting point "
        f"for investigation, not a final verdict."
    )
