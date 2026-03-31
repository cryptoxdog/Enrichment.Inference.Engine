# engine/compliance/__init__.py
"""Compliance module — spec validation and domain constraints."""

from .validator import validate_enrichment_request

__all__ = ["validate_enrichment_request"]
