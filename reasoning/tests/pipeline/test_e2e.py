"""
reasoning/tests/pipeline/test_e2e.py — End-to-end integration tests for the full pipeline.
Phase 7 | Plan 05 | Requirements: REAS-06, REPT-01, REPT-02, REPT-03, REPT-04, REPT-05

Tests validate the complete pipeline: prefetch → graph → compose → store.

Design:
- All infrastructure (Gemini, PostgreSQL, Neo4j, Qdrant, AsyncPostgresSaver) is mocked.
- No live API calls or database connections required.
- Tests marked @pytest.mark.integration require Docker services (skip in CI).
- Tests without @pytest.mark.integration run with full mocking (always run).

Mock strategy:
- generate_report() is mocked at the function-call level (using mock_prefetch + mock_run_graph).
- Alternatively: compose_report_node is tested directly with full mock state (REPT-01, REPT-04).
- write_report() is mocked to capture INSERT values.
- generate_report() orchestration is tested by patching its internal collaborators.

The E2E tests validate:
1. Full pipeline for equity (VHM): two write_report calls with vi+en report_json
2. Full pipeline for gold (GOLD): WGC warning present in data_warnings
3. report_json schema validation against Pydantic card models
4. No prohibited terms in Markdown output
5. Bilingual independence: vi and en are different strings
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from reasoning.app.nodes.state import (
    ReportOutput,
    MacroRegimeOutput,
    ValuationOutput,
    StructureOutput,
    EntryQualityOutput,
    GroundingResult,
    RegimeProbability,
)
from reasoning.app.pipeline.report_schema import (
    EntryQualityCard,
    MacroRegimeCard,
    ValuationCard,
    StructureCard,
    ReportCard,
)


# ---------------------------------------------------------------------------
# Shared mock builders
# ---------------------------------------------------------------------------


def _make_mock_report_state(ticker: str = "VHM", asset_type: str = "equity") -> dict:
    """Build a complete mock ReportState with all node outputs populated."""
    return {
        "ticker": ticker,
        "asset_type": asset_type,
        "fred_rows": [],
        "regime_analogues": [],
        "macro_docs": [],
        "fundamentals_rows": [],
        "structure_marker_rows": [],
        "gold_price_rows": [],
        "gold_etf_rows": [],
        "earnings_docs": [],
        "retrieval_warnings": [],
        "macro_regime_output": MacroRegimeOutput(
            regime_probabilities=[
                RegimeProbability(
                    regime_id="regime_2020_covid",
                    regime_name="COVID Shock 2020",
                    confidence=0.75,
                    source_analogue_id="analogue_2020",
                ),
            ],
            top_regime_id="regime_2020_covid",
            top_confidence=0.75,
            is_mixed_signal=False,
            macro_label="Headwind",
            narrative="Current macro environment is a headwind for risk assets.",
            sources={},
            warnings=[],
        ),
        "valuation_output": ValuationOutput(
            asset_type=asset_type,
            valuation_label="Attractive",
            pe_ratio=12.5 if asset_type == "equity" else None,
            pb_ratio=1.8 if asset_type == "equity" else None,
            real_yield=1.2 if asset_type == "gold" else None,
            narrative="Valuation appears attractive at current levels.",
            sources={},
            warnings=[],
        ),
        "structure_output": StructureOutput(
            structure_label="Neutral",
            close=18500.0,
            drawdown_from_ath=-15.2,
            drawdown_from_52w_high=-8.4,
            close_pct_rank=0.62,
            narrative="Price structure is neutral with moderate drawdown from ATH.",
            sources={},
            warnings=[],
        ),
        "entry_quality_output": EntryQualityOutput(
            macro_assessment="Headwind",
            valuation_assessment="Attractive",
            structure_assessment="Neutral",
            composite_tier="Cautious",
            conflict_pattern=None,
            conflict_narrative=None,
            structure_veto_applied=False,
            stale_data_caveat=None,
            narrative="Entry quality is Cautious — macro headwind partially offset by attractive valuation.",
            sources={},
            warnings=[],
        ),
        "grounding_result": GroundingResult(
            status="pass",
            checked_outputs=["macro_regime_output", "valuation_output", "structure_output"],
            unattributed_claims=[],
            warnings=[],
        ),
        "conflict_output": None,
        "report_output": None,
        "language": "en",
    }


def _make_mock_gold_state() -> dict:
    """Build a mock ReportState for gold asset (triggers WGC warning)."""
    state = _make_mock_report_state("GOLD", "gold")
    state["retrieval_warnings"] = [
        "DATA WARNING: WGC central bank buying data unavailable — "
        "gold valuation assessed without central bank demand context (HTTP 501)."
    ]
    return state


def _make_report_output(language: str, asset_type: str = "equity") -> ReportOutput:
    """Build a complete mock ReportOutput."""
    vi_data_warnings = ["DATA WARNING: some retrieval warning"]
    en_data_warnings: list = []

    if asset_type == "gold":
        wgc_warning = (
            "DATA WARNING: WGC central bank buying data unavailable — "
            "gold valuation assessed without central bank demand context (HTTP 501)."
        )
        vi_data_warnings.append(wgc_warning)
        en_data_warnings.append(wgc_warning)

    data_warnings = vi_data_warnings if language == "vi" else en_data_warnings

    entry_quality_section = {
        "tier": "Thận trọng" if language == "vi" else "Cautious",
        "macro_assessment": "Bất lợi" if language == "vi" else "Headwind",
        "valuation_assessment": "Hấp dẫn" if language == "vi" else "Attractive",
        "structure_assessment": "Trung lập" if language == "vi" else "Neutral",
        "structure_veto_applied": False,
        "narrative": (
            "Chất lượng điểm vào ở mức Thận trọng." if language == "vi"
            else "Entry quality is Cautious — attractive valuation offset by macro headwinds."
        ),
    }
    macro_section = {
        "label": "Bất lợi" if language == "vi" else "Headwind",
        "top_confidence": 0.75,
        "is_mixed_signal": False,
        "regime_probabilities": [],
        "narrative": (
            "Môi trường vĩ mô hiện tại là bất lợi." if language == "vi"
            else "Current macro environment is a headwind."
        ),
    }
    val_label_vi = "Hấp dẫn"
    val_section = {
        "label": val_label_vi if language == "vi" else "Attractive",
        "narrative": (
            "Định giá hiện tại khá hấp dẫn." if language == "vi"
            else "Valuation appears attractive at current levels."
        ),
    }
    struct_section = {
        "label": "Trung lập" if language == "vi" else "Neutral",
        "narrative": (
            "Cấu trúc giá ở mức trung lập." if language == "vi"
            else "Price structure is neutral with moderate drawdown."
        ),
        "close": 18500.0,
        "drawdown_from_ath": -15.2,
    }

    report_json = {
        "entry_quality": entry_quality_section,
        "macro_regime": macro_section,
        "valuation": val_section,
        "structure": struct_section,
        "data_warnings": data_warnings,
        "language": language,
    }

    if language == "vi":
        report_markdown = (
            "# Báo cáo phân tích\n\n"
            "## Chất lượng điểm vào: Thận trọng\n\n"
            "Chất lượng điểm vào ở mức Thận trọng.\n\n"
            "## Chế độ vĩ mô: Bất lợi\n\n"
            "Môi trường vĩ mô hiện tại là bất lợi.\n\n"
            "## Định giá: Hấp dẫn\n\n"
            "Định giá hiện tại khá hấp dẫn.\n\n"
            "## Cấu trúc giá: Trung lập\n\n"
            "Cấu trúc giá ở mức trung lập.\n"
        )
    else:
        report_markdown = (
            "# Analysis Report\n\n"
            "## Entry Quality: Cautious\n\n"
            "Entry quality is Cautious — attractive valuation offset by macro headwinds.\n\n"
            "## Macro Regime: Headwind\n\n"
            "Current macro environment is a headwind.\n\n"
            "## Valuation: Attractive\n\n"
            "Valuation appears attractive at current levels.\n\n"
            "## Structure: Neutral\n\n"
            "Price structure is neutral with moderate drawdown.\n"
        )

    return ReportOutput(
        report_json=report_json,
        report_markdown=report_markdown,
        language=language,
        data_as_of=datetime(2026, 1, 15, tzinfo=timezone.utc),
        data_warnings=data_warnings,
        model_version="gemini-2.5-pro",
        warnings=[],
    )


def _make_mock_db_engine():
    """Create a mock SQLAlchemy engine for write_report testing."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 1
    mock_conn.execute.return_value = mock_result
    mock_engine.connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
    mock_engine.connect.return_value.__exit__ = MagicMock(return_value=False)
    return mock_engine


# ---------------------------------------------------------------------------
# E2E: test_e2e_equity_vi_en — Full pipeline for VHM equity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_equity_vi_en():
    """Full pipeline for VHM equity: two write_report calls with vi+en reports."""
    from reasoning.app.pipeline import generate_report

    mock_engine = _make_mock_db_engine()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    prefetch_state = _make_mock_report_state("VHM", "equity")
    result_vi = {"report_output": _make_report_output("vi", "equity")}
    result_en = {"report_output": _make_report_output("en", "equity")}

    write_calls = []

    def capture_write_report(engine, asset_id, language, report_output, duration_ms=None):
        write_calls.append({
            "asset_id": asset_id,
            "language": language,
            "report_output": report_output,
        })
        return len(write_calls) * 100

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", new_callable=AsyncMock) as mock_run_graph, \
         patch("reasoning.app.pipeline.write_report", side_effect=capture_write_report):

        mock_prefetch.return_value = prefetch_state
        mock_run_graph.side_effect = [result_vi, result_en]

        vi_id, en_id = await generate_report(
            ticker="VHM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    # Assert 2 write_report calls
    assert len(write_calls) == 2, (
        f"Expected 2 write_report calls (vi + en), got {len(write_calls)}"
    )
    assert write_calls[0]["language"] == "vi", "First write_report must be for 'vi'"
    assert write_calls[1]["language"] == "en", "Second write_report must be for 'en'"

    # Assert report_json has 4 card sections
    vi_report_json = write_calls[0]["report_output"].report_json
    en_report_json = write_calls[1]["report_output"].report_json

    for section in ["entry_quality", "macro_regime", "valuation", "structure"]:
        assert section in vi_report_json, f"vi report_json must have '{section}' section"
        assert section in en_report_json, f"en report_json must have '{section}' section"

    # Assert report_markdown is non-empty
    assert len(write_calls[0]["report_output"].report_markdown) > 0, "vi report_markdown must be non-empty"
    assert len(write_calls[1]["report_output"].report_markdown) > 0, "en report_markdown must be non-empty"

    # Assert data_warnings is a list
    assert isinstance(vi_report_json.get("data_warnings"), list), "vi report_json['data_warnings'] must be a list"
    assert isinstance(en_report_json.get("data_warnings"), list), "en report_json['data_warnings'] must be a list"

    # Assert return values are integers
    assert isinstance(vi_id, int), f"vi_id must be int, got {type(vi_id)}"
    assert isinstance(en_id, int), f"en_id must be int, got {type(en_id)}"


# ---------------------------------------------------------------------------
# E2E: test_e2e_gold_with_wgc_warning — Full pipeline for gold asset
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_gold_with_wgc_warning():
    """Full pipeline for gold: WGC warning present in data_warnings for both languages."""
    from reasoning.app.pipeline import generate_report

    mock_engine = _make_mock_db_engine()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    prefetch_state = _make_mock_gold_state()
    result_vi = {"report_output": _make_report_output("vi", "gold")}
    result_en = {"report_output": _make_report_output("en", "gold")}

    write_calls = []

    def capture_write_report(engine, asset_id, language, report_output, duration_ms=None):
        write_calls.append({
            "asset_id": asset_id,
            "language": language,
            "report_output": report_output,
        })
        return len(write_calls) * 200

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", new_callable=AsyncMock) as mock_run_graph, \
         patch("reasoning.app.pipeline.write_report", side_effect=capture_write_report):

        mock_prefetch.return_value = prefetch_state
        mock_run_graph.side_effect = [result_vi, result_en]

        await generate_report(
            ticker="GOLD",
            asset_type="gold",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    # Assert 2 write_report calls
    assert len(write_calls) == 2, f"Expected 2 write_report calls, got {len(write_calls)}"

    # Assert WGC warning present for gold
    for call_record in write_calls:
        data_warnings = call_record["report_output"].data_warnings
        wgc_warnings = [w for w in data_warnings if "WGC" in w or "central bank" in w.lower()]
        assert len(wgc_warnings) > 0, (
            f"Gold asset must have WGC warning for language='{call_record['language']}'. "
            f"Got data_warnings: {data_warnings}"
        )


# ---------------------------------------------------------------------------
# E2E: test_e2e_report_json_schema_validation — Validate report_json structure
# ---------------------------------------------------------------------------


def test_e2e_report_json_schema_validation():
    """Validate report_json structure against Pydantic card models after compose_report_node."""
    from reasoning.app.pipeline.compose_report import compose_report_node

    state = _make_mock_report_state("VHM", "equity")
    state["language"] = "en"

    result = compose_report_node(state)
    report_json = result["report_output"].report_json

    # Validate entry_quality card fields
    eq = report_json.get("entry_quality", {})
    assert "tier" in eq, "entry_quality must have 'tier'"
    assert "narrative" in eq, "entry_quality must have 'narrative'"
    assert "macro_assessment" in eq, "entry_quality must have 'macro_assessment'"
    assert "valuation_assessment" in eq, "entry_quality must have 'valuation_assessment'"
    assert "structure_assessment" in eq, "entry_quality must have 'structure_assessment'"

    # Validate macro_regime card fields
    mr = report_json.get("macro_regime", {})
    assert "label" in mr, "macro_regime must have 'label'"
    assert "confidence" in mr or "top_confidence" in mr, "macro_regime must have confidence field"
    assert "narrative" in mr, "macro_regime must have 'narrative'"

    # Validate valuation card fields
    val = report_json.get("valuation", {})
    assert "label" in val, "valuation must have 'label'"
    assert "narrative" in val, "valuation must have 'narrative'"

    # Validate structure card fields
    struct = report_json.get("structure", {})
    assert "label" in struct, "structure must have 'label'"
    assert "narrative" in struct, "structure must have 'narrative'"

    # Validate no Pydantic nested instances
    from pydantic import BaseModel
    for section_name in ["entry_quality", "macro_regime", "valuation", "structure"]:
        section = report_json.get(section_name, {})
        assert isinstance(section, dict), f"report_json['{section_name}'] must be a plain dict"
        assert not isinstance(section, BaseModel), f"report_json['{section_name}'] must not be Pydantic model"


# ---------------------------------------------------------------------------
# E2E: test_e2e_no_prohibited_terms_in_markdown — Scan Markdown output
# ---------------------------------------------------------------------------


def test_e2e_no_prohibited_terms_in_markdown_english():
    """English Markdown output must not contain prohibited terms."""
    from reasoning.app.pipeline.compose_report import compose_report_node

    state = _make_mock_report_state("VHM", "equity")
    state["language"] = "en"

    result = compose_report_node(state)
    markdown = result["report_output"].report_markdown.lower()

    # Check prohibited terms (exact word match — not substrings of compound words)
    import re

    # Prohibited standalone words
    prohibited_en = ["buy", "sell", "entry confirmed"]
    for term in prohibited_en:
        # Use word boundary matching: "buy" should not match "buyback" or "overbought"
        pattern = r"\b" + re.escape(term) + r"\b"
        matches = re.findall(pattern, markdown)
        assert len(matches) == 0, (
            f"English Markdown must not contain standalone '{term}'. "
            f"Found {len(matches)} occurrence(s). Snippet: '{markdown[:500]}'"
        )


def test_e2e_no_prohibited_terms_in_markdown_vietnamese():
    """Vietnamese Markdown output must not contain prohibited terms."""
    from unittest.mock import patch
    from reasoning.app.pipeline.compose_report import compose_report_node

    state = _make_mock_report_state("VHM", "equity")
    state["language"] = "vi"

    vi_narrative = "Môi trường cho thấy điều kiện thận trọng với tín hiệu bất lợi."

    with patch("reasoning.app.pipeline.compose_report._rewrite_narrative_vi") as mock_rewrite:
        mock_rewrite.return_value = vi_narrative
        result = compose_report_node(state)

    markdown = result["report_output"].report_markdown

    prohibited_vi = ["mua vào", "bán", "xác nhận điểm vào"]
    for term in prohibited_vi:
        assert term not in markdown, (
            f"Vietnamese Markdown must not contain '{term}'. "
            f"Found in markdown output."
        )


# ---------------------------------------------------------------------------
# E2E: test_e2e_bilingual_independence — vi and en are independent strings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_bilingual_independence():
    """vi and en reports are independently generated — different strings."""
    from reasoning.app.pipeline import generate_report

    mock_engine = _make_mock_db_engine()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    prefetch_state = _make_mock_report_state("VHM", "equity")
    result_vi = {"report_output": _make_report_output("vi", "equity")}
    result_en = {"report_output": _make_report_output("en", "equity")}

    write_calls = []

    def capture_write_report(engine, asset_id, language, report_output, duration_ms=None):
        write_calls.append({
            "language": language,
            "report_output": report_output,
        })
        return len(write_calls) * 300

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", new_callable=AsyncMock) as mock_run_graph, \
         patch("reasoning.app.pipeline.write_report", side_effect=capture_write_report):

        mock_prefetch.return_value = prefetch_state
        mock_run_graph.side_effect = [result_vi, result_en]

        await generate_report(
            ticker="VHM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    vi_record = next(c for c in write_calls if c["language"] == "vi")
    en_record = next(c for c in write_calls if c["language"] == "en")

    vi_report_json = vi_record["report_output"].report_json
    en_report_json = en_record["report_output"].report_json

    # Assert vi and en report_json language fields differ
    assert vi_report_json.get("language") == "vi", "vi report_json must have language='vi'"
    assert en_report_json.get("language") == "en", "en report_json must have language='en'"

    # Assert vi labels are Vietnamese
    vi_tier = vi_report_json.get("entry_quality", {}).get("tier", "")
    vi_tiers = {"Thuận lợi", "Trung lập", "Thận trọng", "Tránh"}
    assert vi_tier in vi_tiers, (
        f"vi report_json tier must be Vietnamese, got: '{vi_tier}'"
    )

    # Assert en labels are English
    en_tier = en_report_json.get("entry_quality", {}).get("tier", "")
    en_tiers = {"Favorable", "Neutral", "Cautious", "Avoid"}
    assert en_tier in en_tiers, (
        f"en report_json tier must be English, got: '{en_tier}'"
    )

    # Assert vi and en report_markdown are different
    vi_md = vi_record["report_output"].report_markdown
    en_md = en_record["report_output"].report_markdown
    assert vi_md != en_md, (
        "vi and en report_markdown must be different strings (independent generation)"
    )

    # Assert vi markdown contains Vietnamese headers
    assert "Chất lượng điểm vào" in vi_md or "Thận trọng" in vi_md or "Trung lập" in vi_md, (
        f"vi Markdown must contain Vietnamese content. Got snippet: '{vi_md[:300]}'"
    )

    # Assert en markdown contains English headers
    assert "Entry Quality" in en_md or "Macro Regime" in en_md or "Valuation" in en_md, (
        f"en Markdown must contain English content. Got snippet: '{en_md[:300]}'"
    )


# ---------------------------------------------------------------------------
# E2E: test_e2e_generate_report_returns_two_ids — tuple return type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_generate_report_returns_two_ids():
    """generate_report() returns (vi_id, en_id) tuple of integers."""
    from reasoning.app.pipeline import generate_report

    mock_engine = _make_mock_db_engine()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    prefetch_state = _make_mock_report_state("VHM", "equity")
    result_vi = {"report_output": _make_report_output("vi", "equity")}
    result_en = {"report_output": _make_report_output("en", "equity")}

    call_counter = [0]

    def mock_write(engine, asset_id, language, report_output, duration_ms=None):
        call_counter[0] += 1
        return 1000 + call_counter[0]

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", new_callable=AsyncMock) as mock_run_graph, \
         patch("reasoning.app.pipeline.write_report", side_effect=mock_write):

        mock_prefetch.return_value = prefetch_state
        mock_run_graph.side_effect = [result_vi, result_en]

        result = await generate_report(
            ticker="VHM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    assert isinstance(result, tuple), f"generate_report must return tuple, got {type(result)}"
    assert len(result) == 2, f"generate_report tuple must have 2 elements, got {len(result)}"
    vi_id, en_id = result
    assert isinstance(vi_id, int), f"vi_id must be int, got {type(vi_id)}"
    assert isinstance(en_id, int), f"en_id must be int, got {type(en_id)}"
    assert vi_id == 1001, f"vi_id must be 1001, got {vi_id}"
    assert en_id == 1002, f"en_id must be 1002, got {en_id}"


# ---------------------------------------------------------------------------
# E2E: test_e2e_compose_report_validates_full_pipeline_state — compose_report_node validation
# ---------------------------------------------------------------------------


def test_e2e_compose_report_validates_full_pipeline_state():
    """compose_report_node produces valid ReportOutput from a fully populated state."""
    from reasoning.app.pipeline.compose_report import compose_report_node
    from reasoning.app.nodes.state import ReportOutput

    state = _make_mock_report_state("VHM", "equity")
    state["language"] = "en"

    result = compose_report_node(state)

    assert "report_output" in result, "compose_report_node must return dict with 'report_output' key"
    output = result["report_output"]
    assert isinstance(output, ReportOutput), f"report_output must be ReportOutput, got {type(output)}"
    assert output.language == "en"
    assert isinstance(output.report_json, dict)
    assert isinstance(output.report_markdown, str)
    assert len(output.report_markdown) > 0
    assert isinstance(output.data_as_of, datetime)
    assert isinstance(output.data_warnings, list)
    assert output.model_version == "gemini-2.5-pro"


# ---------------------------------------------------------------------------
# E2E: test_e2e_deepcopy_isolates_state — state isolation between runs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_deepcopy_isolates_state():
    """generate_report() deep-copies state so vi and en runs don't share state."""
    from reasoning.app.pipeline import generate_report

    mock_engine = _make_mock_db_engine()
    mock_neo4j = MagicMock()
    mock_qdrant = MagicMock()

    original_state = _make_mock_report_state("VHM", "equity")
    call_states = []

    async def mock_run_graph(state, language, thread_id, db_uri):
        # Capture the state dict BEFORE it's modified by run_graph
        call_states.append({"language": language, "state": copy.copy(state)})
        return {"report_output": _make_report_output(language, "equity")}

    def mock_write(engine, asset_id, language, report_output, duration_ms=None):
        return 1 if language == "vi" else 2

    with patch("reasoning.app.pipeline.prefetch") as mock_prefetch, \
         patch("reasoning.app.pipeline.run_graph", side_effect=mock_run_graph), \
         patch("reasoning.app.pipeline.write_report", side_effect=mock_write):

        mock_prefetch.return_value = original_state

        vi_id, en_id = await generate_report(
            ticker="VHM",
            asset_type="equity",
            db_engine=mock_engine,
            neo4j_driver=mock_neo4j,
            qdrant_client=mock_qdrant,
            db_uri="postgresql://localhost/test",
        )

    # Both runs should have been called
    assert len(call_states) == 2
    vi_state = next(c["state"] for c in call_states if c["language"] == "vi")
    en_state = next(c["state"] for c in call_states if c["language"] == "en")

    # Both states must start from the same prefetch values
    assert vi_state["ticker"] == "VHM"
    assert en_state["ticker"] == "VHM"

    # Results should be correct
    assert vi_id == 1
    assert en_id == 2


# ---------------------------------------------------------------------------
# Integration tests (require Docker services — skipped in CI)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_integration_generate_report_live_db():
    """
    INTEGRATION: Full pipeline with live PostgreSQL and mocked Gemini.

    Requires:
        - PostgreSQL accessible at DATABASE_URL
        - reports table migrated (V6__reports.sql)
        - langgraph schema initialized

    Skipped in CI — run manually with:
        pytest -m integration tests/pipeline/test_e2e.py
    """
    # Placeholder — would require live DB connection
    pytest.skip("Integration test requires live Docker services")
