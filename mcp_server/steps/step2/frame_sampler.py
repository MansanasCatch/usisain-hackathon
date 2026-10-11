from mcp_server.shared.video_utils import sample_frames, transcribe_audio
from mcp_server.shared.visual_signals import classify_frame, normalize_pct


def process_video_frames(video_path: str, max_frames: int = 24):
    frames, duration = sample_frames(video_path, max_frames)
    if not frames:
        return (None, duration, None, None, None, None)
    frame_results = [classify_frame(f) for f in frames]
    counts = {"real": 0, "edited": 0, "ai_generated": 0}
    for r in frame_results:
        counts[r["dominant_category"]] += 1
    total = len(frame_results)
    pct = normalize_pct({k: v / total * 100 for k, v in counts.items()})
    transcript = transcribe_audio(video_path)
    avg_ela = sum((r["signals"]["ela_suspicion"] for r in frame_results)) / total
    avg_freq_ratio = sum((r["signals"]["frequency"]["ratio"] for r in frame_results)) / total
    avg_freq_suspicion = (
        sum((r["signals"]["frequency"]["suspicion"] for r in frame_results)) / total
    )
    has_meta = any((r["signals"]["metadata"]["has_camera_metadata"] for r in frame_results))
    flagged_software = next(
        (
            r["signals"]["metadata"]["flagged_software"]
            for r in frame_results
            if r["signals"]["metadata"]["flagged_software"]
        ),
        None,
    )
    signals = {
        "ela_suspicion": round(avg_ela, 1),
        "frequency": {"ratio": round(avg_freq_ratio, 4), "suspicion": round(avg_freq_suspicion, 1)},
        "metadata": {"has_camera_metadata": has_meta, "flagged_software": flagged_software},
    }
    return (frames, duration, pct, signals, transcript, frame_results)
