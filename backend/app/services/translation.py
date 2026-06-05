"""
Context-aware localization engine.
Uses Claude (claude-opus-4-5) with:
  - rolling 5-page context window
  - per-bubble tone hints based on bubble shape
  - series glossary injection
  - structured JSON output
"""
import json
import re
import anthropic
import structlog
from app.core.config import get_settings

log = structlog.get_logger()
settings = get_settings()

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are a senior manga localization editor for an English-language publisher.
Your translations must read like polished, professional scanlations — not machine translation.
Follow these rules exactly:

1. TONE: Match the emotional register in English (casual teen banter, intense battle dialogue,
   technical exposition, comic relief). Prioritize natural English flow over literal accuracy.
2. HONORIFICS: Keep -san, -kun, -chan, -senpai unless a direct English equivalent fits perfectly.
3. SFX: Localize onomatopoeia creatively. ドカン → "KRAKOOM", ピン → "PLING", バキ → "CRACK".
   Make them LOUD and dynamic in English.
4. CULTURAL NOTES: If a pun or cultural reference cannot survive translation, provide your best
   localized version AND add a tl_note explaining the original.
5. GLOSSARY: Use every term in the provided glossary exactly as written. Do not improvise names.
6. LENGTH: Keep translations concise enough to fit inside a speech bubble. Prefer punchy phrasing.
7. OUTPUT: Return ONLY valid JSON. No markdown, no commentary, no preamble."""

TONE_HINTS = {
    "jagged":      "This is a SHOUT or sound effect (SFX). Be explosive and dynamic. ALL CAPS for SFX.",
    "smooth_oval": "Standard dialogue bubble. Match the character's personality and emotional state.",
    "rectangular": "Narration caption box. Formal, measured, past-tense prose.",
    "thought":     "Internal thought bubble. Italicized feel; introspective or uncertain tone.",
    "caption":     "Expository caption. Clear, informative, neutral register.",
}


def build_translation_prompt(
    jp_text: str,
    bubble_shape: str,
    context_text: str,
    glossary: list[dict],
) -> str:
    tone_hint = TONE_HINTS.get(bubble_shape, TONE_HINTS["smooth_oval"])
    glossary_str = json.dumps(
        [{"jp": g["japanese_term"], "en": g["english_term"], "type": g["term_type"]} for g in glossary],
        ensure_ascii=False,
        indent=2,
    ) if glossary else "[]"

    return f"""KNOWN TERMS GLOSSARY (use exactly as written):
{glossary_str}

PRIOR PAGE CONTEXT (last {settings.context_window_pages} pages — Japanese, for continuity):
{context_text or "(no prior context)"}

TEXT TO TRANSLATE:
{jp_text}

TONE CONTEXT: {tone_hint}

Respond with ONLY this JSON object (no markdown):
{{
  "english_text": "...",
  "tone_label": "dialogue|narration|sfx|technical|thought",
  "alternatives": ["...", "..."],
  "tl_note": null
}}"""


def translate_block(
    jp_text: str,
    bubble_shape: str,
    context_text: str = "",
    glossary: list[dict] | None = None,
) -> dict:
    """
    Calls Claude to translate a single OCR block.
    Returns parsed dict with keys: english_text, tone_label, alternatives, tl_note.
    """
    prompt = build_translation_prompt(jp_text, bubble_shape, context_text, glossary or [])

    try:
        message = client.messages.create(
            model=settings.translation_model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()

        # Strip any accidental markdown fences
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()

        result = json.loads(raw)
        log.info("Translated", jp=jp_text[:30], en=result.get("english_text", "")[:40])
        return result

    except json.JSONDecodeError as e:
        log.error("JSON parse error from Claude", error=str(e), raw=raw[:200])
        # Graceful fallback: return raw text as english
        return {
            "english_text": jp_text,
            "tone_label": "dialogue",
            "alternatives": [],
            "tl_note": "Auto-translation failed; original text preserved.",
        }
    except anthropic.APIError as e:
        log.error("Anthropic API error", error=str(e))
        raise


def select_font_for_block(bubble_shape: str, tone_label: str, is_sfx: bool) -> tuple[str, float]:
    """
    Returns (font_family_name, font_size_pt).
    Font files must be present in backend/app/fonts/.
    """
    if is_sfx or bubble_shape == "jagged":
        return "Bangers-Regular", 18.0
    if tone_label == "technical" or bubble_shape in ("rectangular", "caption"):
        return "MangaTemple", 11.0
    if bubble_shape == "thought":
        return "AnimeAce2-Italic", 12.0
    return "AnimeAce2", 12.0


def build_context_text(prior_blocks: list[dict]) -> str:
    """
    Concatenate prior page OCR text for context injection.
    prior_blocks: list of {page_number, raw_jp_text}.
    """
    lines = []
    for b in prior_blocks:
        lines.append(f"[Page {b['page_number']}] {b['raw_jp_text']}")
    return "\n".join(lines)
