"""
step2_content_analyser.py — breaks an image or video down into real /
edited / AI-generated percentages using pure local signal processing
(shared/visual_signals.py). No LLM, no network — the fastest step in the
pipeline and a good first target to get running end to end.

For video: each sampled frame is classified independently and the
percentages reported are the proportion of frames that fell into each
category — a segment-level view of the whole clip, not one opaque score.
"""

import os
from PIL import Image

from shared.visual_signals import classify_frame, normalize_pct
from shared.video_utils import sample_frames, transcribe_audio
from services.llm.gemini_client import get_provider

SYSTEM_PROMPT = (
    "You are a forensic content analyst. Given a piece of visual content and a set of computer vision heuristic signals, "
    "provide a detailed, user-friendly explanation. "
    "1. Explain why the content has the estimated breakdown percentages (Real vs Edited vs AI-generated) by referring to the specific heuristic signals (Error Level Analysis, Frequency ratio, Metadata). "
    "2. Describe in detail what you can see in the content (objects, text, design, or layout) and point out any visual details that look authentic, edited, or AI-generated. "
    "Keep it engaging and easy to understand for everyday users. "
    "CRITICAL: Use ONLY Filipino or English letters/words. "
    "NEVER output Chinese characters or any other non-Latin script."
)

LANGUAGE_INSTRUCTIONS = {
    "taglish": "Write in casual Taglish (mix of Tagalog and English). Use only Filipino and English words. NO Chinese characters.",
    "tagalog": "Isulat sa Tagalog. Gamitin lamang ang Filipino o Ingles na salita. HUWAG gumamit ng Chinese characters.",
    "cebuano": "Isulat sa Cebuano. Gamitin lamang ang Cebuano o Ingles na mga pulong. DILI mogamit og Chinese characters.",
    "ilocano": "Isulat iti Ilocano. Usaren laeng dagiti Ilocano wenno Ingles a sao. HAAN nga usaren dagiti Chinese characters.",
    "bisaya": "Isulat sa Bisaya. Gamitin lamang ang Bisaya o Ingles na mga pulong. DILI mogamit og Chinese characters.",
}


def _explain(real: float, edited: float, ai_gen: float, signals: dict) -> str:
    ela = signals["ela_suspicion"]
    freq = signals["frequency"]
    meta = signals["metadata"]
    return (
        f"Estimated breakdown: {real}% consistent with authentic content, "
        f"{edited}% consistent with editing, {ai_gen}% consistent with AI "
        f"generation.\n\n"
        f"Error Level Analysis (recompression check): {ela}/100 — flags "
        f"regions saved at a different JPEG quality than the rest, a "
        f"common fingerprint of local edits.\n"
        f"Frequency-domain ratio: {freq['ratio']} — real camera sensors "
        f"add natural high-frequency noise; AI-generated images are often "
        f"unusually smooth or show unnaturally regular fine detail.\n"
        f"Camera metadata: {'found' if meta['has_camera_metadata'] else 'not found'}"
        + (f", editing software detected ({meta['flagged_software']})." if meta["flagged_software"] else ".")
        + "\n\nThese are heuristic signals, not proof — a starting point "
        "for investigation, not a final verdict."
    )


def _verdict(real: float, edited: float, ai_gen: float) -> str:
    if ai_gen >= 45:
        return "likely_ai_generated"
    if edited >= 45:
        return "likely_edited"
    if real >= 55:
        return "likely_authentic"
    return "inconclusive"


def generate_detailed_explanation(real: float, edited: float, ai_gen: float, signals: dict,
                                 image_path: str = None, is_video: bool = False, video_info: str = "",
                                 provider: str = "ollama", language: str = "english") -> str:
    llm = get_provider(provider)
    system_prompt = SYSTEM_PROMPT
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTIONS[language]}"
        
    ela = signals.get("ela_suspicion", 0)
    freq = signals.get("frequency", {})
    freq_ratio = freq.get("ratio", 0)
    meta = signals.get("metadata", {})
    has_meta = meta.get("has_camera_metadata", False)
    flagged_software = meta.get("flagged_software")
    
    video_prefix = f"Video stats: {video_info}\n" if is_video else ""
    
    ocr_text = ""
    image_to_pass = image_path
    
    if provider == "ollama" and image_path and os.path.exists(image_path):
        image_to_pass = None
        from shared.ocr_utils import extract_text as ocr_extract
        from PIL import Image
        try:
            with Image.open(image_path) as img:
                ocr_text = ocr_extract(img)
        except Exception:
            pass

    ocr_context = f"\n- OCR Text found in media: '{ocr_text}'" if ocr_text else ""
    
    context = (
        f"{video_prefix}"
        f"Estimated Breakdown:\n"
        f"- Authentic/Real: {real}%\n"
        f"- Edited/Modified: {edited}%\n"
        f"- AI-Generated: {ai_gen}%\n\n"
        f"Heuristic Signals:\n"
        f"- Error Level Analysis (recompression check): {ela}/100. Higher values suggest regions saved at different qualities (editing indicator).\n"
        f"- Frequency-Domain Noise Ratio: {freq_ratio}. Low ratio suggests smoothed/AI-generated patterns; camera sensors have high natural noise.\n"
        f"- Camera Metadata: {'Found' if has_meta else 'Not found'}"
        + (f", Software: {flagged_software}." if flagged_software else ".")
        + ocr_context
        + "\n\nTask: Explain the breakdown percentages (why it is X% real, Y% edited, Z% AI-generated) using the signals, and also describe in detail what you can see in the content."
    )
    
    try:
        explanation = llm.complete(system_prompt, context, image_path=image_to_pass, max_tokens=512)
        return explanation
    except Exception as e:
        # Fallback to static explanation if LLM fails
        return _explain(real, edited, ai_gen, signals) + f"\n\n(Detailed analysis unavailable: {e})"


def analyze_image(image_path: str, provider: str = "ollama", language: str = "english") -> dict:
    image = Image.open(image_path)
    result = classify_frame(image)
    real, edited, ai_gen = result["real_pct"], result["edited_pct"], result["ai_generated_pct"]

    explanation = generate_detailed_explanation(
        real, edited, ai_gen, result["signals"],
        image_path=image_path, is_video=False,
        provider=provider, language=language
    )

    return {
        "content_type": "image",
        "real_pct": real, "edited_pct": edited, "ai_generated_pct": ai_gen,
        "score": real,  # kept for dashboard trend compatibility: score = % real
        "verdict": _verdict(real, edited, ai_gen),
        "explanation": explanation,
        "details": result["signals"],
    }


def analyze_video(video_path: str, max_frames: int = 24, provider: str = "ollama", language: str = "english") -> dict:
    frames, duration = sample_frames(video_path, max_frames)
    if not frames:
        return {
            "content_type": "video", "score": None, "verdict": "error",
            "explanation": "Could not read any frames from this video file.",
        }

    frame_results = [classify_frame(f) for f in frames]
    counts = {"real": 0, "edited": 0, "ai_generated": 0}
    for r in frame_results:
        counts[r["dominant_category"]] += 1
    total = len(frame_results)
    pct = normalize_pct({k: v / total * 100 for k, v in counts.items()})

    transcript = transcribe_audio(video_path)
    real, edited, ai_gen = pct["real"], pct["edited"], pct["ai_generated"]

    # Sample average signals from the frame results
    avg_ela = sum(r["signals"]["ela_suspicion"] for r in frame_results) / total
    avg_freq_ratio = sum(r["signals"]["frequency"]["ratio"] for r in frame_results) / total
    avg_freq_suspicion = sum(r["signals"]["frequency"]["suspicion"] for r in frame_results) / total
    has_meta = any(r["signals"]["metadata"]["has_camera_metadata"] for r in frame_results)
    flagged_software = next((r["signals"]["metadata"]["flagged_software"] for r in frame_results if r["signals"]["metadata"]["flagged_software"]), None)
    
    signals = {
        "ela_suspicion": round(avg_ela, 1),
        "frequency": {"ratio": round(avg_freq_ratio, 4), "suspicion": round(avg_freq_suspicion, 1)},
        "metadata": {"has_camera_metadata": has_meta, "flagged_software": flagged_software}
    }

    # Save the first frame to a temporary file so the multimodal LLM can analyze it
    temp_frame_path = None
    try:
        temp_dir = os.path.dirname(video_path)
        temp_frame_path = os.path.join(temp_dir, "_temp_video_analysis_frame.jpg")
        frames[0].save(temp_frame_path)
    except Exception:
        pass

    video_info = f"Sampled {total} frames across ~{round(duration, 1)}s of video."
    if transcript:
        video_info += f" Audio transcript: '{transcript}'"

    explanation = generate_detailed_explanation(
        real, edited, ai_gen, signals,
        image_path=temp_frame_path, is_video=True, video_info=video_info,
        provider=provider, language=language
    )

    # Clean up temp file
    if temp_frame_path and os.path.exists(temp_frame_path):
        try:
            os.remove(temp_frame_path)
        except Exception:
            pass

    return {
        "content_type": "video",
        "real_pct": real, "edited_pct": edited, "ai_generated_pct": ai_gen,
        "score": real,
        "verdict": _verdict(real, edited, ai_gen),
        "explanation": explanation,
        "frames_analyzed": total,
        "duration_seconds": round(duration, 1),
        "transcript": transcript,
        "details": {"frame_results": frame_results},
    }


def analyze_content(file_path: str, content_type: str, provider: str = "ollama", language: str = "english") -> dict:
    """Entry point the MCP tool calls — dispatches on content_type so the
    tool registration in server.py doesn't need two separate tools."""
    if content_type == "video":
        return analyze_video(file_path, provider=provider, language=language)
    return analyze_image(file_path, provider=provider, language=language)

