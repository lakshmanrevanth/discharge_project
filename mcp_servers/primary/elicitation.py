"""Dynamic Elicitation schema builder for the Clinical Rules Engine Tool (SSoT §3.7).

Beginner picture:
  - Rules Engine finds N missing NON-BLOCKING fields for one patient case.
  - We build ONE Pydantic model with those N fields (all optional) and call
    ctx.elicit() ONCE — never one call per field (SSoT §3.7).
  - The reviewer can leave any field blank and accept, decline (gaps stay
    unresolved -> Mandatory HITL), or cancel (abort -> Mandatory HITL).
"""

from __future__ import annotations

from pydantic import Field, create_model

# Field name (from rules.yaml mandatory_clinical_fields) -> Python type used
# to build the reviewer form. Anything not listed here defaults to str.
#
# FastMCP's elicitation schema only allows flat primitive types — string,
# integer, number, boolean (SSoT §3.7 "simple object schemas", no arrays or
# nested objects) — so list-shaped fields (consulting_doctors, allergies)
# stay `str` here; a reviewer enters a comma-separated value if there is
# more than one.
TYPE_HINTS: dict[str, type] = {
    "age": int,
}


def build_missing_fields_schema(missing_fields: list[str]):
    """Build one dynamic Pydantic model covering every missing field.

    Every field has a default of None, so a reviewer may leave any of them
    blank — but the type annotation itself stays a bare (non-Optional) type.
    FastMCP's elicitation schema validator only allows flat primitive/array
    types (SSoT §3.7 "simple object schemas"); an Optional[...] annotation
    produces an anyOf-with-null schema that it rejects. A plain type with a
    None default still makes the field optional to pydantic, without that
    anyOf wrapper.

    Only called with FLAT mandatory_clinical_fields names — always valid
    Python identifiers — so no name-sanitizing is needed.
    """
    fields: dict[str, tuple] = {}
    for name in missing_fields:
        py_type = TYPE_HINTS.get(name, str)
        fields[name] = (
            py_type,
            Field(default=None, description=f"Reviewer-supplied value for '{name}'"),
        )
    return create_model("MissingFieldsSchema", **fields)
