"""Regression coverage for PII removed before trace persistence/export."""

from shared.guardrails.pii_redactor import redact_payload, redact_text
from shared.tracing.langfuse import _safe_payload


def test_pii_redactor_masks_address_in_text_and_structured_payload() -> None:
    assert redact_text("Address: 28 Sycamore Street") == "Address: [ADDRESS_REDACTED]"
    assert redact_payload({"address": "28 Sycamore Street"}) == {
        "address": "[ADDRESS_REDACTED]"
    }


def test_safe_payload_redacts_nested_address_fields() -> None:
    payload = {
        "discharge": {
            "address": "28 Sycamore Street, Springfield, IL 62704",
            "mailing_address": {"line1": "PO Box 12"},
            "ward": "3B",
        }
    }

    assert _safe_payload(payload) == {
        "discharge": {
            "address": "[ADDRESS_REDACTED]",
            "mailing_address": "[ADDRESS_REDACTED]",
            "ward": "3B",
        }
    }


def test_safe_payload_redacts_pii_in_free_text() -> None:
    payload = {"prompt": "Address: 28 Sycamore Street, Springfield, IL 62704\nCall +1 6175551234"}

    assert _safe_payload(payload) == {
        "prompt": "Address: [ADDRESS_REDACTED]\nCall [PHONE_REDACTED]"
    }


def test_safe_payload_redacts_address_in_embedded_json_prompt() -> None:
    payload = {
        "prompt": 'Clinical data: {"patient_name": "Thomas Wright", '
        '"address": "28 Sycamore Street, Springfield, IL 62704"}'
    }

    assert _safe_payload(payload) == {
        "prompt": 'Clinical data: {"patient_name": "Thomas Wright", '
        '"address": "[ADDRESS_REDACTED]"}'
    }
