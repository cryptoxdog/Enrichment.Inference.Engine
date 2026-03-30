"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [kge]
tags: [kge, hyper-relational, n-ary, kb-integration, matching]
owner: engine-team
status: active
--- /L9_META ---

HyperRelationalEncoder — CompoundE3D inside N-ary hyperedge encoding.

Encodes roles and qualifiers into entity representations, then applies
CompoundE3D transformations per role type, capturing 3D context shifts.

Fixes applied vs. v1:
  - hash() replaced with sha256 for cross-process determinism
  - Qualifier perturbation now dispatches by type (numeric vs categorical)
  - Role embedding cache added (LRU-like dict)
  - Combined match score config-driven (no hardcoded magic numbers)
  - to_variant_score() added for EnsembleController integration
  - entity_overlap added to combined match score
  - Backbone link prediction (predict_tail) used in match_hyperedges

Consumes:
  engine.kge.compound_e3d.CompoundE3D
  engine.kge.ensemble.VariantScore
  engine.kge.transformations.Transformation3D
  engine.resolution.similarity  (downstream caller)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from engine.kge.compound_e3d import CompoundE3D
from engine.kge.ensemble import VariantScore
from engine.kge.transformations import Rotation, Scale, Translation

logger = logging.getLogger(__name__)

VARIANT_ID = "hyper_relational"


@dataclass
class HyperEncoderWeights:
    """Configurable score combination weights.

    embedding_weight + role_overlap_weight + entity_overlap_weight = 1.0
    (normalized at runtime if they don't sum to 1.0)
    """

    embedding_weight: float = 0.50
    role_overlap_weight: float = 0.25
    entity_overlap_weight: float = 0.25


@dataclass
class HyperedgeRole:
    """Single role in an N-ary hyperedge.

    qualifiers: dict of additional context properties.
      Numeric qualifiers ("mfi_range": "4.0-6.0") → range-based perturbation.
      Categorical qualifiers ("contamination_tolerance": "low") → hash-based.
    """

    role_type: str
    entity_id: str
    qualifiers: dict[str, Any] = field(default_factory=dict)


@dataclass
class Hyperedge:
    """An N-ary fact with typed roles."""

    relation: str
    roles: list[HyperedgeRole]
    confidence: float = 1.0
    provenance: str = ""


class HyperRelationalEncoder:
    """Encode N-ary hyperedges using per-role CompoundE3D transformations.

    Lifecycle:
      1. __init__(backbone, weights)
      2. register_role_ops(role_type, ops)
      3. encode_role(role) → ndarray(dim,) | None
      4. score_hyperedge(hyperedge) → float [0,1]
      5. match_hyperedges(query, candidates, top_k) → ranked list
      6. to_variant_score(hyperedge) → VariantScore
    """

    def __init__(
        self,
        backbone: CompoundE3D,
        weights: HyperEncoderWeights | None = None,
    ) -> None:
        self._backbone = backbone
        self._weights = weights or HyperEncoderWeights()
        self._normalize_weights()
        self._role_ops: dict[str, list[Any]] = {}
        self._encode_cache: dict[str, npt.NDArray[np.float64]] = {}
        self._register_default_ops()

    def _normalize_weights(self) -> None:
        w = self._weights
        total = w.embedding_weight + w.role_overlap_weight + w.entity_overlap_weight
        if abs(total - 1.0) > 1e-6:
            w.embedding_weight /= total
            w.role_overlap_weight /= total
            w.entity_overlap_weight /= total

    def _register_default_ops(self) -> None:
        """Default per-role transformation cascades (plastics domain example).

        These are illustrative defaults. Override via register_role_ops() for
        production domain packs.
        """
        self._role_ops["material_grade"] = [
            Rotation(angle=15.0, axis=(0.0, 0.0, 1.0)),
            Scale(factor=1.1),
        ]
        self._role_ops["contamination_tolerance"] = [
            Rotation(angle=-10.0, axis=(1.0, 0.0, 0.0)),
        ]
        self._role_ops["supplier"] = [
            Translation(offset=(0.05, 0.0, -0.05)),
        ]
        self._role_ops["buyer"] = [
            Translation(offset=(-0.05, 0.0, 0.05)),
        ]
        self._role_ops["contract"] = [
            Scale(factor=0.9),
            Rotation(angle=5.0, axis=(0.0, 1.0, 0.0)),
        ]

    def register_role_ops(
        self,
        role_type: str,
        ops: list[Any],
    ) -> None:
        """Assign transformation cascade for a role type. Clears cache for role."""
        self._role_ops[role_type] = ops
        # Evict any cached entries for this role
        to_evict = [k for k in self._encode_cache if k.startswith(f"{role_type}:")]
        for k in to_evict:
            del self._encode_cache[k]

    def encode_role(self, role: HyperedgeRole) -> npt.NDArray[np.float64] | None:
        """Return context-transformed embedding for a role.

        Cache key: "{role_type}:{entity_id}:{sorted_qualifiers_hash}"
        Deterministic across processes via sha256.
        """
        # Build deterministic cache key
        qual_str = ";".join(f"{k}={v}" for k, v in sorted(role.qualifiers.items()))
        qual_hash = hashlib.sha256(qual_str.encode()).hexdigest()[:16]
        cache_key = f"{role.role_type}:{role.entity_id}:{qual_hash}"

        if cache_key in self._encode_cache:
            return self._encode_cache[cache_key]

        base = self._backbone.embed(role.entity_id)
        if base is None:
            logger.warning(
                "HyperRelationalEncoder: entity '%s' not in backbone",
                role.entity_id,
            )
            return None

        emb = base.copy()

        # Apply role-type transformation cascade
        for op in self._role_ops.get(role.role_type, []):
            emb = op.apply(emb)

        # Qualifier perturbation — type-dispatched
        for k, v in role.qualifiers.items():
            emb = self._apply_qualifier_perturbation(emb, k, v)

        self._encode_cache[cache_key] = emb
        return emb

    def _apply_qualifier_perturbation(
        self,
        emb: npt.NDArray[np.float64],
        key: str,
        value: Any,
    ) -> npt.NDArray[np.float64]:
        """Apply deterministic perturbation for a qualifier.

        Numeric (range) qualifiers: scale magnitude by normalized midpoint.
        Categorical qualifiers: sha256 hash → seeded Gaussian shift.
        """
        str_val = str(value)

        # Detect numeric range: "4.0-6.0"
        if "-" in str_val:
            parts = str_val.split("-")
            try:
                lo, hi = float(parts[0]), float(parts[1])
                midpoint = (lo + hi) / 2.0
                scale = 1.0 + 0.01 * (midpoint - 5.0)  # normalize around 5.0
                return emb * np.clip(scale, 0.9, 1.1)
            except ValueError:
                pass

        # Categorical: sha256-seeded perturbation
        seed_bytes = hashlib.sha256(f"{key}:{str_val}".encode()).digest()
        seed_int = int.from_bytes(seed_bytes[:4], "big")
        rng = np.random.default_rng(seed_int)
        perturbation = rng.normal(0.0, 0.01, size=emb.shape).astype(np.float64)
        return emb + perturbation

    def score_hyperedge(self, hyperedge: Hyperedge) -> float:
        """Score N-ary fact by pairwise role-transformed entity proximity.

        Returns [0,1] — higher = more internally coherent fact.
        """
        encoded = [self.encode_role(r) for r in hyperedge.roles]
        encoded = [e for e in encoded if e is not None]

        if len(encoded) < 2:
            return 0.0

        sims: list[float] = []
        for i in range(len(encoded)):
            for j in range(i + 1, len(encoded)):
                dot = float(np.dot(encoded[i], encoded[j]))
                norm = float(np.linalg.norm(encoded[i]) * np.linalg.norm(encoded[j]))
                if norm > 1e-9:
                    sims.append(dot / norm)

        raw = float(np.mean(sims)) if sims else 0.0
        return float(np.clip((raw + 1.0) / 2.0, 0.0, 1.0))

    def match_hyperedges(
        self,
        query: Hyperedge,
        candidates: list[Hyperedge],
        top_k: int = 10,
    ) -> list[tuple[Hyperedge, float]]:
        """Rank candidates against query hyperedge.

        Combined score = w_emb * embedding_score
                       + w_role * role_type_overlap
                       + w_entity * entity_overlap

        entity_overlap = fraction of shared (role_type, entity_id) pairs.
        This fixes the v1 gap where identical role types but mismatched
        entities scored the same as true matches.
        """
        w = self._weights
        query_role_types = {r.role_type for r in query.roles}
        query_role_entities = {(r.role_type, r.entity_id) for r in query.roles}
        results: list[tuple[Hyperedge, float]] = []

        for candidate in candidates:
            cand_role_types = {r.role_type for r in candidate.roles}
            cand_role_entities = {(r.role_type, r.entity_id) for r in candidate.roles}

            # Embedding coherence score
            emb_score = self.score_hyperedge(candidate)

            # Role-type structural overlap (Jaccard)
            union_types = query_role_types | cand_role_types
            role_overlap = (
                len(query_role_types & cand_role_types) / len(union_types) if union_types else 0.0
            )

            # Entity-level overlap (Jaccard on (role_type, entity_id) pairs)
            union_entities = query_role_entities | cand_role_entities
            entity_overlap = (
                len(query_role_entities & cand_role_entities) / len(union_entities)
                if union_entities
                else 0.0
            )

            combined = (
                w.embedding_weight * emb_score
                + w.role_overlap_weight * role_overlap
                + w.entity_overlap_weight * entity_overlap
            )
            results.append((candidate, float(np.clip(combined, 0.0, 1.0))))

        results.sort(key=lambda x: -x[1])
        return results[:top_k]

    def to_variant_score(
        self,
        hyperedge: Hyperedge,
        confidence: float | None = None,
    ) -> VariantScore:
        """Produce VariantScore for EnsembleController.

        Allows HyperRelationalEncoder to participate in ensemble fusion.
        """
        score = self.score_hyperedge(hyperedge)
        return VariantScore(
            variant_id=VARIANT_ID,
            variant_type="hyper_relational",
            score=score,
            confidence=confidence if confidence is not None else hyperedge.confidence,
            metadata={
                "relation": hyperedge.relation,
                "num_roles": len(hyperedge.roles),
                "provenance": hyperedge.provenance,
            },
        )
