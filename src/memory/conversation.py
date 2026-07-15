import json
from pathlib import Path
from typing import Optional

import google.generativeai as genai

from src.config import cfg, settings
from src.core.prompt_manager import load_prompt

_DATA_DIR = Path(__file__).parent.parent.parent / "data" / "memory"


def _summary_path(document_id: str) -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _DATA_DIR / f"{document_id}_summary.json"


def load_summary(document_id: str) -> Optional[str]:
    path = _summary_path(document_id)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("summary")
    return None


def save_summary(document_id: str, summary: str) -> None:
    path = _summary_path(document_id)
    path.write_text(json.dumps({"summary": summary, "document_id": document_id}), encoding="utf-8")


def update_summary(document_id: str, audit_result: dict) -> str:
    previous = load_summary(document_id) or "No prior audit."

    prompt = load_prompt("summarizer_system")
    transcript = json.dumps(audit_result, indent=2, default=str)

    if settings.gemini_api_key:
        _gemini_cfg = cfg.get("gemini", {})
        _MODEL = _gemini_cfg.get("model", "gemini-2.0-flash")
        _TEMPERATURE = _gemini_cfg.get("temperature", 0.0)
        _MAX_TOKENS = _gemini_cfg.get("max_tokens", 1024)

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            model_name=_MODEL,
            system_instruction=prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=_TEMPERATURE,
                max_output_tokens=_MAX_TOKENS,
            ),
        )
        user_content = (
            f"Previous summary:\n{previous}\n\n"
            f"New audit result:\n{transcript}\n\n"
            f"Produce an updated summary."
        )
        resp = model.generate_content(user_content)
        summary = resp.text or previous
    else:
        summary = (
            f"Audit completed for document {document_id}. "
            f"Risk level: {audit_result.get('compliance_report', {}).get('overall_risk_level', 'unknown')}. "
            f"Math validation: {'passed' if audit_result.get('math_validation', {}).get('is_valid') else 'issues found'}."
        )

    save_summary(document_id, summary)
    return summary


def clear_summary(document_id: str) -> None:
    path = _summary_path(document_id)
    if path.exists():
        path.unlink()
