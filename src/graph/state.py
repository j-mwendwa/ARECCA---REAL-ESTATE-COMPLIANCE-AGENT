from typing import TypedDict


class AgentState(TypedDict):
    document_id: str
    filename: str
    storage_path: str
    content_hash: str
    parsed_doc: dict | None
    sections: list[dict] | None
    extraction: dict | None
    lease_terms: dict | None
    math_validation: dict | None
    compliance_report: dict | None
    audit_result: dict | None
    errors: list[str]
    warnings: list[str]
    input_security: dict | None
    output_security: dict | None
