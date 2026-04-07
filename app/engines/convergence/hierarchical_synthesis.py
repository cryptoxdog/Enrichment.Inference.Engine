"""
hierarchical_synthesis.py
Pattern 2 — RAPTOR-style hierarchical composite synthesis

Purpose:
  Groups high-confidence enriched fields by the pass that first resolved them,
  clusters them into CompositeNode objects (RAPTOR parent nodes), and attaches
  the result to EnrichResponse.feature_vector["_composite_nodes"].

  Activation: ConvergenceConfig.synthesize_composites = True
  Default: False — zero behavioral change when disabled.

Dependencies:
  app.models.enrichment   — EnrichResponse, ConvergenceState, FieldResult
  app.engines.convergence — ConvergenceConfig
  PacketEnvelope          — immutable I/O boundary

L9 Compliance:
  - Feature-flagged via ConvergenceConfig; no ambient state
  - Fully deterministic: same ConvergenceState → same CompositeNode set
  - No routes, auth, or infra
  - Zero stubs; all imports resolve
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from app.engines.convergence.config import ConvergenceConfig
from app.models.enrichment import ConvergenceState, EnrichResponse, FieldResult

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_COMPOSITE_NODES_KEY = "_composite_nodes"
_MIN_COMPOSITE_CONFIDENCE: float = 0.75   # RAPTOR leaf threshold
_MAX_FIELDS_PER_NODE: int = 4             # cap: prevents overloaded parent nodes
_MIN_FIELDS_PER_NODE: int = 2             # single-field nodes are not composites


# ── Domain objects ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class CompositeNode:
    """
    Immutable RAPTOR parent node representing a cluster of co-resolved fields.
    node_id is deterministic: SHA-256 of sorted constituent field names.
    """
    node_id: str
    resolved_pass: int
    constituent_fields: Tuple[str, ...]
    mean_confidence: float
    semantic_label: str       # e.g. "identity_cluster_pass2"
    is_derived_target: bool   # True if any constituent is a derived_from target

    @classmethod
    def build(
        cls,
        constituent_fields: List[str],
        resolved_pass: int,
        mean_confidence: float,
        is_derived_target: bool,
    ) -> "CompositeNode":
        sorted_fields = tuple(sorted(constituent_fields))
        node_id = hashlib.sha256(
            ":".join(sorted_fields).encode()
        ).hexdigest()[:16]
        label = f"composite_pass{resolved_pass}_{node_id[:6]}"
        return cls(
            node_id=node_id,
            resolved_pass=resolved_pass,
            constituent_fields=sorted_fields,
            mean_confidence=round(mean_confidence, 4),
            semantic_label=label,
            is_derived_target=is_derived_target,
        )

    def to_feature_entry(self) -> dict:
        return {
            "node_id": self.node_id,
            "pass": self.resolved_pass,
            "fields": list(self.constituent_fields),
            "confidence": self.mean_confidence,
            "label": self.semantic_label,
            "is_derived_target": self.is_derived_target,
        }


# ── Field classification helpers ─────────────────────────────────────────────

def _get_pass_resolved(field_result: FieldResult) -> Optional[int]:
    """Extract the pass number at which this field first achieved confidence >= threshold."""
    return getattr(field_result, "resolved_pass", None)


def _is_derived_target(field_name: str, cfg: ConvergenceConfig) -> bool:
    """
    True if the field appears as a derived_from target in the domain KB.
    These fields are excluded from composite constituents because they are
    already the synthesis output of earlier fields.
    """
    derived_targets: FrozenSet[str] = frozenset(
        getattr(cfg, "derived_field_targets", []) or []
    )
    return field_name in derived_targets


def _cluster_fields_by_pass(
    high_confidence_fields: Dict[str, FieldResult],
    cfg: ConvergenceConfig,
) -> Dict[int, List[Tuple[str, float]]]:
    """
    Group (field_name, confidence) pairs by the pass that first resolved them.
    Returns {pass_number: [(field_name, confidence), ...]}
    """
    clusters: Dict[int, List[Tuple[str, float]]] = {}
    for fname, fresult in high_confidence_fields.items():
        if _is_derived_target(fname, cfg):
            continue  # exclude synthesis outputs from being re-clustered
        pass_num = _get_pass_resolved(fresult)
        if pass_num is None:
            continue
        confidence = getattr(fresult, "confidence", 0.0)
        clusters.setdefault(pass_num, []).append((fname, confidence))
    return clusters


def _build_nodes_from_cluster(
    pass_num: int,
    fields: List[Tuple[str, float]],
    cfg: ConvergenceConfig,
) -> List[CompositeNode]:
    """
    Partition a single pass-cluster into CompositeNode objects of size
    [_MIN_FIELDS_PER_NODE, _MAX_FIELDS_PER_NODE].  Any remainder that
    falls below _MIN_FIELDS_PER_NODE is discarded.
    """
    nodes: List[CompositeNode] = []
    # Sort by confidence desc so highest-confidence fields lead each node
    sorted_fields = sorted(fields, key=lambda x: x[1], reverse=True)

    chunk: List[Tuple[str, float]] = []
    for fname, conf in sorted_fields:
        chunk.append((fname, conf))
        if len(chunk) == _MAX_FIELDS_PER_NODE:
            names = [f for f, _ in chunk]
            mean_conf = sum(c for _, c in chunk) / len(chunk)
            any_derived = any(_is_derived_target(n, cfg) for n in names)
            nodes.append(
                CompositeNode.build(names, pass_num, mean_conf, any_derived)
            )
            chunk = []

    # Emit trailing chunk if large enough
    if len(chunk) >= _MIN_FIELDS_PER_NODE:
        names = [f for f, _ in chunk]
        mean_conf = sum(c for _, c in chunk) / len(chunk)
        any_derived = any(_is_derived_target(n, cfg) for n in names)
        nodes.append(
            CompositeNode.build(names, pass_num, mean_conf, any_derived)
        )
    return nodes


# ── Core synthesis ────────────────────────────────────────────────────────────

def build_composite_nodes(
    convergence_state: ConvergenceState,
    cfg: ConvergenceConfig,
) -> List[CompositeNode]:
    """
    Main entry: walk all resolved fields in convergence_state, filter to
    high-confidence, cluster by pass, and produce CompositeNode objects.
    """
    if not cfg.synthesize_composites:
        return []

    resolved: Dict[str, FieldResult] = (
        getattr(convergence_state, "resolved_fields", {}) or {}
    )
    high_confidence = {
        fname: fresult
        for fname, fresult in resolved.items()
        if getattr(fresult, "confidence", 0.0) >= _MIN_COMPOSITE_CONFIDENCE
    }

    if not high_confidence:
        logger.debug("hierarchical_synthesis.no_eligible_fields")
        return []

    clusters = _cluster_fields_by_pass(high_confidence, cfg)
    nodes: List[CompositeNode] = []
    for pass_num, fields in sorted(clusters.items()):
        nodes.extend(_build_nodes_from_cluster(pass_num, fields, cfg))

    logger.info(
        "hierarchical_synthesis.nodes_built",
        extra={
            "node_count": len(nodes),
            "eligible_fields": len(high_confidence),
            "pass_clusters": list(clusters.keys()),
        },
    )
    return nodes


# ── EnrichResponse attachment ─────────────────────────────────────────────────

def attach_composites_to_feature_vector(
    response: EnrichResponse,
    nodes: List[CompositeNode],
) -> EnrichResponse:
    """
    Return a new EnrichResponse with composite nodes embedded in feature_vector.
    Does not mutate the original response (PacketEnvelope immutability).
    """
    if not nodes:
        return response

    updated_fv = {
        **(response.feature_vector or {}),
        _COMPOSITE_NODES_KEY: [n.to_feature_entry() for n in nodes],
    }
    logger.debug(
        "hierarchical_synthesis.attached",
        extra={"node_count": len(nodes)},
    )
    return response.replace(feature_vector=updated_fv)


# ── High-level orchestration entry point ─────────────────────────────────────

def synthesize_and_attach(
    convergence_state: ConvergenceState,
    response: EnrichResponse,
    cfg: ConvergenceConfig,
) -> EnrichResponse:
    """
    Called by SchemaProposer.analyze() exit path after convergence is declared.
    Returns response unchanged when synthesize_composites is False or no eligible
    fields exist.

    Integration point: app/engines/convergence/schema_proposer.py at the
        return response  line in the post-convergence path.
    """
    nodes = build_composite_nodes(convergence_state, cfg)
    return attach_composites_to_feature_vector(response, nodes)
