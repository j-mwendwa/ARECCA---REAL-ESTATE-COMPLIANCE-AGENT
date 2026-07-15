import uuid
import asyncio
from pathlib import Path
from datetime import datetime

import chainlit as cl
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import cfg
from src.database.session import async_session_factory, engine
from src.database.models import Base, LeaseDocument, LeaseExtraction, MathValidation, ComplianceFlag, AuditStatus
from src.ingestion.storage import save_file
from src.graph.graph import build_graph
from src.graph.state import AgentState
from src.retrieval.hybrid_retriever import get_hybrid_retriever
from src.core.llamaindex_setup import setup_llamaindex
from src.core.logging import setup_logging
from src.vectordb.qdrant_store import ensure_collection


_GRAPH = None


def _get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


async def _init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def _list_documents(session: AsyncSession) -> list[LeaseDocument]:
    result = await session.execute(
        select(LeaseDocument).order_by(desc(LeaseDocument.created_at)).limit(50)
    )
    return list(result.scalars().all())


def _format_audit_result(state: dict) -> str:
    lines = []
    extraction = state.get("extraction") or {}
    lease_terms = extraction.get("lease_terms") or state.get("lease_terms") or {}
    math_val = state.get("math_validation") or {}
    compliance = state.get("compliance_report") or {}

    lines.append("## Audit Complete\n")

    lines.append("### Extracted Terms")
    if lease_terms:
        items = [
            ("Lessor", lease_terms.get("lessor")),
            ("Lessee", lease_terms.get("lessee")),
            ("Address", lease_terms.get("property_address")),
            ("Start Date", lease_terms.get("lease_start_date")),
            ("End Date", lease_terms.get("lease_end_date")),
            ("Term (months)", lease_terms.get("lease_term_months")),
            ("Base Rent (monthly)", f"${lease_terms.get('base_rent_monthly'):,.2f}" if lease_terms.get("base_rent_monthly") else None),
            ("Security Deposit", f"${lease_terms.get('security_deposit'):,.2f}" if lease_terms.get("security_deposit") else None),
            ("Escalation Type", lease_terms.get("escalation_type")),
            ("Escalation Rate", f"{lease_terms.get('escalation_rate')}%" if lease_terms.get("escalation_rate") else None),
            ("Late Fee", lease_terms.get("late_fee_amount")),
            ("Grace Period", f"{lease_terms.get('grace_period_days')} days" if lease_terms.get("grace_period_days") else None),
        ]
        for label, value in items:
            if value:
                lines.append(f"  - **{label}:** {value}")
    else:
        lines.append("  No terms extracted.")

    confidence = extraction.get("confidence_score") or 0
    lines.append(f"\n  **Confidence:** {confidence:.1%}")

    rent_schedule = lease_terms.get("rent_schedule") or extraction.get("rent_schedule")
    if rent_schedule:
        lines.append("\n### Rent Schedule")
        for entry in rent_schedule:
            yr = entry.get("year", "?")
            annual = entry.get("annual_rent", 0)
            monthly = entry.get("monthly_rent", 0)
            esc = entry.get("escalation_percent")
            esc_str = f" (+{esc}%)" if esc else ""
            lines.append(f"  - Year {yr}: ${annual:,.2f}/yr (${monthly:,.2f}/mo){esc_str}")

    lines.append("\n### Math Validation")
    if math_val.get("is_valid"):
        lines.append("  ✅ **Pass** — All rent calculations are consistent.")
    else:
        lines.append("  ❌ **Fail** — Discrepancies found.")
        for d in (math_val.get("discrepancies") or []):
            lines.append(f"    - {d}")

    lines.append("\n### Compliance Report")
    flags = compliance.get("flags") or []
    if flags:
        risk_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        for flag in flags:
            icon = risk_icons.get(flag.get("risk_level", "low"), "⚪")
            lines.append(f"  {icon} **{flag.get('rule_name')}** ({flag.get('risk_level')})")
            lines.append(f"    {flag.get('description')}")
    else:
        lines.append("  ✅ No compliance issues found.")

    return "\n".join(lines)


@cl.on_chat_start
async def on_chat_start():
    setup_logging()
    await _init_db()
    setup_llamaindex()
    ensure_collection()

    _get_graph()

    await cl.Message(
        content="Welcome to **ARECCA** — your lease compliance auditor.\n\nChoose an option below to get started."
    ).send()

    await _show_main_menu()


async def _show_main_menu():
    await cl.AskActionMessage(
        content="What would you like to do?",
        keys=[
            cl.ActionStyle(name="upload", label="📄  Upload & Audit Lease", description="Upload a PDF lease for full analysis", value="upload"),
            cl.ActionStyle(name="list", label="📋  View Document History", description="Browse previously audited documents", value="list"),
            cl.ActionStyle(name="search", label="🔍  Search Documents", description="Search across all indexed lease clauses", value="search"),
        ],
    ).send()


@cl.on_message
async def on_message(msg: cl.Message):
    text = msg.content.strip().lower()

    if text.startswith("search:"):
        query = text[7:].strip()
        if not query:
            await cl.Message(content="Please provide a search query like `search: late fee clause`").send()
            return
        await _handle_search(query)
        return

    if text.startswith("doc:"):
        doc_id = text[4:].strip()
        await _show_document(doc_id)
        return

    if text in ("menu", "back", "main"):
        await _show_main_menu()
        return

    await cl.Message(
        content="Use the menu buttons above, or type:\n"
        "  - `search: <query>` — search across documents\n"
        "  - `doc: <id>` — view a document by ID\n"
        "  - `menu` — show the main menu"
    ).send()


@cl.action_callback("upload")
async def on_upload(action: cl.Action):
    files = await cl.AskFileMessage(
        content="Upload a lease PDF to analyse.",
        accept={"application/pdf": [".pdf"]},
        max_size_mb=50,
    ).send()

    if not files:
        await cl.Message(content="No file received.").send()
        await _show_main_menu()
        return

    pdf = files[0]
    content = Path(pdf.path).read_bytes()
    blob_name = f"leases/{datetime.utcnow().strftime('%Y/%m/%d')}/{uuid.uuid4()}_{pdf.name}"
    storage_path = save_file(content, blob_name)

    doc_id = str(uuid.uuid4())

    async with async_session_factory() as session:
        document = LeaseDocument(
            id=uuid.UUID(doc_id),
            filename=pdf.name,
            storage_path=storage_path,
            content_hash=uuid.uuid4().hex,
            status=AuditStatus.processing,
        )
        session.add(document)
        await session.commit()

    await cl.Message(
        content=f"📄 **{pdf.name}** uploaded.\n\nDocument ID: `{doc_id}`"
    ).send()

    await _run_audit_for_document(doc_id)


@cl.action_callback("list")
async def on_list(action: cl.Action):
    await _handle_list_documents()


@cl.action_callback("search")
async def on_search(action: cl.Action):
    query_msg = await cl.AskUserMessage(content="What would you like to search for?", timeout=120).send()
    if query_msg and query_msg.get("output"):
        await _handle_search(query_msg["output"])
    else:
        await _show_main_menu()


async def _handle_list_documents():
    async with async_session_factory() as session:
        docs = await _list_documents(session)

    if not docs:
        await cl.Message(content="No documents found. Upload a lease PDF to get started.").send()
        await _show_main_menu()
        return

    lines = ["### Document History\n"]
    for doc in docs:
        status_icon = {"completed": "✅", "failed": "❌", "processing": "⏳", "pending": "⏸️"}
        icon = status_icon.get(doc.status.value, "❓")
        created = doc.created_at.strftime("%Y-%m-%d %H:%M")
        lines.append(f"{icon} **{doc.filename}** — {created}")
        lines.append(f"   `{doc.id}` — Status: {doc.status.value}")
        if doc.status == AuditStatus.completed:
            lines.append(f"   Type `doc: {doc.id}` to view results\n")
        elif doc.status == AuditStatus.processing:
            lines.append("   Still processing\n")
        else:
            lines.append(f"   Type `doc: {doc.id}` to retry\n")

    await cl.Message(content="\n".join(lines)).send()
    await _show_main_menu()


async def _show_document(doc_id: str):
    try:
        uid = uuid.UUID(doc_id)
    except ValueError:
        await cl.Message(content=f"Invalid document ID: `{doc_id}`").send()
        await _show_main_menu()
        return

    async with async_session_factory() as session:
        result = await session.execute(select(LeaseDocument).where(LeaseDocument.id == uid))
        doc = result.scalar_one_or_none()

        if not doc:
            await cl.Message(content=f"Document not found: `{doc_id}`").send()
            await _show_main_menu()
            return

        if doc.status != AuditStatus.completed:
            await cl.Message(
                content=f"Document **{doc.filename}** is `{doc.status.value}`.\n\n"
                "Run an audit by uploading again or type `menu`."
            ).send()
            await _show_main_menu()
            return

        ext_result = await session.execute(
            select(LeaseExtraction).where(LeaseExtraction.document_id == uid)
        )
        ext = ext_result.scalar_one_or_none()

        math_result = await session.execute(
            select(MathValidation).where(MathValidation.document_id == uid)
        )
        math = math_result.scalar_one_or_none()

        flags_result = await session.execute(
            select(ComplianceFlag).where(ComplianceFlag.document_id == uid)
        )
        flags = list(flags_result.scalars().all())

    lines = [f"## 📄 {doc.filename}\n"]
    lines.append(f"**Document ID:** `{doc.id}`")
    lines.append(f"**Uploaded:** {doc.created_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Pages:** {doc.page_count or 'N/A'}")
    lines.append("**Status:** ✅ Completed\n")

    if ext:
        raw = ext.raw_json or {}
        lease_terms = raw.get("lease_terms") or raw
        lines.append("### Extracted Terms")
        key_labels = [
            ("lessor", "Lessor"), ("lessee", "Lessee"), ("property_address", "Address"),
            ("lease_start_date", "Start Date"), ("lease_end_date", "End Date"),
            ("lease_term_months", "Term (months)"),
            ("base_rent_monthly", "Base Rent (mo)"), ("security_deposit", "Deposit"),
            ("escalation_type", "Escalation"), ("escalation_rate", "Rate"),
            ("late_fee_amount", "Late Fee"), ("grace_period_days", "Grace Period"),
        ]
        for key, label in key_labels:
            val = lease_terms.get(key)
            if val is not None:
                if key in ("base_rent_monthly", "security_deposit"):
                    lines.append(f"  - **{label}:** ${val:,.2f}")
                elif key == "escalation_rate":
                    lines.append(f"  - **{label}:** {val}%")
                else:
                    lines.append(f"  - **{label}:** {val}")
        conf = raw.get("confidence_score") or 0
        lines.append(f"\n  **Confidence:** {conf:.1%}")

        rs = lease_terms.get("rent_schedule")
        if rs:
            lines.append("\n### Rent Schedule")
            for e in rs:
                esc = f" (+{e['escalation_percent']}%)" if e.get("escalation_percent") else ""
                lines.append(f"  - Year {e['year']}: ${e['annual_rent']:,.2f}/yr (${e['monthly_rent']:,.2f}/mo){esc}")

    if math:
        lines.append("\n### Math Validation")
        if math.is_valid:
            lines.append("  ✅ **Pass**")
        else:
            lines.append("  ❌ **Fail**")
            details = math.discrepancy_details or {}
            for d in details.get("discrepancies", []):
                lines.append(f"    - {d}")

    if flags:
        lines.append(f"\n### Compliance — {len(flags)} flag(s)")
        risk_icons = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        for f in flags:
            icon = risk_icons.get(f.risk_level.value, "⚪")
            lines.append(f"  {icon} **{f.rule_name}** ({f.risk_level.value})")
            lines.append(f"    {f.description}")

    await cl.Message(content="\n".join(lines)).send()
    await _show_main_menu()


async def _handle_search(query: str):
    ensure_collection()
    retriever = get_hybrid_retriever()

    msg = cl.Message(content=f"🔍 Searching for: \"{query}\"...")
    await msg.send()

    try:
        nodes = await asyncio.to_thread(retriever.retrieve, query)
    except Exception as e:
        await cl.Message(content=f"Search failed: {e}").send()
        await _show_main_menu()
        return

    if not nodes:
        await cl.Message(content="No results found. Try a different query.").send()
        await _show_main_menu()
        return

    lines = [f"### Search Results for \"{query}\"\n"]
    for i, node in enumerate(nodes, 1):
        score = node.score or 0
        section = node.metadata.get("section_title", "Unknown")
        page = node.metadata.get("page_number", "")
        page_str = f" (p. {page})" if page else ""
        text = node.text[:400]
        lines.append(f"**{i}. {section}**{page_str} — relevance: {score:.1%}")
        lines.append(f"  > {text}\n")

    await cl.Message(content="\n".join(lines)).send()
    await _show_main_menu()


async def _run_audit_for_document(doc_id: str):
    msg = cl.Message(content="⏳ Starting audit pipeline...")
    await msg.send()

    async with async_session_factory() as session:
        result = await session.execute(
            select(LeaseDocument).where(LeaseDocument.id == uuid.UUID(doc_id))
        )
        doc = result.scalar_one_or_none()

    if not doc:
        await cl.Message(content="Document not found in database.").send()
        return

    graph = _get_graph()

    initial_state: AgentState = {
        "document_id": doc_id,
        "filename": doc.filename,
        "storage_path": doc.storage_path,
        "content_hash": doc.content_hash,
        "parsed_doc": None,
        "sections": None,
        "extraction": None,
        "lease_terms": None,
        "math_validation": None,
        "compliance_report": None,
        "audit_result": None,
        "errors": [],
        "warnings": [],
        "input_security": None,
        "output_security": None,
    }

    try:
        final_state = await asyncio.to_thread(graph.invoke, initial_state)

        errors = final_state.get("errors", [])
        if errors:
            await cl.Message(content="❌ Audit failed:\n" + "\n".join(errors)).send()
            return

        async with async_session_factory() as session:
            doc_ref = await session.get(LeaseDocument, uuid.UUID(doc_id))

            ext = final_state.get("extraction")
            if ext:
                session.add(LeaseExtraction(
                    document_id=uuid.UUID(doc_id),
                    raw_json=ext,
                    llm_model=cfg.get("llm", {}).get("model", "legal-model"),
                ))

            math_val = final_state.get("math_validation")
            if math_val:
                session.add(MathValidation(
                    document_id=uuid.UUID(doc_id),
                    is_valid=math_val.get("is_valid", False),
                    discrepancy_details={
                        "discrepancies": math_val.get("discrepancies", []),
                        "projected_schedule": math_val.get("projected_schedule", []),
                    },
                ))

            compliance = final_state.get("compliance_report")
            if compliance:
                for flag in compliance.get("flags", []):
                    session.add(ComplianceFlag(
                        document_id=uuid.UUID(doc_id),
                        rule_id=flag["rule_id"],
                        rule_name=flag["rule_name"],
                        risk_level=flag["risk_level"],
                        description=flag["description"],
                    ))

            if doc_ref:
                doc_ref.status = AuditStatus.completed
                doc_ref.updated_at = datetime.utcnow()
            await session.commit()

        result_text = _format_audit_result(final_state)
        await cl.Message(content=result_text).send()

    except Exception as e:
        async with async_session_factory() as session:
            doc_ref = await session.get(LeaseDocument, uuid.UUID(doc_id))
            if doc_ref:
                doc_ref.status = AuditStatus.failed
                await session.commit()
        await cl.Message(content=f"❌ Audit failed: {e}").send()

    await _show_main_menu()
