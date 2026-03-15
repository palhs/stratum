"""
reasoning/app/nodes/grounding_check.py — grounding_check_node: numeric claim attribution.
Phase 6 | Plan 05 | Requirement: REAS-05

Verifies that every non-None float field in upstream node outputs has a corresponding
source citation. Qualitative string fields are NOT checked — only typed float values
require record-level attribution.

CRITICAL constraints (REAS-05):
- Verify all float fields in node output Pydantic models
- Qualitative claims (str fields) need data SOURCE attribution only — not record ID
  → string fields are NOT checked by this node
- Fail mode: raise GroundingError (never return a warning) when claims are unattributed
- Only float fields and derived calculations require record ID citations
- Do NOT regex-scan narrative strings — check only typed Pydantic fields
- None-valued float fields are skipped — only non-None floats require attribution
- Nested Pydantic models in lists (e.g., RegimeProbability) are checked via their
  own source_analogue_id field, not the parent sources dict
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from reasoning.app.nodes.state import (
    GroundingError,
    GroundingResult,
    MacroRegimeOutput,
    ReportState,
    StructureOutput,
    ValuationOutput,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_float_fields(model: BaseModel, prefix: str) -> list[tuple[str, str]]:
    """
    Recursively walk a Pydantic model and collect float-valued (non-None) fields.

    Returns a list of (qualified_path, short_field_name) tuples where:
    - qualified_path: e.g. "macro_regime_output.top_confidence"
    - short_field_name: the bare field name ("top_confidence")

    Traversal rules:
    - float-valued fields (isinstance(value, float) and value is not None): included
    - None-valued fields: skipped
    - str, bool, int, list[str], dict: skipped
    - Nested BaseModel instances: recurse with extended prefix
    - List of BaseModel instances: handled separately via _has_own_source (not yielded here)
    - Lists of primitives: skipped
    """
    results: list[tuple[str, str]] = []

    for field_name in type(model).model_fields:
        value = getattr(model, field_name, None)

        if value is None:
            continue  # None floats are not checked

        if isinstance(value, float):
            results.append((f"{prefix}.{field_name}", field_name))

        elif isinstance(value, BaseModel):
            # Nested Pydantic model — recurse
            nested_results = _collect_float_fields(value, f"{prefix}.{field_name}")
            results.extend(nested_results)

        # list[BaseModel] handled separately in _verify_output for source_analogue_id logic
        # str, bool, int, list[str], dict: skip

    return results


def _verify_output(
    output: BaseModel,
    output_key: str,
    errors: list[str],
) -> None:
    """
    Verify all float fields in a node output model have source attribution.

    For direct float fields: checks if field_name in output.sources
    For list[BaseModel] items that have their own source field (source_analogue_id):
        checks that source_analogue_id is a non-empty string
    Appends error strings to the errors list for all unattributed claims.
    """
    sources: dict[str, str] = getattr(output, "sources", {}) or {}

    # 1. Check direct float fields on the top-level model
    direct_floats = _collect_float_fields(output, output_key)
    for qualified_path, field_name in direct_floats:
        if field_name not in sources or not sources[field_name]:
            errors.append(
                f"[{output_key}] float field '{field_name}' "
                f"(path: {qualified_path}) has no source attribution"
            )

    # 2. Check list[BaseModel] items that carry their own source field
    for field_name in type(output).model_fields:
        value = getattr(output, field_name, None)
        if not isinstance(value, list):
            continue
        for idx, item in enumerate(value):
            if not isinstance(item, BaseModel):
                continue
            # Check if this nested model has its own source field (source_analogue_id)
            source_analogue_id = getattr(item, "source_analogue_id", None)
            # Check if this item has float fields that need attribution
            nested_floats = _collect_float_fields(item, f"{output_key}.{field_name}[{idx}]")
            if not nested_floats:
                continue  # No float fields to check
            # For nested items with source_analogue_id: use that as attribution
            if source_analogue_id is not None:
                # source_analogue_id attribute exists on the model
                if not source_analogue_id:  # empty string = unattributed
                    for qualified_path, nested_field in nested_floats:
                        errors.append(
                            f"[{output_key}] nested float '{nested_field}' "
                            f"(path: {qualified_path}) has empty source_analogue_id"
                        )
            else:
                # No source_analogue_id — fall back to parent sources dict
                nested_sources: dict[str, str] = getattr(item, "sources", {}) or {}
                for qualified_path, nested_field in nested_floats:
                    if nested_field not in nested_sources or not nested_sources[nested_field]:
                        errors.append(
                            f"[{output_key}] nested float '{nested_field}' "
                            f"(path: {qualified_path}) has no source attribution"
                        )


# ---------------------------------------------------------------------------
# Node function
# ---------------------------------------------------------------------------


def grounding_check_node(state: ReportState) -> dict[str, Any]:
    """
    LangGraph node: verifies all numeric claims in upstream node outputs are attributed.

    State reads:
        - state["macro_regime_output"]: Optional[MacroRegimeOutput]
        - state["valuation_output"]: Optional[ValuationOutput]
        - state["structure_output"]: Optional[StructureOutput]

    State writes:
        - state["grounding_result"]: GroundingResult

    Raises:
        GroundingError: when any float field lacks source attribution.
        The error message lists ALL unattributed claims (not just the first).

    Behavior:
        - Only inspects outputs that are not None (partial state is valid)
        - float fields that are None are skipped (only non-None floats are checked)
        - str, bool, int, list[str], dict fields are never checked
        - Nested Pydantic models (e.g., RegimeProbability) use source_analogue_id
          as their attribution mechanism
    """
    # Keys to inspect — in dependency order
    _KEYS_TO_CHECK: list[tuple[str, type[BaseModel]]] = [
        ("macro_regime_output", MacroRegimeOutput),
        ("valuation_output", ValuationOutput),
        ("structure_output", StructureOutput),
    ]

    errors: list[str] = []
    checked_outputs: list[str] = []

    for key, _ in _KEYS_TO_CHECK:
        output = state.get(key)  # type: ignore[call-overload]
        if output is None:
            continue
        checked_outputs.append(key)
        _verify_output(output, key, errors)

    if errors:
        error_count = len(errors)
        error_details = "\n".join(f"  - {e}" for e in errors)
        raise GroundingError(
            f"Grounding check failed — {error_count} unattributed numeric claim"
            f"{'s' if error_count != 1 else ''}:\n{error_details}"
        )

    return {
        "grounding_result": GroundingResult(
            status="pass",
            checked_outputs=checked_outputs,
            unattributed_claims=[],
        )
    }
