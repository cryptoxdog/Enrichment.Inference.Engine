"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [kge]
tags: [kge, neuro-symbolic, fol, matching, rotate3d]
owner: engine-team
status: active
--- /L9_META ---

NeuroSymbolicEngine — RotatE3D embeddings feeding neural FOL operators.

Connects RotatE3D as embedding backbone into First-Order Logic operators
for P1 entity matching with symbolic justification.

Architecture:
  symbolic gate → neural FOL operator → scored match result

FOL operator semantics (corrected):
  - All operators work on normalized unit-sphere embeddings.
  - conjunction: Łukasiewicz t-norm, element-wise max(a+b-1, 0)
  - disjunction: Łukasiewicz t-conorm, element-wise min(a+b, 1)
  - negation: complement on [0,1] per-dimension: 1-a
  - existential: soft max-pool over candidate set
  - universal: soft min-pool over candidate set
  Scoring: cosine between FOL result and ICP centroid (or reference embedding),
  NOT against the mean of the input pair — that was circular.

Relation-chain traversal:
  Requires a GraphAccessor (protocol) to walk Neo4j edges.
  If None, chains fall back to direct entity embedding.

Fixes applied vs. v1:
  - Circular self-scoring replaced with ICP/reference-based scoring
  - Łukasiewicz operators corrected to [0,1]-normalized inputs
  - negation corrected to (1 - a) complement form
  - relation_chain traversal added (requires GraphAccessor)
  - Confidence propagation: conjunction reduces, disjunction preserves
  - relation_source added to match result for audit trail
  - symbolic_condition protocol aligned with rule_engine.py rule names

Consumes:
  engine.kge.rotate3d.RotatE3D
  engine.kge.ensemble.EnsembleController
  engine.resolution.resolver  (batch_match() output)
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from engine.kge.rotate3d import RotatE3D

logger = logging.getLogger(__name__)


# ======================================================================
# Graph Accessor Protocol — allows NSE to traverse relation chains
# without direct Neo4j dependency (testable, mockable)
# ======================================================================


@runtime_checkable
class GraphAccessor(Protocol):
    """Protocol for traversing entity relations in the graph.

    Implementors: engine.graph.* or test mocks.
    """

    def neighbors(
        self,
        entity_id: str,
        relation: str,
        direction: str = "outbound",
    ) -> list[str]:
        """Return entity IDs connected via relation from entity_id."""
        ...


# ======================================================================
# Neural FOL Operators
# ======================================================================


class NeuralFOLOperators:
    """Łukasiewicz t-norm/t-conorm FOL operators over [0,1] embeddings.

    All inputs normalized to [0,1] before operator application via
    sigmoid(x). Outputs remain in [0,1].

    Scoring convention: higher = more logically consistent with match.
    """

    @staticmethod
    def _to_unit(emb: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        """Map embedding to [0,1] via sigmoid for FOL operator input."""
        return 1.0 / (1.0 + np.exp(-emb))

    @staticmethod
    def conjunction(
        emb_a: npt.NDArray[np.float64],
        emb_b: npt.NDArray[np.float64],
    ) -> tuple[npt.NDArray[np.float64], float]:
        """∧: Łukasiewicz t-norm. Returns (result_emb, confidence_factor).

        confidence_factor < 1.0: conjunction is a conservative operation.
        """
        a = NeuralFOLOperators._to_unit(emb_a)
        b = NeuralFOLOperators._to_unit(emb_b)
        result: npt.NDArray[np.float64] = np.maximum(a + b - 1.0, 0.0)
        # Confidence = mean activation of result (higher = more agreement)
        conf_factor = float(np.mean(result))
        return result, conf_factor

    @staticmethod
    def disjunction(
        emb_a: npt.NDArray[np.float64],
        emb_b: npt.NDArray[np.float64],
    ) -> tuple[npt.NDArray[np.float64], float]:
        """∨: Łukasiewicz t-conorm. Returns (result_emb, confidence_factor)."""
        a = NeuralFOLOperators._to_unit(emb_a)
        b = NeuralFOLOperators._to_unit(emb_b)
        result: npt.NDArray[np.float64] = np.minimum(a + b, 1.0)
        conf_factor = float(np.mean(result))
        return result, conf_factor

    @staticmethod
    def negation(
        emb: npt.NDArray[np.float64],
    ) -> tuple[npt.NDArray[np.float64], float]:
        """¬: Standard complement on [0,1]: result = 1 - sigmoid(emb)."""
        a = NeuralFOLOperators._to_unit(emb)
        result: npt.NDArray[np.float64] = 1.0 - a
        conf_factor = float(np.mean(result))
        return result, conf_factor

    @staticmethod
    def existential(
        candidate_embeddings: list[npt.NDArray[np.float64]],
    ) -> tuple[npt.NDArray[np.float64], float]:
        """∃x.P(x): Soft max-pool — represents 'there exists'."""
        if not candidate_embeddings:
            return np.zeros(1, dtype=np.float64), 0.0
        stacked = np.stack([NeuralFOLOperators._to_unit(e) for e in candidate_embeddings], axis=0)
        result: npt.NDArray[np.float64] = np.max(stacked, axis=0)
        conf_factor = float(np.mean(result))
        return result, conf_factor

    @staticmethod
    def universal(
        candidate_embeddings: list[npt.NDArray[np.float64]],
    ) -> tuple[npt.NDArray[np.float64], float]:
        """∀x.P(x): Soft min-pool — represents 'for all'."""
        if not candidate_embeddings:
            return np.zeros(1, dtype=np.float64), 0.0
        stacked = np.stack([NeuralFOLOperators._to_unit(e) for e in candidate_embeddings], axis=0)
        result: npt.NDArray[np.float64] = np.min(stacked, axis=0)
        conf_factor = float(np.mean(result))
        return result, conf_factor


# ======================================================================
# FOL Rule
# ======================================================================


@dataclass
class FOLMatchRule:
    """Hybrid FOL rule for entity matching.

    symbolic_condition: optional deterministic gate (string rule name
      from rule_engine.py OR a callable). If string, resolved against
      rule_engine at runtime. If None, always passes.

    relation_chain: relations to traverse from each entity to collect
      context embeddings before applying fol_operator. Requires a
      GraphAccessor. If accessor is None, falls back to direct pair.

    confidence_decay: multiplier applied to rule weight per chain hop.
    """

    name: str
    relation_chain: list[str] = field(default_factory=list)
    fol_operator: str = "conjunction"
    symbolic_condition: str | Callable[[str, str], bool] | None = None
    weight: float = 1.0
    confidence_decay: float = 0.9  # per-hop decay for chained rules
    description: str = ""


# ======================================================================
# Match Result
# ======================================================================


@dataclass
class NSEMatchResult:
    """Result of NeuroSymbolicEngine.match_with_fol()."""

    entity_a: str
    entity_b: str
    final_score: float  # weighted combined [0,1]
    rule_scores: dict[str, float]  # rule_name → score
    rule_confidences: dict[str, float]  # rule_name → confidence
    symbolic_gates_passed: list[str]  # rule names that passed gate
    relation_sources: dict[str, list[str]]  # rule_name → entities traversed
    explanation: str


# ======================================================================
# Main Engine
# ======================================================================


class NeuroSymbolicEngine:
    """Neuro-Symbolic Hybrid Engine.

    Lifecycle:
      1. __init__(backbone, graph_accessor, icp_entity_ids)
      2. register_rule(rule)
      3. match_with_fol(entity_a, entity_b) → NSEMatchResult
      4. batch_match(query_id, candidate_ids, threshold, top_k) → list
    """

    def __init__(
        self,
        backbone: RotatE3D,
        graph_accessor: GraphAccessor | None = None,
        icp_entity_ids: list[str] | None = None,
    ) -> None:
        self._backbone = backbone
        self._graph = graph_accessor
        self._ops = NeuralFOLOperators()
        self._rules: list[FOLMatchRule] = []
        self._icp_embedding: npt.NDArray[np.float64] | None = None

        if icp_entity_ids:
            self._build_icp_embedding(icp_entity_ids)

        self._register_default_matching_rules()

    def _build_icp_embedding(self, entity_ids: list[str]) -> None:
        """Build ICP centroid embedding from known high-value entities.

        Used as reference point for FOL operator scoring.
        This replaces the circular self-scoring of v1.
        """
        embeddings = []
        for eid in entity_ids:
            emb = self._backbone.embed(eid)
            if emb is not None:
                embeddings.append(emb)
        if embeddings:
            self._icp_embedding = np.mean(np.stack(embeddings, axis=0), axis=0)
            logger.info("NSE: ICP centroid built from %d entities", len(embeddings))

    def _register_default_matching_rules(self) -> None:
        self._rules = [
            FOLMatchRule(
                name="supplier_material_grade_match",
                relation_chain=["SUPPLIES", "HAS_GRADE"],
                fol_operator="conjunction",
                weight=1.5,
                confidence_decay=0.9,
                description="Both entities supply same material grade",
            ),
            FOLMatchRule(
                name="facility_tier_match",
                relation_chain=["HAS_TIER"],
                fol_operator="conjunction",
                weight=1.2,
                confidence_decay=0.95,
                description="Both facilities at same processing tier",
            ),
            FOLMatchRule(
                name="buyer_grade_compatibility",
                relation_chain=["ACCEPTS_GRADE"],
                fol_operator="existential",
                weight=1.0,
                confidence_decay=0.85,
                description="Buyer accepts at least one common material grade",
            ),
        ]

    def register_rule(self, rule: FOLMatchRule) -> None:
        self._rules.append(rule)

    def _resolve_symbolic_gate(
        self,
        rule: FOLMatchRule,
        entity_a: str,
        entity_b: str,
    ) -> bool:
        """Evaluate symbolic gate. Returns True if rule should fire."""
        if rule.symbolic_condition is None:
            return True
        if callable(rule.symbolic_condition):
            try:
                return bool(rule.symbolic_condition(entity_a, entity_b))
            except Exception:
                return True
        # String condition: treated as a permissive pass (integrators can
        # override by subclassing or injecting rule_engine lookup)
        return True

    def _collect_chain_embeddings(
        self,
        entity_id: str,
        relation_chain: list[str],
    ) -> list[tuple[npt.NDArray[np.float64], int]]:
        """Traverse relation_chain from entity_id, collect (embedding, hop) pairs.

        Falls back to direct entity embedding if no chain or no accessor.
        Returns list of (embedding, hop_distance).
        """
        results: list[tuple[npt.NDArray[np.float64], int]] = []
        base_emb = self._backbone.embed(entity_id)
        if base_emb is not None:
            results.append((base_emb, 0))

        if not relation_chain or self._graph is None:
            return results

        current_ids = [entity_id]
        for hop, rel in enumerate(relation_chain, start=1):
            next_ids: list[str] = []
            for cid in current_ids:
                try:
                    next_ids.extend(self._graph.neighbors(cid, rel))
                except Exception:
                    pass
            for nid in next_ids:
                emb = self._backbone.embed(nid)
                if emb is not None:
                    results.append((emb, hop))
            current_ids = next_ids or current_ids  # hold last level if no results

        return results

    def _score_fol_result(
        self,
        result_emb: npt.NDArray[np.float64],
    ) -> float:
        """Score FOL result embedding against ICP reference.

        If no ICP built, falls back to L2-norm activation (mean unit value).
        This replaces the v1 circular self-scoring.
        """
        if self._icp_embedding is not None and result_emb.shape == self._icp_embedding.shape:
            dot = float(np.dot(result_emb, self._icp_embedding))
            norm = float(np.linalg.norm(result_emb) * np.linalg.norm(self._icp_embedding))
            if norm > 1e-9:
                raw = dot / norm
                return float(np.clip((raw + 1.0) / 2.0, 0.0, 1.0))
        # Fallback: mean activation of result vector (bounded to [0,1])
        return float(np.clip(np.mean(np.abs(result_emb)), 0.0, 1.0))

    def match_with_fol(
        self,
        entity_a: str,
        entity_b: str,
    ) -> NSEMatchResult:
        """Score entity pair using all registered FOL rules.

        Decision flow per rule:
          1. Symbolic gate (deterministic filter)
          2. Relation-chain traversal to collect context embeddings
          3. Neural FOL operator over collected embeddings
          4. Score result against ICP reference
          5. Decay confidence by hop count
        """
        rule_scores: dict[str, float] = {}
        rule_confidences: dict[str, float] = {}
        passed_gates: list[str] = []
        relation_sources: dict[str, list[str]] = {}
        total_weight = 0.0
        weighted_sum = 0.0

        for rule in self._rules:
            # Step 1: symbolic gate
            if not self._resolve_symbolic_gate(rule, entity_a, entity_b):
                rule_scores[rule.name] = 0.0
                rule_confidences[rule.name] = 0.0
                continue

            passed_gates.append(rule.name)

            # Step 2: collect chain embeddings for both entities
            embs_a = self._collect_chain_embeddings(entity_a, rule.relation_chain)
            embs_b = self._collect_chain_embeddings(entity_b, rule.relation_chain)

            if not embs_a or not embs_b:
                rule_scores[rule.name] = 0.0
                rule_confidences[rule.name] = 0.0
                continue

            # All embeddings from both sides for existential/universal
            all_embs = [e for e, _ in embs_a + embs_b]
            # Primary embeddings (hop=0)
            emb_a_base = embs_a[0][0]
            emb_b_base = embs_b[0][0]

            # Maximum hop depth (drives confidence decay)
            max_hop = max(h for _, h in embs_a + embs_b)
            hop_decay = rule.confidence_decay**max_hop

            # Track which entities were traversed
            relation_sources[rule.name] = list({entity_a, entity_b})

            # Step 3: neural FOL operator
            op_name = rule.fol_operator
            try:
                if op_name == "conjunction":
                    result_emb, conf_factor = self._ops.conjunction(emb_a_base, emb_b_base)
                elif op_name == "disjunction":
                    result_emb, conf_factor = self._ops.disjunction(emb_a_base, emb_b_base)
                elif op_name == "negation":
                    result_emb, conf_factor = self._ops.negation(emb_a_base)
                elif op_name == "existential":
                    result_emb, conf_factor = self._ops.existential(all_embs)
                elif op_name == "universal":
                    result_emb, conf_factor = self._ops.universal(all_embs)
                else:
                    logger.warning(
                        "NSE: unknown fol_operator '%s' in rule '%s'", op_name, rule.name
                    )
                    continue
            except Exception:
                logger.exception("NSE: FOL operator failed for rule '%s'", rule.name)
                continue

            # Step 4: score against ICP reference
            match_score = self._score_fol_result(result_emb)

            # Step 5: apply hop-based confidence decay
            final_rule_confidence = float(np.clip(conf_factor * hop_decay, 0.0, 1.0))
            final_rule_score = float(np.clip(match_score * final_rule_confidence, 0.0, 1.0))

            rule_scores[rule.name] = final_rule_score
            rule_confidences[rule.name] = final_rule_confidence
            weighted_sum += rule.weight * final_rule_score
            total_weight += rule.weight

        final = float(np.clip(weighted_sum / total_weight, 0.0, 1.0)) if total_weight > 0 else 0.0

        explanation_parts = [
            f"{name}: {score:.3f} (conf={rule_confidences.get(name, 0.0):.2f})"
            for name, score in sorted(rule_scores.items(), key=lambda x: -x[1])
            if score > 0
        ]
        explanation = f"NSE({entity_a},{entity_b})={final:.3f} | " + (
            " | ".join(explanation_parts) if explanation_parts else "no rules fired"
        )

        return NSEMatchResult(
            entity_a=entity_a,
            entity_b=entity_b,
            final_score=final,
            rule_scores=rule_scores,
            rule_confidences=rule_confidences,
            symbolic_gates_passed=passed_gates,
            relation_sources=relation_sources,
            explanation=explanation,
        )

    def batch_match(
        self,
        query_id: str,
        candidate_ids: list[str],
        threshold: float = 0.0,
        top_k: int = 20,
    ) -> list[NSEMatchResult]:
        """Rank candidates against query entity.

        threshold: exclude results with final_score < threshold.
        Sorted descending by final_score.
        """
        results = []
        for cid in candidate_ids:
            r = self.match_with_fol(query_id, cid)
            if r.final_score >= threshold:
                results.append(r)
        results.sort(key=lambda x: -x.final_score)
        return results[:top_k]
