from enum import Enum


class Verdict(str, Enum):
    LIKELY_TRUE = "likely_true"
    FLAGGED = "flagged"
    INCONCLUSIVE = "inconclusive"


class Provider(str, Enum):
    OLLAMA = "ollama"
    GEMINI = "gemini"
    GROK = "grok"


class Channel(str, Enum):
    EXTENSION = "extension"
    WEBAPP = "webapp"


class ContentType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    POST = "post"


class Language(str, Enum):
    ENGLISH = "english"
    TAGLISH = "taglish"
    TAGALOG = "tagalog"
    CEBUANO = "cebuano"
    ILOCANO = "ilocano"
    BISAYA = "bisaya"
