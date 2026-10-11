"""Model capability and vision support utilities."""

VISION_KEYWORDS = (
    "vision",
    "moondream",
    "llava",
    "bakllava",
    "minicpm-v",
    "scout",
    "multimodal",
    "-vl",
    "vl-",
    "_vl",
    "vl_",
    "qwen2-vl",
    "llama-3.2-11b-vision",
    "llama-3.2-90b-vision",
)


def model_supports_vision(provider: str, model_name: str | None = None) -> bool:
    """Determine whether a given model supports multimodal image vision.

    - Google Gemini: All active Gemini models natively support vision.
    - Grok / Groq / OpenAI compatible: Vision models have vision/multimodal keywords.
    - Ollama: Models with vision architectures (moondream, llava, etc.) support vision.
    """
    p = (provider or "").strip().lower()
    if p == "gemini":
        return True

    name = (model_name or "").strip().lower()
    if not name:
        return False

    return any(k in name for k in VISION_KEYWORDS)


def get_text_only_model_notice(model_name: str, language: str) -> str:
    """Return a localized friendly message when a pure text model is fed an image without text."""
    lang = (language or "english").strip().lower()
    clean_name = model_name or "active model"

    if lang in ("tagalog", "taglish"):
        return (
            f"Larawan na walang text overlay ang natukoy. Ang aktibong modelo ({clean_name}) ay text-only at walang visual encoder. "
            f"Para sa visual na pagsusuri ng larawan, lumipat sa isang Vision model (tulad ng Google Gemini o modelo na may 👁️ Vision badge) sa dropdown sa itaas. "
            f"Ang pagsusuri ng digital forensics ay matagumpay na nakumpleto sa Step 2."
        )
    if lang in ("cebuano", "bisaya"):
        return (
            f"Hulagway nga walay text overlay ang nakit-an. Ang aktibong modelo ({clean_name}) kay text-only ug walay visual encoder. "
            f"Aron masusi ang visual nga bahin, mobalhin sa usa ka Vision model (sama sa Google Gemini o modelo nga dunay 👁️ Vision badge) sa dropdown sa ibabaw. "
            f"Ang digital forensics analysis malampusong nahuman sa Step 2."
        )
    if lang == "ilocano":
        return (
            f"Ladawan nga awan ti text overlay ti nasarakan. Ti agdama a modelo ({clean_name}) ket text-only ken awan ti visual encoder na. "
            f"Tapno ma-analisar ti visual elements, umakar iti Vision model (kas iti Google Gemini wenno modelo nga addaan 👁️ Vision badge) iti dropdown iti ngato. "
            f"Ti digital forensics analysis ket sibaballigi a nakumpleto iti Step 2."
        )

    return (
        f"Visual image without text overlay detected. The active model ({clean_name}) is text-only and does not possess a visual encoder. "
        f"To analyze visual image elements, switch to a Vision model (such as Google Gemini or a model with the 👁️ Vision badge) in the top dropdown. "
        f"Digital forensic analysis was completed in Step 2."
    )
