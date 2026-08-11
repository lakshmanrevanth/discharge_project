"""Risk heatmap grouping for Validation Report (Secondary MCP tool shape)."""

from __future__ import annotations

from dashboard.components.analytics import heatmap_from_findings, load_heatmap


def test_heatmap_from_findings_groups_by_severity():
    findings = [
        {
            "rule_id": "allergy_contradiction_check",
            "severity": "critical",
            "weight": 8,
            "blocking": True,
            "message": "Allergy conflict",
            "field": "medications",
        },
        {
            "rule_id": "med_omission_check",
            "severity": "warning",
            "weight": 3,
            "blocking": False,
            "message": "Med omitted",
            "field": "medications",
        },
        {
            "rule_id": "missing_address",
            "severity": "info",
            "weight": 1,
            "blocking": False,
            "message": "Address missing",
            "field": "address",
        },
        {
            "rule_id": "bill_unpaid",
            "severity": "critical",
            "weight": 5,
            "blocking": True,
            "message": "Bill unpaid",
            "field": "payment_status",
        },
    ]
    heat = heatmap_from_findings(findings)
    assert heat["totals"]["critical"] == 2
    assert heat["totals"]["warning"] == 1
    assert heat["totals"]["info"] == 1
    assert len(heat["cells"]["critical"]) == 2
    row0 = heat["cells"]["critical"][0]
    assert row0["rule_id"] == "allergy_contradiction_check"
    assert row0["message"] == "Allergy conflict"
    assert row0["field"] == "medications"


def test_heatmap_merges_title_case_severity():
    heat = heatmap_from_findings(
        [
            {"rule_id": "a", "severity": "Critical", "weight": 2, "blocking": True},
            {"rule_id": "b", "severity": "critical", "weight": 1, "blocking": False},
        ]
    )
    assert set(heat["totals"]) == {"critical"}
    assert heat["totals"]["critical"] == 2


def test_heatmap_empty_findings():
    heat = heatmap_from_findings([])
    assert heat["cells"] == {}
    assert heat["totals"] == {}


def test_load_heatmap_falls_back_local(monkeypatch):
    async def _boom(findings):
        raise RuntimeError("offline")

    monkeypatch.setattr(
        "dashboard.components.analytics.try_secondary_heatmap",
        _boom,
    )
    heat, src = load_heatmap(
        [{"rule_id": "x", "severity": "warning", "weight": 1, "blocking": False}]
    )
    assert src == "local"
    assert heat["totals"]["warning"] == 1
