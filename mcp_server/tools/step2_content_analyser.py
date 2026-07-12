"""
step2_content_analyser.py — breaks an image or video down into real /
edited / AI-generated percentages using pure local signal processing
(shared/visual_signals.py). No LLM, no network — the fastest step in the
pipeline and a good first target to get running end to end.

For video: each sampled frame is classified independently and the
percentages reported are the proportion of frames that fell into each
category — a segment-level view of the whole clip, not one opaque score.
"""

from PIL import Image

from shared.visual_signals import classify_frame, normalize_pct
from shared.video_utils import sample_frames, transcribe_audio


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


def analyze_image(image_path: str) -> dict:
    image = Image.open(image_path)
    result = classify_frame(image)
    real, edited, ai_gen = result["real_pct"], result["edited_pct"], result["ai_generated_pct"]

    return {
        "content_type": "image",
        "real_pct": real, "edited_pct": edited, "ai_generated_pct": ai_gen,
        "score": real,  # kept for dashboard trend compatibility: score = % real
        "verdict": _verdict(real, edited, ai_gen),
        "explanation": _explain(real, edited, ai_gen, result["signals"]),
        "details": result["signals"],
    }


def analyze_video(video_path: str, max_frames: int = 24) -> dict:
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

    explanation = (
        f"Sampled {total} frames across ~{round(duration, 1)}s of video. "
        f"{real}% of sampled frames look consistent with authentic "
        f"footage, {edited}% show signs of editing, and {ai_gen}% show "
        f"signs consistent with AI generation.\n\n"
        f"Audio was transcribed locally for context — nothing left this "
        f"machine during analysis.\n\n"
        "These are heuristic, frame-level signals meant to help you "
        "investigate further, not a definitive verdict on the whole video."
    )

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


def analyze_content(file_path: str, content_type: str) -> dict:
    """Entry point the MCP tool calls — dispatches on content_type so the
    tool registration in server.py doesn't need two separate tools."""
    if content_type == "video":
        return analyze_video(file_path)
    return analyze_image(file_path)
