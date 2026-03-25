"""
Enrichment sources registry.

Each source implements the BaseSource interface and can be used within
the WaterfallEngine for multi-source enrichment with quality-based fallback.
"""

from .base import BaseSource, EnrichmentResult, SourceConfig
from .perplexity_adapter import PerplexitySonarSource

__all__ = [
    "BaseSource",
    "EnrichmentResult",
    "PerplexitySonarSource",
    "SourceConfig",
]
