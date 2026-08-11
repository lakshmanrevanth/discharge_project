"""Clinical Watcher Tool + Roots (SSoT §3.5, §3.8).

Discovers discharge / lab / bill files inside client-declared Roots only.
MUST NOT take raw filesystem paths as tool parameters — uses ctx.list_roots().
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from fastmcp import Context, FastMCP

from mcp_servers.primary.roots import (
    INTAKE_SUBFOLDERS,
    assert_inside_root,
    file_uri_to_path,
    safe_join,
)
from shared.logger import get_logger

logger = get_logger("clinical_watcher")


def _patient_id_from_name(filename: str) -> str | None:
    """Extract patient id prefix like P001 / P1019 from P1019_thomas_wright.txt.

    Any digit length is accepted so new patients (P001, P50, P1025, …) work.
    """
    stem = filename.split(".")[0]  # drop extensions / .ocr.txt style later
    # Handle P1019_labs / P1019_bill / P1019_name_name
    if "_" in stem:
        prefix = stem.split("_", 1)[0]
    else:
        prefix = stem
    if prefix.startswith("P") and prefix[1:].isdigit():
        return prefix.upper()
    return None


def _scan_root(root_path: Path) -> dict:
    """Scan doctor_reports / lab_reports / bills under one Root path."""
    cases: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: {folder: [] for folder in INTAKE_SUBFOLDERS}
    )

    for folder_name in INTAKE_SUBFOLDERS:
        folder = safe_join(root_path, folder_name)
        if not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if not path.is_file():
                continue
            # Guard every file path (defense in depth)
            assert_inside_root(path, root_path)
            patient_id = _patient_id_from_name(path.name)
            if patient_id is None:
                continue
            cases[patient_id][folder_name].append(path.name)

    # Stable output order
    ordered = []
    for patient_id in sorted(cases.keys()):
        ordered.append({"patient_id": patient_id, "files": cases[patient_id]})

    return {
        "root_path": str(root_path),
        "case_count": len(ordered),
        "cases": ordered,
    }


def register_watcher_tools(mcp: FastMCP) -> None:
    """Attach the Clinical Watcher tool to the Primary MCP server."""

    @mcp.tool(
        name="clinical_watcher",
        title="Clinical Watcher Tool",
        description=(
            "Discover new discharge, lab, and bill files inside MCP Roots. "
            "Uses ctx.list_roots() only — never pass raw filesystem paths."
        ),
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def clinical_watcher(ctx: Context) -> str:
        """List intake files under all Roots declared by the MCP client."""
        try:
            roots = await ctx.list_roots()
        except Exception as exc:
            # Client did not advertise Roots capability
            return json.dumps(
                {
                    "error": "no_roots",
                    "message": (
                        "Client did not declare MCP Roots "
                        f"({type(exc).__name__}: {exc}). "
                        "Monitor must register file:///.../data/input before calling this tool."
                    ),
                    "cases": [],
                    "case_count": 0,
                }
            )

        if not roots:
            return json.dumps(
                {
                    "error": "no_roots",
                    "message": "Client did not declare any Roots. "
                    "Monitor must register file:///.../data/input before calling this tool.",
                    "cases": [],
                    "case_count": 0,
                }
            )

        results = []
        for root in roots:
            uri = str(root.uri)
            try:
                root_path = file_uri_to_path(uri)
                if not root_path.is_dir():
                    results.append(
                        {
                            "root_uri": uri,
                            "error": "root_not_a_directory",
                            "cases": [],
                            "case_count": 0,
                        }
                    )
                    continue
                scanned = _scan_root(root_path)
                scanned["root_uri"] = uri
                if root.name:
                    scanned["root_name"] = root.name
                results.append(scanned)
            except ValueError as exc:
                logger.warning("Root rejected: %s (%s)", uri, exc)
                results.append(
                    {
                        "root_uri": uri,
                        "error": str(exc),
                        "cases": [],
                        "case_count": 0,
                    }
                )

        total_cases = sum(r.get("case_count", 0) for r in results)
        payload = {
            "roots_scanned": len(results),
            "case_count": total_cases,
            "results": results,
        }
        logger.info("clinical_watcher found %s case(s) across %s root(s)", total_cases, len(results))
        return json.dumps(payload, indent=2)
