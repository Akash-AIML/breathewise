"""Input normalization, injection detection, and grounding checks for the assistant."""

import logging
import re
import unicodedata

# Preserve the original logger category after the module split.
logger = logging.getLogger("app.services.llm_assistant_service")

# Patterns indicating potential adversarial prompt injection or role hijacking.
# Matching happens on a heavily normalized string, not the raw user input.
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts|directives)",
    r"disregard\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts|directives)",
    r"act\s+as\s+(an\s+|a\s+)?(unrestricted|jailbroken|developer|dan|evil|uncensored)",
    r"override\s+(the\s+)?(risk|aqi|system|safety|policy|rules)",
    r"forget\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(rules|instructions)",
    r"you\s+are\s+now\s+(an\s+|a\s+)?(unrestricted|jailbroken|developer|dan)",
    r"system\s*:\s*you\s+(must|are|will|shall)",
    r"reveal\s+(your|the)\s+(system\s+)?prompt",
    r"print\s+(your|the)\s+(system\s+)?prompt",
    r"pretend\s+(to\s+be|you\s+are)\s+(an?\s+)?(system|developer|admin)",
    r"bypass\s+(the\s+)?(safety|security|validation|guardrails)",
]

# Structural control tokens used by common chat templates. These are never
# legitimate in a user question about air quality.
INJECTION_MARKERS = (
    "<|im_start|>",
    "<|im_end|>",
    "<|system|>",
    "<|assistant|>",
    "[inst]",
    "[/inst]",
    "<<sys>>",
    "<</sys>>",
    "### system",
    "### assistant",
    "[system]",
    "role:system",
    '"role":"system"',
)

# Common homoglyphs that could be used to evade a literal keyword check.
# Encoded as explicit Unicode escapes to prevent confusable-character lint warnings.
HOMOGLYPHS = str.maketrans(
    {
        "\u0430": "a",  # Cyrillic small letter a
        "\u0435": "e",  # Cyrillic small letter ie
        "\u043e": "o",  # Cyrillic small letter o
        "\u0440": "p",  # Cyrillic small letter er
        "\u0441": "c",  # Cyrillic small letter es
        "\u0445": "x",  # Cyrillic small letter ha
        "\u0443": "y",  # Cyrillic small letter u
        "\u0456": "i",  # Cyrillic small letter byelorussian-ukrainian i
        "\u0458": "j",  # Cyrillic small letter je
        "\u0455": "s",  # Cyrillic small letter dze
        "\u04bb": "h",  # Cyrillic small letter shha
        "\u0501": "d",  # Cyrillic small letter komi de
        "\u0261": "g",  # Latin small letter script g
        "\u0144": "n",  # Latin small letter n with acute
        "\u2170": "i",  # Small roman numeral one
        "\u217c": "l",  # Small roman numeral fifty
        "\uff10": "0",  # Fullwidth digit zero
        "\uff11": "1",  # Fullwidth digit one
    }
)


def normalize_for_screening(text: str) -> str:
    """Canonicalize user text so spacing, unicode and homoglyph tricks cannot evade matching."""
    text = unicodedata.normalize("NFKC", text)
    # Replace zero-width/control characters with a space rather than deleting
    # them, so "ignore\u200ball" cannot become the unmatched token "ignoreall".
    text = "".join(
        char if unicodedata.category(char) not in {"Cf", "Cc"} or char in {" ", "\n", "\t"} else " "
        for char in text
    )
    text = text.translate(HOMOGLYPHS)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def screen_for_prompt_injection(user_query: str) -> bool:
    """
    Returns True if the query contains suspicious adversarial injection patterns.

    This is a defence-in-depth signal, not the primary guarantee. The user
    query is always sent as *user-role data*, and every LLM field that must
    remain trustworthy (AQI, risk, actions, provenance) is overwritten with
    validated values in ``_build_grounded_explanation``.
    """
    normalized = normalize_for_screening(user_query)
    if any(marker in normalized for marker in INJECTION_MARKERS):
        logger.warning("Prompt injection control token detected in user query")
        return True
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, normalized):
            logger.warning("Prompt injection pattern detected in user query")
            return True
    return False


def answer_is_grounded(answer: str, validated_aqi: int | None) -> bool:
    """Reject LLM answers that assert an AQI other than the validated value."""
    asserted = [int(value) for value in re.findall(r"\bAQI\b[^0-9]{0,16}(\d{1,3})", answer, re.I)]
    if validated_aqi is None:
        return not asserted
    return all(value == validated_aqi for value in asserted)
