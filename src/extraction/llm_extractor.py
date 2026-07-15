import json
from pathlib import Path
from typing import Any

import google.generativeai as genai

from src.config import settings, cfg
from src.core.exceptions import ExtractionError
from src.extraction.schemas import LeaseTerms, ExtractionResult, RentSchedule


_gemini_cfg = cfg.get("gemini", {})
_TARGET_MODEL = _gemini_cfg.get("model", "gemini-2.0-flash")
_TEMPERATURE = _gemini_cfg.get("temperature", 0.0)
_MAX_TOKENS = _gemini_cfg.get("max_tokens", 4096)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "extraction" / "lease_extraction_v1.md"


def _load_extraction_prompt() -> str:
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text()
    return "Extract lease terms from the following document sections into a JSON object."


def extract_lease_terms(sections: list[dict[str, Any]]) -> ExtractionResult:
    genai.configure(api_key=settings.gemini_api_key)
    system_prompt = _load_extraction_prompt()

    clauses_text = ""
    for sec in sections:
        title = sec.get("title", "Unknown")
        content = sec.get("content", "")[:3000]
        clauses_text += f"=== {title} ===\n{content}\n\n"

    schema_json = LeaseTerms.model_json_schema()

    user_content = (
        f"Extract lease terms from the following document sections.\n\n"
        f"{clauses_text}\n\n"
        f"Return ONLY valid JSON matching this schema:\n{json.dumps(schema_json, indent=2)}\n\n"
        f"Also include a 'confidence_score' (0.0-1.0) and 'raw_clauses' (dict of section title -> raw text)."
    )

    model = genai.GenerativeModel(
        model_name=_TARGET_MODEL,
        system_instruction=system_prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=_TEMPERATURE,
            max_output_tokens=_MAX_TOKENS,
            response_mime_type="application/json",
        ),
    )

    try:
        response = model.generate_content(user_content)
    except Exception as e:
        raise ExtractionError(f"LLM extraction failed: {e}") from e

    content = response.text
    if not content:
        raise ExtractionError("Empty response from LLM")

    try:
        raw = json.loads(content)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Failed to parse LLM JSON: {e}") from e

    lease_terms_data = raw.get("lease_terms", raw)
    lease_terms = LeaseTerms(**lease_terms_data)

    if "rent_schedule" in lease_terms_data and lease_terms_data["rent_schedule"]:
        lease_terms.rent_schedule = [RentSchedule(**rs) for rs in lease_terms_data["rent_schedule"]]

    confidence = raw.get("confidence_score", 0.0)
    raw_clauses = raw.get("raw_clauses", {})

    result = ExtractionResult(
        lease_terms=lease_terms,
        raw_clauses=raw_clauses,
        confidence_score=confidence,
    )

    return result
