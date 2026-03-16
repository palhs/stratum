"""
reasoning/app/pipeline/term_dict.py
Vietnamese financial term dictionary loader and label applicator.
Phase 7 | Plan 03 | Requirement: REPT-03

Design decisions (locked):
- load_term_dict() is cached at module level — JSON parsed once per process.
- apply_terms() accepts a plain dict (serialized report JSON), NOT a Pydantic model.
  This avoids a dependency on report_schema.py (Plan 02) and keeps Plan 03
  parallel-safe in Wave 2.
- Only structured label fields are replaced — narrative text is NOT modified.
  Vietnamese narrative generation is handled by compose_report_node (Plan 04)
  via a Gemini call.
- English financial abbreviations (P/E, P/B, ATH, ETF, MA, RSI, FOMC, SBV,
  GDP, CPI, etc.) are kept as-is in narrative text per CONTEXT.md decision.
- apply_terms() returns a deep copy — input dict is never mutated.
- apply_terms() is idempotent — applying twice produces the same result because
  Vietnamese values are not keys in the same lookup tables.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Module-level cache — loaded once on first call to load_term_dict()
# ---------------------------------------------------------------------------

_TERM_DICT: dict[str, Any] | None = None
_TERM_DICT_PATH = Path(__file__).parent / "term_dict_vi.json"


def load_term_dict() -> dict[str, Any]:
    """Load the Vietnamese financial term dictionary from term_dict_vi.json.

    Returns a nested dict with keys:
        tiers, macro_labels, valuation_labels, structure_labels,
        card_headers, conflict_patterns, data_warning,
        metrics, macro_concepts, narrative_connectors

    The result is cached at module level — the JSON file is read once per
    Python process.
    """
    global _TERM_DICT
    if _TERM_DICT is None:
        with open(_TERM_DICT_PATH, encoding="utf-8") as fh:
            _TERM_DICT = json.load(fh)
    return _TERM_DICT


def apply_terms(report_json: dict[str, Any]) -> dict[str, Any]:
    """Replace English structured labels with Vietnamese equivalents.

    Accepts a plain dict (e.g. the value of ReportOutput.report_json after
    serialization via model_dump_json + json.loads).  Does NOT accept a
    Pydantic model instance — call .model_dump() or json.loads(card.model_dump_json())
    before passing here.

    Fields replaced:
        report_json["entry_quality"]["tier"]      — via tiers lookup
        report_json["macro_regime"]["label"]      — via macro_labels lookup
        report_json["valuation"]["label"]         — via valuation_labels lookup
        report_json["structure"]["label"]         — via structure_labels lookup
        report_json["conflict"]["pattern_name"]   — via conflict_patterns lookup
            (only when "conflict" key present and value is not None)

    All replacements use dict.get(value, value) — unknown values pass through
    unchanged (graceful degradation).

    Narrative text fields are intentionally NOT modified; they are generated
    directly in Vietnamese by compose_report_node via Gemini.

    Args:
        report_json: Plain dict representation of a report card structure.

    Returns:
        A new deep-copied dict with structured labels translated.  The input
        dict is never mutated.
    """
    d = copy.deepcopy(report_json)
    td = load_term_dict()

    tiers: dict[str, str] = td["tiers"]
    macro_labels: dict[str, str] = td["macro_labels"]
    valuation_labels: dict[str, str] = td["valuation_labels"]
    structure_labels: dict[str, str] = td["structure_labels"]
    conflict_patterns: dict[str, str] = td["conflict_patterns"]

    # --- Entry quality tier ---
    if isinstance(d.get("entry_quality"), dict):
        eq = d["entry_quality"]
        if "tier" in eq:
            eq["tier"] = tiers.get(eq["tier"], eq["tier"])

    # --- Macro regime label ---
    if isinstance(d.get("macro_regime"), dict):
        mr = d["macro_regime"]
        if "label" in mr:
            mr["label"] = macro_labels.get(mr["label"], mr["label"])

    # --- Valuation label ---
    if isinstance(d.get("valuation"), dict):
        val = d["valuation"]
        if "label" in val:
            val["label"] = valuation_labels.get(val["label"], val["label"])

    # --- Structure label ---
    if isinstance(d.get("structure"), dict):
        struct = d["structure"]
        if "label" in struct:
            struct["label"] = structure_labels.get(struct["label"], struct["label"])

    # --- Conflict pattern name (optional section) ---
    conflict = d.get("conflict")
    if isinstance(conflict, dict) and "pattern_name" in conflict:
        pn = conflict["pattern_name"]
        conflict["pattern_name"] = conflict_patterns.get(pn, pn)

    return d
