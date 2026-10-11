import os

import cv2

from mcp_server.prompts.step1_prompts import (
    LANGUAGE_INSTRUCTIONS,
    SECURITY_GUARDRAIL,
    SYSTEM_PROMPT,
)
from mcp_server.services.llm import get_provider
from mcp_server.steps.base import BaseStep, Step1Input, Step1Output


class Step1AIInsights(BaseStep):
    step_number = 1
    name = "ai_insights"

    async def run(self, input_data: Step1Input) -> Step1Output:
        content_summary = input_data.content_summary
        file_path = input_data.file_path
        content_type = input_data.content_type
        provider = input_data.provider
        language = input_data.language
        use_ocr = input_data.use_ocr
        llm = get_provider(provider)
        system_prompt = SYSTEM_PROMPT
        lang_key = (language or "english").strip().lower()
        lang_inst = LANGUAGE_INSTRUCTIONS.get(lang_key, LANGUAGE_INSTRUCTIONS.get("english", ""))
        if lang_inst:
            system_prompt = f"{SYSTEM_PROMPT} {lang_inst}"
        system_prompt = f"{system_prompt} {SECURITY_GUARDRAIL}"
        image_to_pass = None
        temp_frame_path = None
        ocr_text = ""
        if file_path and os.path.exists(file_path):
            if use_ocr:
                from PIL import Image

                from mcp_server.shared.ocr_utils import extract_text as ocr_extract

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
                                temp_frame_path = os.path.join(
                                    temp_dir, "_temp_step1_video_frame.jpg"
                                )
                                cv2.imwrite(temp_frame_path, frame)
                                with Image.open(temp_frame_path) as img:
                                    ocr_text = ocr_extract(img)
                            cap.release()
                        except Exception:
                            pass
                except Exception:
                    pass
            text_parts = []
            if content_summary:
                text_parts.append(f"Claim / Context: {content_summary}")
            if ocr_text:
                text_parts.append(f"Extracted image text (OCR): {ocr_text}")
            combined_text = "\n".join(text_parts).strip()

            from mcp_server.shared.model_utils import (
                get_text_only_model_notice,
                model_supports_vision,
            )

            active_model_name = (
                getattr(llm, "model", None) or getattr(llm, "text_model", None) or ""
            )
            if not active_model_name:
                if provider == "grok":
                    active_model_name = os.environ.get("GROK_MODEL", "gpt-oss-120b")
                elif provider == "gemini":
                    active_model_name = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
                elif provider == "ollama":
                    active_model_name = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")

            has_vision = model_supports_vision(provider, active_model_name)

            if has_vision:
                if content_type == "image":
                    image_to_pass = file_path
                    user_prompt = f"Text context: {combined_text or '(no text overlay)'}\nPlease analyze the attached image and provide a short, clear, objective summary of what is visible."
                elif content_type == "video":
                    if not temp_frame_path:
                        try:
                            cap = cv2.VideoCapture(file_path)
                            ok, frame = cap.read()
                            if ok:
                                temp_dir = os.path.dirname(file_path)
                                temp_frame_path = os.path.join(
                                    temp_dir, "_temp_step1_video_frame.jpg"
                                )
                                cv2.imwrite(temp_frame_path, frame)
                            cap.release()
                        except Exception:
                            pass
                    image_to_pass = temp_frame_path
                    user_prompt = f"Text context: {combined_text or '(no text overlay)'}\nPlease analyze the attached representative video frame and provide a short, clear summary of the visible scene."
                else:
                    user_prompt = f"Text content: {combined_text or '(no text provided)'}"
            else:
                if combined_text:
                    user_prompt = f"Content:\n{combined_text}\nPlease provide a short, clear, objective summary of what is conveyed in this content."
                else:
                    notice = get_text_only_model_notice(active_model_name, lang_key)
                    return Step1Output(
                        insight=notice,
                        explanation=notice,
                        ocr_text="",
                    )
        else:
            user_prompt = f"Text content: {content_summary or '(no text provided)'}"
        try:
            insight = await llm.complete(
                system_prompt, user_prompt, image_path=image_to_pass, max_tokens=256
            )
            return Step1Output(insight=insight, explanation=insight, ocr_text=ocr_text)
        except Exception as e:
            return Step1Output(
                insight=None,
                explanation=f"AI insight unavailable: {e}",
                ocr_text=ocr_text,
                error=str(e),
            )
        finally:
            if temp_frame_path and os.path.exists(temp_frame_path):
                try:
                    os.remove(temp_frame_path)
                except Exception:
                    pass
