"""
reasoning/tests/pipeline/test_term_dict.py
Unit tests for Vietnamese financial term dictionary (term_dict_vi.json + term_dict.py).
Phase 7 | Plan 03 | Requirement: REPT-03
"""

import copy
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_leaf_values(d: dict) -> int:
    """Recursively count leaf string values in a nested dict."""
    count = 0
    for v in d.values():
        if isinstance(v, dict):
            count += _count_leaf_values(v)
        else:
            count += 1
    return count


def _make_report_json(
    tier: str = "Favorable",
    macro_label: str = "Supportive",
    valuation_label: str = "Attractive",
    structure_label: str = "Constructive",
    with_conflict: bool = False,
    conflict_pattern: str = "Strong Thesis, Weak Structure",
) -> dict:
    """Create a minimal report_json dict matching the compose_report output shape."""
    report = {
        "entry_quality": {"tier": tier, "narrative": "some text P/E ATH ETF"},
        "macro_regime": {"label": macro_label, "narrative": "some macro text"},
        "valuation": {"label": valuation_label, "narrative": "some valuation text"},
        "structure": {"label": structure_label, "narrative": "some structure text"},
    }
    if with_conflict:
        report["conflict"] = {"pattern_name": conflict_pattern}
    return report


# ---------------------------------------------------------------------------
# Tests: load_term_dict
# ---------------------------------------------------------------------------


class TestLoadTermDict:
    def test_returns_dict(self):
        from reasoning.app.pipeline.term_dict import load_term_dict
        d = load_term_dict()
        assert isinstance(d, dict)

    def test_has_all_required_keys(self):
        from reasoning.app.pipeline.term_dict import load_term_dict
        d = load_term_dict()
        required_keys = [
            "tiers",
            "macro_labels",
            "valuation_labels",
            "structure_labels",
            "card_headers",
            "conflict_patterns",
            "data_warning",
            "metrics",
            "macro_concepts",
            "narrative_connectors",
        ]
        for key in required_keys:
            assert key in d, f"Missing top-level key: {key}"

    def test_all_four_tier_translations(self):
        from reasoning.app.pipeline.term_dict import load_term_dict
        d = load_term_dict()
        tiers = d["tiers"]
        assert tiers.get("Favorable") == "Thuận lợi"
        assert tiers.get("Neutral") == "Trung lập"
        assert tiers.get("Cautious") == "Thận trọng"
        assert tiers.get("Avoid") == "Tránh"

    def test_all_three_macro_label_translations(self):
        from reasoning.app.pipeline.term_dict import load_term_dict
        d = load_term_dict()
        macro = d["macro_labels"]
        assert macro.get("Supportive") == "Hỗ trợ"
        assert macro.get("Mixed") == "Hỗn hợp"
        assert macro.get("Headwind") == "Bất lợi"

    def test_all_three_valuation_label_translations(self):
        from reasoning.app.pipeline.term_dict import load_term_dict
        d = load_term_dict()
        val = d["valuation_labels"]
        assert val.get("Attractive") == "Hấp dẫn"
        assert val.get("Fair") == "Hợp lý"
        assert val.get("Stretched") == "Căng thẳng"

    def test_all_three_structure_label_translations(self):
        from reasoning.app.pipeline.term_dict import load_term_dict
        d = load_term_dict()
        struct = d["structure_labels"]
        assert struct.get("Constructive") == "Tích cực"
        assert struct.get("Neutral") == "Trung lập"
        assert struct.get("Deteriorating") == "Suy giảm"

    def test_card_header_translations_present(self):
        from reasoning.app.pipeline.term_dict import load_term_dict
        d = load_term_dict()
        headers = d["card_headers"]
        expected_headers = [
            "Entry Quality",
            "Macro Regime",
            "Valuation",
            "Structure",
            "Signal Conflict",
            "Data Warning",
        ]
        for header in expected_headers:
            assert header in headers, f"Missing card header: {header}"

    def test_total_term_count_at_least_150(self):
        from reasoning.app.pipeline.term_dict import load_term_dict
        d = load_term_dict()
        total = _count_leaf_values(d)
        assert total >= 150, f"Term count {total} is below 150 minimum"

    def test_returns_same_instance_on_second_call(self):
        """load_term_dict() must be cached — returns the same dict object."""
        from reasoning.app.pipeline.term_dict import load_term_dict
        d1 = load_term_dict()
        d2 = load_term_dict()
        assert d1 is d2, "load_term_dict() must cache and return same dict instance"


# ---------------------------------------------------------------------------
# Tests: apply_terms
# ---------------------------------------------------------------------------


class TestApplyTerms:
    def test_replaces_tier_label(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(tier="Favorable")
        result = apply_terms(report)
        assert result["entry_quality"]["tier"] == "Thuận lợi"

    def test_replaces_macro_regime_label(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(macro_label="Supportive")
        result = apply_terms(report)
        assert result["macro_regime"]["label"] == "Hỗ trợ"

    def test_replaces_valuation_label(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(valuation_label="Attractive")
        result = apply_terms(report)
        assert result["valuation"]["label"] == "Hấp dẫn"

    def test_replaces_structure_label(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(structure_label="Constructive")
        result = apply_terms(report)
        assert result["structure"]["label"] == "Tích cực"

    def test_replaces_conflict_pattern_name(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(
            with_conflict=True,
            conflict_pattern="Strong Thesis, Weak Structure",
        )
        result = apply_terms(report)
        assert result["conflict"]["pattern_name"] != "Strong Thesis, Weak Structure"
        assert result["conflict"]["pattern_name"]  # non-empty

    def test_unknown_tier_passes_through_unchanged(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(tier="UnknownTier")
        result = apply_terms(report)
        assert result["entry_quality"]["tier"] == "UnknownTier"

    def test_unknown_macro_label_passes_through_unchanged(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(macro_label="NoSuchLabel")
        result = apply_terms(report)
        assert result["macro_regime"]["label"] == "NoSuchLabel"

    def test_apply_terms_is_idempotent(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(
            tier="Favorable",
            macro_label="Supportive",
            valuation_label="Attractive",
            structure_label="Constructive",
        )
        once = apply_terms(report)
        twice = apply_terms(copy.deepcopy(once))
        assert once == twice, "apply_terms must be idempotent"

    def test_does_not_mutate_input(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(tier="Favorable")
        original_tier = report["entry_quality"]["tier"]
        apply_terms(report)
        assert report["entry_quality"]["tier"] == original_tier, (
            "apply_terms must not mutate the input dict"
        )

    def test_english_abbreviations_in_narrative_not_modified(self):
        """English abbreviations in narrative fields must pass through unchanged."""
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(tier="Favorable")
        # narrative contains P/E, ATH, ETF per _make_report_json
        result = apply_terms(report)
        narrative = result["entry_quality"]["narrative"]
        assert "P/E" in narrative, "P/E abbreviation must be preserved"
        assert "ATH" in narrative, "ATH abbreviation must be preserved"
        assert "ETF" in narrative, "ETF abbreviation must be preserved"

    def test_missing_conflict_key_does_not_raise(self):
        """apply_terms must handle report_json without 'conflict' key gracefully."""
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(with_conflict=False)
        # Must not raise
        result = apply_terms(report)
        assert "conflict" not in result

    def test_conflict_none_does_not_raise(self):
        """apply_terms must handle report_json with conflict=None gracefully."""
        from reasoning.app.pipeline.term_dict import apply_terms
        report = _make_report_json(with_conflict=False)
        report["conflict"] = None
        result = apply_terms(report)
        assert result["conflict"] is None

    def test_all_tiers_translated(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        tier_map = {
            "Favorable": "Thuận lợi",
            "Neutral": "Trung lập",
            "Cautious": "Thận trọng",
            "Avoid": "Tránh",
        }
        for en, vi in tier_map.items():
            report = _make_report_json(tier=en)
            result = apply_terms(report)
            assert result["entry_quality"]["tier"] == vi, f"{en} -> {vi} failed"

    def test_all_macro_labels_translated(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        label_map = {
            "Supportive": "Hỗ trợ",
            "Mixed": "Hỗn hợp",
            "Headwind": "Bất lợi",
        }
        for en, vi in label_map.items():
            report = _make_report_json(macro_label=en)
            result = apply_terms(report)
            assert result["macro_regime"]["label"] == vi, f"{en} -> {vi} failed"

    def test_all_valuation_labels_translated(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        label_map = {
            "Attractive": "Hấp dẫn",
            "Fair": "Hợp lý",
            "Stretched": "Căng thẳng",
        }
        for en, vi in label_map.items():
            report = _make_report_json(valuation_label=en)
            result = apply_terms(report)
            assert result["valuation"]["label"] == vi, f"{en} -> {vi} failed"

    def test_all_structure_labels_translated(self):
        from reasoning.app.pipeline.term_dict import apply_terms
        label_map = {
            "Constructive": "Tích cực",
            "Neutral": "Trung lập",
            "Deteriorating": "Suy giảm",
        }
        for en, vi in label_map.items():
            report = _make_report_json(structure_label=en)
            result = apply_terms(report)
            assert result["structure"]["label"] == vi, f"{en} -> {vi} failed"
