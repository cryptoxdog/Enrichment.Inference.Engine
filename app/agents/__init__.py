"""
Agent integration layer for the Enrichment Inference Engine.

Provides MCP server and specialized agent modules for AI-driven
consumers (Odoo AI assistants, autonomous enrichment agents).
"""
from .mcp_server import MCPServer

__all__ = ["MCPServer"]
