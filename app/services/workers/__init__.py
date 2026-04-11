"""
Workers module — background Redis Streams consumers.

- GraphInferenceConsumer: Closes bidirectional ENRICH↔GRAPH loop
- SchemaPromotionWorker: Auto-promotes discovered schema fields
"""

from __future__ import annotations

from .graph_inference_consumer import GraphInferenceConsumer
from .schema_promotion_worker import SchemaPromotionWorker

__all__ = [
    "GraphInferenceConsumer",
    "SchemaPromotionWorker",
]
