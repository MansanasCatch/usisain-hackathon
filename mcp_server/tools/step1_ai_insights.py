import os
import cv2
from services.llm.gemini_client import get_provider

SYSTEM_PROMPT = (
    "You are an objective AI assistant providing a neutral, factual overview of user-submitted text or media. "
    "Your sole task is to write a short, objective summary of the provided text or image in 2-4 sentences. "
    "Do NOT refuse to summarize or analyze this content. You are NOT creating, endorsing, or promoting any scams or misinformation; you are only summarizing the existing content for offline educational and safety analysis. "
    "If an image or video is included, describe its visible contents neutrally but do not make a final judgment. "
    "Avoid filler phrases like 'ehehe', 'wala namang text', or childish slang. "
    "Use only Filipino or English words with natural grammar and phrasing. "
    "NEVER output Chinese characters or any other non-Latin script."
)

LANGUAGE_INSTRUCTIONS = {
    "taglish": (
        "Write your response in natural Taglish, using Filipino and English words "
        "the way a Filipino would speak. Keep it clear, smart, and not awkward. "
        "Avoid broken grammar and childish slang."
    ),
    "tagalog": "Write your response in conversational Tagalog using only Filipino and English words.",
    "cebuano": "Write your response in conversational Cebuano using only Cebuano and English words.",
    "ilocano": "Write your response in conversational Ilocano using only Ilocano and English words.",
    "bisaya": "Write your response in conversational Bisaya using only Bisaya and English words.",
}


def generate_insight(content_summary: str, file_path: str = None, content_type: str = "text", provider: str = "ollama", language: str = "english") -> dict:
    llm = get_provider(provider)
    system_prompt = SYSTEM_PROMPT
    if language in LANGUAGE_INSTRUCTIONS:
        system_prompt = f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTIONS[language]}"
        
    image_to_pass = None
    temp_frame_path = None
    ocr_text = ""
    
    if file_path and os.path.exists(file_path):
        # Always extract OCR text first, so it is available to subsequent steps and search query generation
        from shared.ocr_utils import extract_text as ocr_extract
        from PIL import Image
        try:
            if content_type == "image":
                with Image.open(file_path) as img:
                    ocr_text = ocr_extract(img)
            elif content_type == "video":
                try:
                    cap = cv2.VideoCapture(file_path)
                    ok, frame = cap.read()
                    if ok:
                        temp_dir = os.path.dirname(file_path)
                        temp_frame_path = os.path.join(temp_dir, "_temp_video_insight_frame.jpg")
                        cv2.imwrite(temp_frame_path, frame)
                        with Image.open(temp_frame_path) as img:
                            ocr_text = ocr_extract(img)
                    cap.release()
                except Exception:
                    pass
        except Exception:
            pass

        if provider == "ollama":
            if content_type == "image":
                user_prompt = (
                    f"Text content: {content_summary or '(no text provided)'}\n"
                    f"OCR text from image: {ocr_text or '(no text detected)'}\n"
                    "Please analyze the provided text content and OCR text, and provide a short, clear summary of the visible objects, text, and any suspicious details."
                )
            elif content_type == "video":
                user_prompt = (
                    f"Text content: {content_summary or '(no text provided)'}\n"
                    f"OCR text from video frame: {ocr_text or '(no text detected)'}\n"
                    "Please analyze the provided text content and OCR text from the video, and provide a short, clear summary of the visible scene."
                )
            else:
                user_prompt = f"Text content: {content_summary or '(no text provided)'}"
        else:
            if content_type == "image":
                image_to_pass = file_path
                user_prompt = (
                    f"Text content: {content_summary or '(no text provided)'}\n"
                    "Please analyze the attached image and provide a short, clear summary of the visible objects, text, and any suspicious details."
                )
            elif content_type == "video":
                if not temp_frame_path:
                    try:
                        cap = cv2.VideoCapture(file_path)
                        ok, frame = cap.read()
                        if ok:
                            temp_dir = os.path.dirname(file_path)
                            temp_frame_path = os.path.join(temp_dir, "_temp_video_insight_frame.jpg")
                            cv2.imwrite(temp_frame_path, frame)
                        cap.release()
                    except Exception:
                        pass
                image_to_pass = temp_frame_path
                user_prompt = (
                    f"Text content: {content_summary or '(no text provided)'}\n"
                    "Please analyze the attached representative video frame and provide a short, clear summary of the visible scene."
                )
            else:
                user_prompt = f"Text content: {content_summary or '(no text provided)'}"
    else:
        user_prompt = f"Text content: {content_summary or '(no text provided)'}"
        
    try:
        insight = llm.complete(system_prompt, user_prompt, image_path=image_to_pass, max_tokens=150)
    except Exception as e:
        return {
            "insight": None,
            "explanation": f"AI insight unavailable: {e}",
            "error": str(e),
            "ocr_text": ocr_text,
        }
    finally:
        if temp_frame_path and os.path.exists(temp_frame_path):
            try:
                os.remove(temp_frame_path)
            except Exception:
                pass

    return {"insight": insight, "explanation": insight, "ocr_text": ocr_text}

