"""MCP Prompts — exact names/params from SSoT §3.4 (MUST NOT rename).

Bodies come from configs/prompts.yaml. Agents must call get_prompt — never
hardcode these strings inside agent code.
"""

from __future__ import annotations

from fastmcp import FastMCP

from mcp_servers.primary.rules_loader import load_prompts_config


def _fill_template(template: str, **kwargs: str) -> str:
    """Replace {{key}} placeholders with values."""
    text = template
    for key, value in kwargs.items():
        text = text.replace("{{" + key + "}}", str(value))
    return text


def register_prompts(mcp: FastMCP) -> None:
    """Attach all Primary MCP Prompts to the server."""

    @mcp.prompt(
        name="discharge-extraction-prompt",
        title="Discharge Extraction Prompt",
        description="Used by Clinical Extractor Agent (params: language, doc_types)",
    )
    def discharge_extraction_prompt(language: str, doc_types: str) -> str:
        cfg = load_prompts_config()["discharge-extraction-prompt"]
        return _fill_template(cfg["template"], language=language, doc_types=doc_types)

    @mcp.prompt(
        name="ehr-cross-validation-prompt",
        title="EHR Cross-Validation Prompt",
        description="Used by Clinical Validation Agent (params: patient_id)",
    )
    def ehr_cross_validation_prompt(patient_id: str) -> str:
        cfg = load_prompts_config()["ehr-cross-validation-prompt"]
        return _fill_template(cfg["template"], patient_id=patient_id)

    @mcp.prompt(
        name="abbreviation-normalization-prompt",
        title="Abbreviation Normalization Prompt",
        description="Used by Clinical Normalizer Agent (params: source_language)",
    )
    def abbreviation_normalization_prompt(source_language: str) -> str:
        cfg = load_prompts_config()["abbreviation-normalization-prompt"]
        return _fill_template(cfg["template"], source_language=source_language)

    @mcp.prompt(
        name="summary-generation-prompt",
        title="Summary Generation Prompt",
        description="Used by Discharge Summary Generator (params: risk_level, audience)",
    )
    def summary_generation_prompt(risk_level: str, audience: str) -> str:
        cfg = load_prompts_config()["summary-generation-prompt"]
        return _fill_template(cfg["template"], risk_level=risk_level, audience=audience)

    @mcp.prompt(
        name="rag-answer-prompt",
        title="RAG Answer Prompt",
        description="Used by Agno RAG Generation Agent (params: context_length)",
    )
    def rag_answer_prompt(context_length: str) -> str:
        cfg = load_prompts_config()["rag-answer-prompt"]
        return _fill_template(cfg["template"], context_length=context_length)
