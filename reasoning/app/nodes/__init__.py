"""
reasoning/app/nodes — LangGraph reasoning node functions.
Phase 6 | Requirements: REAS-01 through REAS-05, REAS-07

Each node is a standalone function accepting ReportState and returning a dict
with one state key update. Nodes are individually validated in Phase 6 and
assembled into a StateGraph in Phase 7.
"""
from reasoning.app.nodes.structure import structure_node
from reasoning.app.nodes.valuation import valuation_node
from reasoning.app.nodes.macro_regime import macro_regime_node
from reasoning.app.nodes.entry_quality import entry_quality_node
from reasoning.app.nodes.grounding_check import grounding_check_node
from reasoning.app.nodes.conflicting_signals import conflicting_signals_handler

__all__ = [
    "structure_node",
    "valuation_node",
    "macro_regime_node",
    "entry_quality_node",
    "grounding_check_node",
    "conflicting_signals_handler",
]
