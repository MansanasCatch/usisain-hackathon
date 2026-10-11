import os
import cv2
from mcp_server.steps.base import BaseStep, Step1Input, Step1Output
from mcp_server.prompts.step1_prompts import (
    SYSTEM_PROMPT,
    LANGUAGE_INSTRUCTIONS,
    SECURITY_GUARDRAIL,
)
from mcp_server.services.llm import get_provider


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
        if language in LANGUAGE_INSTRUCTIONS:
            system_prompt = f"{SYSTEM_PROMPT} {LANGUAGE_INSTRUCTIONS[language]}"
        system_prompt = f"{system_prompt} {SECURITY_GUARDRAIL}"

        image_to_pass = None
        temp_frame_path = None
        ocr_text = ""

        if file_path and os.path.exists(file_path):
            if use_ocr:
                from mcp_server.shared.ocr_utils import extract_text as ocr_extract
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

            if provider != "ollama":
                if content_type == "image":
                    image_to_pass = file_path
                    user_prompt = (
                        f"Text content: {content_summary or '(no text provided)'}\n"
                        "Please analyze the attached image and provide a short, clear, objective summary of what is visible."
                    )
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
                    user_prompt = (
                        f"Text content: {content_summary or '(no text provided)'}\n"
                        "Please analyze the attached representative video frame and provide a short, clear, summary of the visible scene."
                    )
                else:
                    user_prompt = f"Text content: {content_summary or '(no text provided)'}"
            else:
                user_prompt = f"Text content: {content_summary or '(no text provided)'}"
        else:
            user_prompt = f"Text content: {content_summary or '(no text provided)'}"

        try:
            insight = await llm.complete(
                system_prompt, user_prompt, image_path=image_to_pass, max_tokens=256
            )
            return Step1Output(
                insight=insight,
                explanation=insight,
                ocr_text=ocr_text,
            )
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
