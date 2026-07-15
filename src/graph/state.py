from typing import TypedDict, Optional


class AgentState(TypedDict):
    document_id: str
    filename: str
    storage_path: str
    content_hash: str
    parsed_doc: Optional[dict]
    sections: Optional[list[dict]]
    extraction: Optional[dict]
    lease_terms: Optional[dict]
    math_validation: Optional[dict]
    compliance_report: Optional[dict]
    audit_result: Optional[dict]
    errors: list[str]
    warnings: list[str]
    input_security: Optional[dict]
    output_security: Optional[dict]
