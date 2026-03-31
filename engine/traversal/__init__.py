# engine/traversal/__init__.py
"""Traversal module — parameterized Neo4j query execution."""

from .graph_query import execute_match_query

__all__ = ["execute_match_query"]
