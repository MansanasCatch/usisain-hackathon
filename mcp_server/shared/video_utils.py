"""
video_utils.py — frame sampling and local audio transcription, shared by
step 2 (content analyser) when the input is a video. Everything here runs
on-device: OpenCV reads frames directly from the file, faster-whisper
transcribes the audio track locally. Nothing is uploaded anywhere.
"""

import cv2
from PIL import Image

_whisper_model = None


def get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper_model


def sample_frames(video_path: str, max_frames: int = 24):
    cap = cv2.VideoCapture(video_path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    duration = total / fps if fps else 0
    if total <= 0:
        cap.release()
        return ([], 0)
    step = max(1, total // max_frames)
    frames = []
    idx = 0
    while idx < total and len(frames) < max_frames:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if ok:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(rgb))
        idx += step
    cap.release()
    return (frames, duration)


def transcribe_audio(video_path: str) -> str:
    try:
        model = get_whisper_model()
        segments, _info = model.transcribe(video_path, beam_size=1)
        return " ".join((seg.text.strip() for seg in segments)).strip()
    except Exception as e:
        return f"[transcription unavailable: {e}]"
