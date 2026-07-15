"""
Context assembler that builds the extraction prompt with entity memory,
conversation summary, token counting, and trimming.

Reference: LLM-RAG-PIPELINE / src/core/context_assembler.py
"""
import structlog

from src.core.prompt_manager import load_prompt
from src.core.token_counter import count_tokens, truncate_to_token_limit
from src.memory.entity_memory import EntityMemory
from src.memory.conversation import load_summary
from src.config import cfg

logger = structlog.get_logger()

_TARGET_CONTEXT_TOKENS = cfg.get("context", {}).get("target_context_tokens", 8000)


class AssembledContext:
    def __init__(
        self,
        system_prompt: str,
        entity_memory_block: str,
        conversation_summary: str,
        sections_text: str,
        total_tokens: int,
    ) -> None:
        self.system_prompt = system_prompt
        self.entity_memory_block = entity_memory_block
        self.conversation_summary = conversation_summary
        self.sections_text = sections_text
        self.total_tokens = total_tokens

    def build_prompt(self, schema_json: str) -> str:
        parts = [
            f"<s>[INST] <<SYS>>\n{self.system_prompt}\n<</SYS>>",
        ]
        if self.entity_memory_block:
            parts.append(f"\n<entity_memory>\n{self.entity_memory_block}\n</entity_memory>")
        if self.conversation_summary:
            parts.append(f"\n<conversation_summary>\n{self.conversation_summary}\n</conversation_summary>")
        parts.append(f"\n\nExtract lease terms from the following document sections.\n\n{self.sections_text}")
        parts.append(f"\n\nReturn ONLY valid JSON matching this schema:\n{schema_json}")
        parts.append("\n\nAlso include 'confidence_score' (0.0-1.0) and 'raw_clauses' (dict).[/INST]")
        return "".join(parts)


class ContextAssembler:
    def __init__(
        self,
        document_id: str,
        prompt_name: str = "extraction/lease_extraction",
        target_tokens: int = _TARGET_CONTEXT_TOKENS,
    ) -> None:
        self.document_id = document_id
        self.prompt_name = prompt_name
        self.target_tokens = target_tokens
        self.memory = EntityMemory(document_id) if document_id else None

    def assemble(self, sections: list[dict]) -> AssembledContext:
        system_prompt = load_prompt(self.prompt_name)

        entity_memory_block = self.memory.summary if self.memory else ""
        conversation_summary = load_summary(self.document_id) or ""

        sections_text = ""
        for sec in sections:
            title = sec.get("title", "Unknown")
            content = sec.get("content", "")[:3000]
            sections_text += f"=== {title} ===\n{content}\n\n"

        total_tokens = (
            count_tokens(system_prompt)
            + count_tokens(entity_memory_block)
            + count_tokens(conversation_summary)
            + count_tokens(sections_text)
            + 500
        )

        if total_tokens > self.target_tokens:
            over = total_tokens - self.target_tokens
            if over > 0 and sections_text:
                sections_tokens = count_tokens(sections_text)
                trim_to = max(sections_tokens - over, 500)
                sections_text = truncate_to_token_limit(sections_text, trim_to)
                trimmed_tokens = count_tokens(sections_text)
                total_tokens = (
                    count_tokens(system_prompt)
                    + count_tokens(entity_memory_block)
                    + count_tokens(conversation_summary)
                    + trimmed_tokens
                    + 500
                )
                logger.info("context_trimmed", original_tokens=total_tokens + over, trimmed_to=total_tokens)

        return AssembledContext(
            system_prompt=system_prompt,
            entity_memory_block=entity_memory_block,
            conversation_summary=conversation_summary,
            sections_text=sections_text,
            total_tokens=total_tokens,
        )
