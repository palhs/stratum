"""
reasoning/app/nodes — LangGraph reasoning node implementations.
Phase 6 | Requirement: REAS-03

Each node is a pure function: (ReportState) -> dict[str, Any]
Nodes read from state, produce one output key, never call retrieval functions.
"""
