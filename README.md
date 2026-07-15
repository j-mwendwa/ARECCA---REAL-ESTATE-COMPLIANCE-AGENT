# ARECCA — Automated Real Estate Contract Compliance Auditor

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1c3c3c)](https://langchain-ai.github.io/langgraph/)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-0.14-purple)](https://llamaindex.ai)
[![Qdrant](https://img.shields.io/badge/Vector%20Store-Qdrant%20%2B%20BM25-red)](https://qdrant.tech)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**ARECCA** ingests commercial real estate lease PDFs, extracts structured terms via a legal-fine-tuned LLM, validates rent math deterministically (never trusts the LLM with numbers), flags compliance violations against state laws, and indexes everything for hybrid semantic search.

---

## Architecture

```
                        ┌──────────────────────────────┐
                        │   Chainlit Chat UI (8501)     │
                        │   or HTTP Client (8000)       │
                        └──────────┬───────────────────┘
                                   │
                        ┌──────────▼───────────────────┐
                        │   FastAPI + LangGraph App     │
                        │   src/api/main.py             │
                        └──────────┬───────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
     ┌────────▼────────┐  ┌───────▼────────┐  ┌────────▼────────┐
     │  Input Guardrail │  │  Local Storage │  │  PostgreSQL     │
     │  (injection,     │  │  (data/uploads)│  │  (results)      │
     │   malware scan)  │  └────────────────┘  └─────────────────┘
     └────────┬────────┘
              │
     ┌────────▼─────────────────────────────────────────────┐
     │           LangGraph StateGraph Pipeline               │
     │                                                       │
     │  ┌──────────┐   ┌─────────┐   ┌────────────────┐     │
     │  │  Ingest   │──►│  Chunk  │──►│  Extract       │     │
     │  │(PDFReader)│   │(Semantic│   │(HF Legal LLM + │     │
     │  │          │   │ Splitter)│   │ ContextAssembly)│     │
     │  └──────────┘   └─────────┘   └────────┬───────┘     │
     │                                         │             │
     │  ┌──────────┐   ┌─────────┐   ┌────────▼───────┐     │
     │  │  Report  │◄──│ Output  │◄──│  Math Validate │     │
     │  │          │   │ Guardrail│   │  (NumPy, no LLM)│     │
     │  └──────────┘   └─────────┘   └────────┬───────┘     │
     │                                         │             │
     │  ┌──────────┐   ┌─────────┐            │             │
     │  │  Index   │◄──│Compliance│◄───────────┘             │
     │  │ (Qdrant) │   │(Rule Eng)│                         │
     │  └──────────┘   └─────────┘                          │
     └──────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │                              │
           ┌────────▼────────┐          ┌──────────▼───────┐
           │ Qdrant Cloud    │          │  Entity Memory   │
           │ (Hybrid Search) │          │  + Conversation  │
           │ dense + BM25    │          │  Summary (Gemini)│
           │ alpha=0.3       │          │                  │
           └─────────────────┘          └──────────────────┘
```

### 5-Phase Pipeline

| Phase | What | Never trusts LLM with |
|-------|------|----------------------|
| **1. Document Ingestion** | LlamaIndex `PDFReader` parses the PDF; raw file stored locally in `data/uploads/` | — |
| **2. Semantic Chunking** | `SemanticSplitterNodeParser` splits by embedding-similarity breakpoints (buffer=3, percentile=85) | — |
| **3. Structured Extraction** | `AdaptLLM/law-llm-7b` via HuggingFace pipeline, forced JSON output via Pydantic `LeaseTerms` schema, context assembled from entity memory + conversation summary | *freeform generation* — output is Pydantic-validated |
| **4. Math Validation** | NumPy-vectorized computation of projected rent schedule; compares every year against stated values with configurable decimal tolerance | **all financial math** — pure Python `@tool`, never called on LLM |
| **5. Compliance & Flagging** | Rule engine compares against CA state laws (late fee cap, grace period, deposit limit, escalation disclosure) | — |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Chat UI** | Chainlit (ChatGPT-style interface on port 8501) |
| **API** | FastAPI 0.111, Uvicorn |
| **Pipeline** | LangGraph 1.2 (StateGraph, 10 nodes) |
| **LLM (Primary)** | `AdaptLLM/law-llm-7b` (Mistral-7B fine-tuned on legal corpus) via HuggingFace `transformers` |
| **LLM (Summarization)** | Gemini 2.0 Flash (optional, via `google-generativeai`) |
| **Embeddings** | `nlpaueb/legal-bert-base-uncased` (768-dim legal-domain BERT) |
| **Vector Store** | Qdrant Cloud with hybrid search (dense cosine + BM25 sparse, alpha=0.3) |
| **Ingestion** | LlamaIndex `PDFReader` + `SemanticSplitterNodeParser` |
| **Database** | PostgreSQL 15+ (async via `asyncpg` + SQLAlchemy 2.0) |
| **File Storage** | Local filesystem (`data/uploads/`) |
| **Math** | NumPy vectorized validation |
| **Prompts** | Markdown files in `prompts/`, versioned, hot-reloadable |
| **Memory** | Entity memory (JSON + optional Fernet encryption), conversation summary (Gemini rolling summary) |
| **Guardrails** | Injection detection (single alternation regex), malicious content scan (bytes), LRU-cached results |
| **Observability** | LangSmith tracing (opt-in), structlog, token accounting |
| **Container** | Multi-stage Docker, non-root `arecca` user, persistent volumes |
| **Deployment** | Railway (auto-deploy from GitHub) |
| **Testing** | pytest (~44 tests), pytest-asyncio |

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Qdrant Cloud account (or local Qdrant: `docker run -p 6333:6333 qdrant/qdrant`)
- (Optional) Gemini API key for conversation summaries
- (Optional) GPU for local LLM inference; falls back to CPU

### Local Development

```bash
# 1. Clone & enter
cd arecca

# 2. Environment
cp .env.example .env
# Edit .env with your keys (DATABASE_URL, QDRANT_URL, QDRANT_API_KEY, etc.)

# 3. Install
make install

# 4. Run the API
make dev
# → http://localhost:8000
# → health: http://localhost:8000/health

# 5. Run the Chainlit UI (separate terminal)
chainlit run src/ui/app.py --port 8501
# → http://localhost:8501
```

### Docker

```bash
# Build
docker build -t arecca:latest .

# Run
docker run -p 8000:8000 \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/data:/app/data \
  arecca:latest
```

### Railway Deployment

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/...)

1. Push to GitHub
2. Connect repo to [Railway](https://railway.app)
3. Add PostgreSQL plugin (Railway injects `DATABASE_URL` automatically)
4. Set env vars: `GEMINI_API_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`, `STORAGE_PATH`
5. Deploy — Railway auto-detects the `Dockerfile`

---

## Chainlit UI

The Chainlit UI provides a ChatGPT-style interface on port 8501.

```bash
chainlit run src/ui/app.py --port 8501
```

### Features:
- **Upload & Audit** — Click the upload button, select a PDF, the full pipeline runs automatically
- **Document History** — Browse previously audited documents with status indicators
- **Search** — Natural language search across indexed lease clauses
- **Audit Results** — Formatted extraction, math validation, and compliance report with risk level icons

---

## API Reference

### `POST /api/v1/upload`
Upload a lease PDF for auditing.

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@lease.pdf"
```
```json
{
  "document_id": "uuid-...",
  "filename": "lease.pdf",
  "status": "processing",
  "message": "Document uploaded and queued for audit"
}
```

### `POST /api/v1/audit/{document_id}`
Run the full 5-phase LangGraph audit pipeline.

```bash
curl -X POST http://localhost:8000/api/v1/audit/uuid-...
```
```json
{
  "document_id": "uuid-...",
  "filename": "lease.pdf",
  "status": "completed",
  "extraction": { "lease_terms": { ... }, "confidence_score": 0.94 },
  "math_validation": { "is_valid": true, "details": { ... } },
  "compliance_report": {
    "overall_risk_level": "medium",
    "flag_count": 1,
    "flags": [ { "rule_id": "GRACE_PERIOD", "risk_level": "medium", ... } ]
  }
}
```

### `POST /api/v1/search`
Hybrid semantic search over ingested lease clauses.

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{ "query": "late fee grace period", "top_k": 5, "alpha": 0.3 }'
```
```json
{
  "query": "late fee grace period",
  "results": [
    { "section_title": "Section 3: Late Fee...",
      "content": "A late fee of 5% applies after 10...",
      "score": 0.87,
      "page_number": 4 }
  ]
}
```

### `GET /api/v1/documents`
List all audited documents.

### `GET /api/v1/documents/{document_id}`
Get audit result for a specific document.

### `GET /health`
Liveness probe.

---

## Configuration

### `.env` (secrets)

| Variable | Required | Default |
|----------|----------|---------|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://localhost:5432/arecca` |
| `QDRANT_URL` | Yes | `https://your-cluster.cloud.qdrant.io:6333` |
| `QDRANT_API_KEY` | Yes (Cloud) | — |
| `GEMINI_API_KEY` | No | — (for conversation summaries) |
| `STORAGE_PATH` | No | `data/uploads` |
| `API_KEY` | No | `dev-local-key` |
| `LANGSMITH_API_KEY` | No | — |
| `MEMORY_ENCRYPTION_KEY` | No | — |

### `configs/config.yaml` (runtime tuning)

```yaml
llm:
  model: AdaptLLM/law-llm-7b           # HuggingFace model ID
  device: auto                          # cpu / cuda / auto
  load_in_8bit: true                    # memory optimization

gemini:
  model: gemini-2.0-flash               # Gemini model for summaries
  temperature: 0.0
  max_tokens: 4096

chunking:
  strategy: semantic                    # semantic | sentence
  semantic_buffer_size: 3
  semantic_breakpoint_percentile: 85

retrieval:
  hybrid_search: true
  alpha: 0.3                            # 0 = dense only, 1 = sparse only

validation:
  rounding_decimals: 2
  tolerance: 0.01                       # $0.01 discrepancy threshold

context:
  target_context_tokens: 8000           # context window budget

prompts:
  version: v1
  hot_reload: false                     # set true during prompt development
```

---

## Project Structure

```
src/
├── ui/
│   └── app.py                Chainlit chat UI (port 8501)
├── api/
│   ├── main.py               FastAPI app + lifespan (tracing, llamaindex, DB)
│   ├── routes.py             /upload, /audit, /search, /documents
│   └── schemas.py            Pydantic request/response models
├── graph/
│   ├── graph.py              StateGraph compiler (10 nodes, conditional edges)
│   ├── state.py              AgentState TypedDict
│   ├── nodes.py              Pipeline nodes (guardrail → ingest → ... → report)
│   ├── edges.py              Conditional routing (blocked → rejection, errors → end)
│   ├── guardrails.py         Input (ext/malware/injection) + output (confidence/risk)
│   └── tools.py              NumPy @tool for rent schedule validation
├── ingestion/
│   ├── llamaindex_pipeline.py    PDFReader + SemanticSplitterNodeParser
│   └── storage.py                Local filesystem storage (save_file, copy_file, delete_file)
├── extraction/
│   ├── schemas.py            Pydantic: LeaseTerms, RentSchedule, ExtractionResult
│   └── hf_extractor.py       HuggingFace pipeline + ContextAssembler
├── validation/
│   └── math_validator.py     Decimal-based rent math (backup for tests)
├── compliance/
│   ├── rules.py              13 compliance rules (late fee, deposit, grace, etc.)
│   └── engine.py             Rule engine → ComplianceReport
├── vectordb/
│   └── qdrant_store.py       Qdrant client + collection + hybrid store
├── retrieval/
│   └── hybrid_retriever.py   LlamaIndex retriever (alpha=0.3, hybrid mode)
├── database/
│   ├── models.py             SQLAlchemy: LeaseDocument, Extraction, Validation, Flag
│   └── session.py            AsyncSession factory
├── memory/
│   ├── entity_memory.py      KV facts per document (JSON + Fernet)
│   └── conversation.py       Rolling summary via Gemini
├── core/
│   ├── config.py             Pydantic Settings + YAML merge
│   ├── context_assembler.py  Prompt + entity_memory + summary + token trim
│   ├── prompt_manager.py     Versioned prompt loader from prompts/ tree
│   ├── token_counter.py      tiktoken cl100k_base
│   ├── tracing.py            LangSmith opt-in
│   ├── llamaindex_setup.py   Centralised embed model init
│   └── logging.py            structlog JSON/console
├── configs/config.yaml        Runtime configuration
├── prompts/
│   ├── extraction/            Lease extraction prompt (v1)
│   ├── compliance/            Compliance rules reference
│   └── summarizer_system.md   Rollup summarizer system prompt
└── tests/                     ~44 tests (pytest)
    ├── test_guardrails.py
    ├── test_guardrail_efficiency.py
    ├── test_graph_tools.py
    ├── test_compliance.py
    ├── test_math_validator.py
    ├── test_chunker.py
    ├── test_storage.py
    ├── test_parser.py
    └── test_llamaindex_pipeline.py
```

---

## Testing

```bash
# Run all tests
make test

# Or directly
python -m pytest tests/ -v

# Run a specific module
python -m pytest tests/test_math_validator.py -v
python -m pytest tests/test_guardrail_efficiency.py -v
```

Test coverage:

| Module | Tests | What it proves |
|--------|-------|----------------|
| `test_math_validator` | 6 | Deterministic rent math (fixed %, fixed $, CPI, caps, discrepancies) |
| `test_compliance` | 5 | Rule engine flags (late fee, grace, deposit, clean) |
| `test_chunker` | 4 | Section header detection, multi-page chunking |
| `test_graph_tools` | 5 | NumPy vectorized `validate_rent_schedule` |
| `test_guardrails` | 9 | Input/output security decisions |
| `test_guardrail_efficiency` | 10 | Sub-millisecond guard checks, cache hits, early exits |
| `test_storage` | 4 | Local filesystem save, copy, delete, error handling |
| `test_llamaindex_pipeline` | 3 | Ingestion pipeline |
| `test_parser` | 2 | PDF parsing |

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **LLM never touches math** | `validate_rent_schedule` is a pure NumPy `@tool`; the graph node calls it directly, never the LLM |
| **Prompts in markdown files** | `prompts/extraction/lease_extraction_v1.md` — versioned, hot-reloadable, auditable in git |
| **Semantic over regex chunking** | `SemanticSplitterNodeParser` adapts to document structure; no brittle regex maintenance |
| **Context assembly with token budget** | Entity memory + conversation summary injected into prompt, trimmed from the back if over 8K tokens |
| **LRU-cached guardrails** | Same content_hash skips re-scanning; single alternation regex for O(1) pattern matching |
| **HuggingFace legal model** | `AdaptLLM/law-llm-7b` fine-tuned on legal corpus; no API calls, private by default |
| **Hybrid search alpha=0.3** | Biased toward dense semantic search with 30% sparse BM25 signal for exact clause matching |
| **Per-document entity memory** | Extracted facts persisted as JSON; optional Fernet encryption at rest |
| **Gemini for summaries** | Optional Gemini 2.0 Flash generates rolling conversation summaries; falls back to template if no key set |
| **Local file storage** | PDFs stored in `data/uploads/` — no cloud dependency; just mount a volume for persistence |

---

## GitHub Actions CI / Deploy

The project includes a CI/CD pipeline in `.github/workflows/deploy.yml`:

- **CI** — Runs on every PR/push to `main`: lint (`ruff`), type check (`mypy`), tests (`pytest`)
- **Docker** — Builds the Docker image with BuildKit caching
- **Deploy** — Deploys to Railway via the official GitHub Action

**Required secrets:**
- `RAILWAY_TOKEN` — Railway API token
- `RAILWAY_PROJECT_ID` — Railway project ID
- `RAILWAY_SERVICE_ID` — Railway service ID
