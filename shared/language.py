"""Language helpers for Normalizer / Medical Lang Bridge (beginner-friendly).

Primary focus comes from configs/rules.yaml → language_codes_supported
(same set as mock_ehr/seed.py comments): en, es, hi, de, fr, nl

  Seed / sample examples:
    en — P1019, P1023 (and clean English cases)
    es — P1020 (Spanish)
    hi — P1021, P1015 (Hindi)
    nl — P1022, P1024 (Dutch)
    de — P1016 (German)
    fr — P1017 (French)

Fallback: if a new / unexpected language shows up, we still translate via
Sampling with nova-lite (SSoT §3.6 multilingual hint). We never reject the case.
"""

from __future__ import annotations

import re

# Default if rules.yaml cannot be read (keeps imports safe in tiny scripts)
_DEFAULT_PRIMARY = ("en", "es", "hi", "de", "fr", "nl")

PRIMARY_LANGUAGE_LABELS = {
    "en": "English",
    "es": "Spanish",
    "hi": "Hindi",
    "de": "German",
    "fr": "French",
    "nl": "Dutch",
}

# Aliases people (or Extractor) might put in the language field → short code
_PRIMARY_ALIASES = {
    "en": "en",
    "eng": "en",
    "english": "en",
    "es": "es",
    "spa": "es",
    "spanish": "es",
    "español": "es",
    "espanol": "es",
    "hi": "hi",
    "hin": "hi",
    "hindi": "hi",
    "de": "de",
    "deu": "de",
    "ger": "de",
    "german": "de",
    "deutsch": "de",
    "fr": "fr",
    "fra": "fr",
    "fre": "fr",
    "french": "fr",
    "français": "fr",
    "francais": "fr",
    "nl": "nl",
    "nld": "nl",
    "dut": "nl",
    "dutch": "nl",
    "nederlands": "nl",
    "auto": "auto",
    "unknown": "auto",
    "und": "auto",
    "": "auto",
}


def _load_primary_from_rules() -> tuple[str, ...]:
    """Read language_codes_supported from rules.yaml (SSoT §6.2)."""
    try:
        import yaml

        from shared.settings import get_path

        with open(get_path("rules_yaml"), encoding="utf-8") as f:
            rules = yaml.safe_load(f) or {}
        codes = (
            rules.get("normalization_standards", {}) or {}
        ).get("language_codes_supported")
        if codes:
            return tuple(str(c).strip().lower() for c in codes if str(c).strip())
    except Exception:
        pass
    return _DEFAULT_PRIMARY


# Resolved once at import — same tuple as rules.yaml in a healthy checkout
PRIMARY_LANGUAGE_CODES = _load_primary_from_rules()


def get_primary_language_codes() -> tuple[str, ...]:
    """Return primary codes (re-reads rules so tests can refresh if needed)."""
    return _load_primary_from_rules()


def normalize_lang_code(raw: str | None) -> str:
    """Turn a messy label into a short code.

    Primary languages get clean aliases (Hindi → hi).
    Unknown labels stay as lowercase text (or 'auto' if empty) so the
    fallback path can still run.
    """
    if raw is None:
        return "auto"
    text = str(raw).strip().lower()
    if not text:
        return "auto"
    if text in _PRIMARY_ALIASES:
        return _PRIMARY_ALIASES[text]
    if re.fullmatch(r"[a-z]{2,3}", text):
        return text
    return text


def is_primary_language(source_language: str | None) -> bool:
    """True when the language is one of the seed/rules primary set."""
    return normalize_lang_code(source_language) in get_primary_language_codes()


def is_english(source_language: str | None) -> bool:
    """True only when we are sure the source is English."""
    return normalize_lang_code(source_language) == "en"


def needs_multilingual_model(source_language: str | None) -> bool:
    """True → Sampling hint nova-lite (SSoT §3.6).

    English (primary) → command-r-plus.
    Other primary langs (es/hi/de/fr/nl) → nova-lite.
    Fallback / auto / unknown → also nova-lite (so new languages still work).
    """
    return not is_english(source_language)


def language_path(source_language: str | None) -> str:
    """Return 'primary' or 'fallback' for logging / notes (beginner-clear)."""
    code = normalize_lang_code(source_language)
    if code in get_primary_language_codes():
        return "primary"
    return "fallback"


def _script_guess_primary(text: str) -> str | None:
    """Guess only among primary languages when the language field is missing.

    Hindi is the one primary language with a distinctive script (Devanagari).
    es / de / fr / nl / en all use Latin script — for those we rely on the
    Extractor's language field (or leave 'auto' for the LLM).
    """
    if not text:
        return None
    sample = text[:4000]
    letters = [ch for ch in sample if ch.isalpha()]
    if not letters:
        return None
    devanagari = sum(1 for ch in letters if "\u0900" <= ch <= "\u097F")
    if (devanagari / len(letters)) > 0.15:
        return "hi"
    return None


def _collect_text_from_extraction(extraction: dict) -> str:
    """Pull readable strings out of an ExtractionResult-shaped dict."""
    chunks: list[str] = []

    def walk(value) -> None:
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(extraction or {})
    return "\n".join(chunks)


def detect_source_language(extraction: dict) -> str:
    """Pick a source language for this extraction (any patient_id).

    Order (beginner-simple):
      1. Explicit language on discharge / lab / bill (normalized)
      2. Devanagari script → Hindi (primary)
      3. 'auto' → Lang Bridge detects during Sampling
    """
    for key in ("discharge", "lab", "bill"):
        section = extraction.get(key) or {}
        if isinstance(section, dict):
            lang = normalize_lang_code(section.get("language"))
            if lang and lang != "auto":
                return lang

    guess = _script_guess_primary(_collect_text_from_extraction(extraction))
    if guess:
        return guess
    return "auto"
