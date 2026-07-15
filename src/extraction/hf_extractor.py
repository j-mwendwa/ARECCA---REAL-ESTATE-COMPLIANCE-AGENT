"""
Extraction via HuggingFace model fine-tuned on legal corpus.
Default: AdaptLLM/law-llm-7b (Mistral-7B fine-tuned on legal text).

Uses ContextAssembler for prompt assembly with entity memory + conversation summary,
token counting, and context trimming.
"""
import json
from typing import Any, Optional

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from src.config import cfg
from src.core.exceptions import ExtractionError
from src.core.context_assembler import ContextAssembler
from src.extraction.schemas import LeaseTerms, ExtractionResult, RentSchedule

_HF_CFG = cfg.get("llm", {})
_MODEL = _HF_CFG.get("model", "AdaptLLM/law-llm-7b")
_DEVICE = _HF_CFG.get("device", "auto")
_LOAD_IN_8BIT = _HF_CFG.get("load_in_8bit", True)
_MAX_TOKENS = _HF_CFG.get("max_tokens", 4096)
_TEMPERATURE = _HF_CFG.get("temperature", 0.0)

_pipeline = None
_tokenizer = None


def _load_model():
    global _pipeline, _tokenizer
    if _pipeline is not None:
        return _pipeline

    tokenizer = AutoTokenizer.from_pretrained(_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        _MODEL,
        trust_remote_code=True,
        torch_dtype=torch.float16 if _DEVICE == "cuda" else torch.float32,
        device_map=_DEVICE if _DEVICE != "cpu" else None,
        load_in_8bit=_LOAD_IN_8BIT and _DEVICE != "cpu",
        low_cpu_mem_usage=True,
    )

    _tokenizer = tokenizer
    _pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=_MAX_TOKENS,
        temperature=_TEMPERATURE,
        do_sample=False,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    return _pipeline


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return text


def extract_lease_terms(
    sections: list[dict[str, Any]],
    document_id: Optional[str] = None,
) -> ExtractionResult:
    gen = _load_model()
    schema_json = json.dumps(LeaseTerms.model_json_schema(), indent=2)

    assembler = ContextAssembler(document_id=document_id or "cli")
    assembled = assembler.assemble(sections)
    prompt = assembled.build_prompt(schema_json)

    try:
        output = gen(prompt, return_full_text=False)
        content = output[0]["generated_text"]
    except Exception as e:
        raise ExtractionError(f"HF extraction failed: {e}") from e

    cleaned = _clean_json(content)
    if not cleaned:
        raise ExtractionError("Empty response after cleaning")

    try:
        raw = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            brace_pos = cleaned.find("{")
            end_pos = cleaned.rfind("}") + 1
            if brace_pos >= 0 and end_pos > brace_pos:
                raw = json.loads(cleaned[brace_pos:end_pos])
            else:
                raise
        except (json.JSONDecodeError, ValueError) as e:
            raise ExtractionError(f"Failed to parse model output as JSON: {e}") from e

    lease_terms_data = raw.get("lease_terms", raw)
    lease_terms = LeaseTerms(**lease_terms_data)

    if "rent_schedule" in lease_terms_data and lease_terms_data["rent_schedule"]:
        lease_terms.rent_schedule = [RentSchedule(**rs) for rs in lease_terms_data["rent_schedule"]]

    confidence = raw.get("confidence_score", 0.0)
    raw_clauses = raw.get("raw_clauses", {})

    if document_id and assembler.memory:
        lt = lease_terms
        facts = {}
        if lt.lessor:
            facts["lessor"] = lt.lessor
        if lt.lessee:
            facts["lessee"] = lt.lessee
        if lt.lease_start_date:
            facts["lease_start_date"] = str(lt.lease_start_date)
        if lt.lease_end_date:
            facts["lease_end_date"] = str(lt.lease_end_date)
        if lt.base_rent_monthly:
            facts["base_rent_monthly"] = str(lt.base_rent_monthly)
        if lt.escalation_type:
            facts["escalation_type"] = lt.escalation_type
        if lt.escalation_rate:
            facts["escalation_rate"] = str(lt.escalation_rate)
        if lt.security_deposit:
            facts["security_deposit"] = str(lt.security_deposit)
        if lt.late_fee_amount:
            facts["late_fee_amount"] = str(lt.late_fee_amount)
        assembler.memory.update(facts)

    return ExtractionResult(
        lease_terms=lease_terms,
        raw_clauses=raw_clauses,
        confidence_score=confidence,
    )
