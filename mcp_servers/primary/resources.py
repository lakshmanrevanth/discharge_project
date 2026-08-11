"""MCP Resources — exact URIs from SSoT §3.3 (MUST NOT rename).

Exposes rules.yaml slices, abbreviations, report template, and per-patient
discharge/lab text from data/input/.
"""

from __future__ import annotations

import yaml
from fastmcp import FastMCP

from mcp_servers.primary.rules_loader import (
    find_patient_file,
    load_rules,
    read_text_file,
)
from shared.settings import get_path


def register_resources(mcp: FastMCP) -> None:
    """Attach all Primary MCP Resources to the server."""

    @mcp.resource(
        uri="resource://clinical-rules/completeness",
        name="clinical_rules_completeness",
        title="Clinical Completeness Rules",
        description="Mandatory fields from configs/rules.yaml (completeness validation)",
        mime_type="text/yaml",
    )
    def clinical_rules_completeness() -> str:
        rules = load_rules()
        payload = {
            "mandatory_clinical_fields": rules.get("mandatory_clinical_fields", []),
            "mandatory_prescription_fields": rules.get("mandatory_prescription_fields", []),
        }
        return yaml.safe_dump(payload, sort_keys=False)

    @mcp.resource(
        uri="resource://clinical-rules/cross-validation",
        name="clinical_rules_cross_validation",
        title="Clinical Cross-Validation Rules",
        description="Cross-validation policies and risk weights from configs/rules.yaml only",
        mime_type="text/yaml",
    )
    def clinical_rules_cross_validation() -> str:
        # SSoT §3.3: content from rules.yaml — do not inject FA5 Table 4 IDs here
        rules = load_rules()
        payload = {
            "clinical_validation_policies": rules.get("clinical_validation_policies", {}),
            "risk_scoring_matrix": rules.get("risk_scoring_matrix", {}),
            "business_rules": rules.get("business_rules", {}),
            "quality_thresholds": rules.get("quality_thresholds", {}),
        }
        return yaml.safe_dump(payload, sort_keys=False)

    @mcp.resource(
        uri="resource://medical-abbreviations",
        name="medical_abbreviations",
        title="Medical Abbreviation Map",
        description="Abbreviation expansion dictionary from rules.yaml",
        mime_type="text/yaml",
    )
    def medical_abbreviations() -> str:
        rules = load_rules()
        abbrev = (
            rules.get("normalization_standards", {}).get("abbreviation_map", {})
        )
        return yaml.safe_dump(abbrev, sort_keys=False)

    @mcp.resource(
        uri="resource://report-template/html",
        name="report_template_html",
        title="Discharge Summary HTML Template",
        description="HTML template for discharge summary / reports",
        mime_type="text/html",
    )
    async def report_template_html() -> str:
        template_path = get_path("report_template")
        return await read_text_file(template_path)

    @mcp.resource(
        uri="resource://discharge-report/{patient_id}",
        name="discharge_report",
        title="Discharge Report Text",
        description="Raw discharge document text for a patient_id under data/input/doctor_reports",
        mime_type="text/plain",
    )
    async def discharge_report(patient_id: str) -> str:
        folder = get_path("input_doctor_reports")
        path = find_patient_file(folder, patient_id)
        if path is None:
            return f"[no discharge report found for {patient_id} in {folder}]"
        return await read_text_file(path)

    @mcp.resource(
        uri="resource://lab-report/{patient_id}",
        name="lab_report",
        title="Lab Report Text",
        description="Raw lab report text for a patient_id under data/input/lab_reports",
        mime_type="text/plain",
    )
    async def lab_report(patient_id: str) -> str:
        folder = get_path("input_lab_reports")
        path = find_patient_file(folder, patient_id)
        if path is None:
            return f"[no lab report found for {patient_id} in {folder}]"
        return await read_text_file(path)
