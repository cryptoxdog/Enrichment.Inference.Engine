"""
Enrichment sources registry.

Each source implements the BaseSource interface and can be used within
the WaterfallEngine for multi-source enrichment with quality-based fallback.

Available sources:
- PerplexitySonarSource: Wraps existing perplexity_client (primary)
- ClearbitSource: Company + contact enrichment via Clearbit API
- ZoomInfoSource: Company + contact enrichment via ZoomInfo API
- ApolloSource: Company + contact enrichment via Apollo.io API
- HunterSource: Contact email verification via Hunter.io API
"""

from .apollo import ApolloSource
from .base import BaseSource, EnrichmentResult, SourceConfig
from .clearbit import ClearbitSource
from .hunter import HunterSource
from .perplexity_adapter import PerplexitySonarSource
from .zoominfo import ZoomInfoSource

# Source class registry — maps config names to implementations
SOURCE_REGISTRY: dict[str, type[BaseSource]] = {
    "perplexity_sonar": PerplexitySonarSource,
    "clearbit": ClearbitSource,
    "zoominfo": ZoomInfoSource,
    "apollo": ApolloSource,
    "hunter": HunterSource,
}

__all__ = [
    "ApolloSource",
    "BaseSource",
    "ClearbitSource",
    "EnrichmentResult",
    "HunterSource",
    "PerplexitySonarSource",
    "SOURCE_REGISTRY",
    "SourceConfig",
    "ZoomInfoSource",
]
