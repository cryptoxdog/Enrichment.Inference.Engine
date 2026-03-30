"""
--- L9_META ---
l9_schema: 1
origin: engine-specific
engine: graph
layer: [kge]
tags: [kge, rotate3d, matching, self-adversarial]
owner: engine-team
status: active
--- /L9_META ---

RotatE3D — Complex rotation KGE with self-adversarial negative sampling.

Implements Sun et al. (2019) RotatE with self-adversarial weighting.
Designed as a drop-in EnsembleController variant alongside CompoundE3D,
prioritizing P1 entity matching (symmetric / antisymmetric relation patterns
such as SAME_GRADE_SUPPLIER, TIER_ABOVE, COMPATIBLE_BUYER).

Scoring convention: score_triple() returns [0,1] where 1 = best match.
This aligns with VariantScore expectations in ensemble.py.

Consumes:
  engine.kge.ensemble.VariantScore       — output to EnsembleController
  engine.config.settings.settings        — kge_enabled, kge_embedding_dim
  engine.scoring.assembler._compile_kge  — via write_to_graph()

Fixes applied vs. v1:
  - sigmoid inversion corrected: sigmoid(gamma - dist) not sigmoid(dist - gamma)
  - adversarial sampler corrected: negatives sampled once, weights applied to
    same batch (dist < gamma condition inverted; harder negatives = larger dist
    above margin → higher adversarial weight)
  - SGD updates now cover relation phase parameters
  - L2 regularization on entity re/im embeddings
  - Early-stop on convergence tolerance
  - embed() returns canonical (dim,) form = (re + im) / 2
  - embed_complex() returns full (2*dim,) concatenation for internal use
  - write_to_graph() added for assembler._compile_kge() parity with CompoundE3D
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import numpy.typing as npt

from engine.config.settings import settings
from engine.kge.ensemble import VariantScore

logger = logging.getLogger(__name__)

VARIANT_ID = "rotate3d"


@dataclass
class RotatE3DConfig:
    """Runtime configuration for RotatE3D.

    adversarial_temperature: Controls sharpness of negative weighting.
        Sun et al. §3 recommend starting at 0.5 and annealing to 1.0.
        Stored as initial value; annealing schedule applied during train().
    regularization: L2 coefficient on entity embeddings.
    convergence_tol: Stop early if epoch_loss delta < this value.
    """

    embedding_dim: int = 256
    learning_rate: float = 1e-3
    gamma: float = 6.0  # margin (gamma in RotatE paper)
    negative_sample_size: int = 64
    adversarial_temperature: float = 0.5  # initial; anneals to 1.0
    regularization: float = 1e-4
    convergence_tol: float = 1e-4
    max_epochs: int = 200
    batch_size: int = 512
    training_relations: list[str] = field(default_factory=list)

    @classmethod
    def from_settings(cls) -> RotatE3DConfig:
        return cls(embedding_dim=settings.kge_embedding_dim)


class RotatE3D:
    """RotatE3D embedding model.

    Public surface:
      train(triples)                          — fit on (h, r, t) triples
      score_triple(h, r, t) → float [0,1]    — 1 = best match
      embed(entity_id) → ndarray(dim,)|None  — canonical (re+im)/2 form
      embed_complex(entity_id) → ndarray(2*dim,)|None  — full complex form
      predict_tail(h, r, candidates, k)       — ranked (id, score) list
      to_variant_score(h, r, t, conf)         — VariantScore for Ensemble
      compute_kge_scores(h, r, candidates)    — batch dict for write_to_graph
      write_to_graph(h, r, candidates)        — Neo4j kge_score writeback
    """

    def __init__(self, config: RotatE3DConfig | None = None) -> None:
        self.config = config or RotatE3DConfig.from_settings()
        self.dim = self.config.embedding_dim
        self._entity_re: dict[str, npt.NDArray[np.float64]] = {}
        self._entity_im: dict[str, npt.NDArray[np.float64]] = {}
        self._relation_phase: dict[str, npt.NDArray[np.float64]] = {}
        self._trained = False
        self._all_entities: list[str] = []
        self._training_metrics: dict[str, Any] = {}

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def embed_dim(self) -> int:
        """Canonical embedding dimension (matches CompoundE3D interface)."""
        return self.dim

    # ------------------------------------------------------------------ #
    # Training                                                             #
    # ------------------------------------------------------------------ #

    def train(
        self,
        triples: list[tuple[str, str, str]],
        epochs: int | None = None,
    ) -> dict[str, Any]:
        """Fit on (head_id, relation_type, tail_id) triples.

        Self-adversarial negative sampling per Sun et al. (2019):
          For each positive triple, sample a batch of negatives.
          Weight each negative by softmax over their scores —
          higher-scoring (harder) negatives receive higher weight.
          Loss = Σ_neg w_i * max(0, dist(pos) - dist(neg_i) + gamma)

        SGD updates cover: entity_re, entity_im, relation_phase.
        L2 regularization applied to entity embeddings only.
        Early stop when epoch loss delta < convergence_tol.
        """
        if not settings.kge_enabled:
            return {"status": "skipped", "reason": "kge_enabled=False"}

        epochs = epochs or self.config.max_epochs
        entities: set[str] = set()
        relations: set[str] = set()
        for h, r, t in triples:
            entities.update([h, t])
            relations.add(r)

        self._all_entities = list(entities)
        bound = np.sqrt(6.0 / self.dim)
        pi = np.pi

        for eid in entities:
            if eid not in self._entity_re:
                self._entity_re[eid] = np.random.uniform(-bound, bound, self.dim)
                self._entity_im[eid] = np.random.uniform(-bound, bound, self.dim)
        for rid in relations:
            if rid not in self._relation_phase:
                self._relation_phase[rid] = np.random.uniform(-pi, pi, self.dim)

        triples_arr = list(triples)
        lr = self.config.learning_rate
        reg = self.config.regularization
        ns = self.config.negative_sample_size
        gamma = self.config.gamma
        losses: list[float] = []
        prev_loss = float("inf")

        for epoch in range(epochs):
            # Anneal adversarial temperature: 0.5 → 1.0 linearly
            temp = 0.5 + 0.5 * (epoch / max(epochs - 1, 1))
            np.random.shuffle(triples_arr)
            epoch_loss = 0.0

            for h, r, t in triples_arr:
                pos_dist = self._distance(h, r, t)

                # Sample negatives once; compute distances once
                neg_entities = [np.random.choice(self._all_entities) for _ in range(ns)]
                neg_dists = np.array(
                    [self._distance(h, r, ne) for ne in neg_entities],
                    dtype=np.float64,
                )

                # Self-adversarial weights: harder negatives (larger neg_dist
                # means they score higher as positives would, i.e. smaller
                # distance means they're closer = harder to distinguish).
                # Weight harder negatives MORE: softmax over -dist (invert so
                # smaller distance → larger logit → larger weight).
                adv_weights = self._softmax_weights(-neg_dists, temp)

                # Margin-based loss per negative
                margins = np.maximum(0.0, gamma - neg_dists + pos_dist)
                triple_loss = float(np.sum(adv_weights * margins))
                epoch_loss += triple_loss

                # SGD update — only when loss > 0
                if triple_loss > 0:
                    h_re = self._entity_re.get(h)
                    h_im = self._entity_im.get(h)
                    t_re = self._entity_re.get(t)
                    t_im = self._entity_im.get(t)
                    phase = self._relation_phase.get(r)

                    if h_re is None or t_re is None or phase is None:
                        continue

                    r_re = np.cos(phase)
                    r_im = np.sin(phase)

                    # Gradient of ||h∘r - t||: update h, t, r
                    hr_re = h_re * r_re - h_im * r_im
                    hr_im = h_re * r_im + h_im * r_re
                    diff_re = hr_re - t_re
                    diff_im = hr_im - t_im

                    grad_scale = lr / (np.linalg.norm(np.concatenate([diff_re, diff_im])) + 1e-9)

                    # Entity re/im updates + L2 reg
                    self._entity_re[h] -= (
                        grad_scale * (diff_re * r_re + diff_im * r_im) + lr * reg * h_re
                    )
                    self._entity_im[h] -= (
                        grad_scale * (-diff_re * r_im + diff_im * r_re) + lr * reg * h_im
                    )
                    self._entity_re[t] += grad_scale * diff_re + lr * reg * t_re
                    self._entity_im[t] += grad_scale * diff_im + lr * reg * t_im

                    # Relation phase update
                    dphase = grad_scale * (
                        diff_re * (-h_re * r_im - h_im * r_re)
                        + diff_im * (h_re * r_re - h_im * r_im)
                    )
                    self._relation_phase[r] -= lr * dphase

            mean_loss = epoch_loss / max(len(triples_arr), 1)
            losses.append(mean_loss)

            # Early stop
            if abs(prev_loss - mean_loss) < self.config.convergence_tol and epoch > 10:
                logger.info(
                    "RotatE3D early stop at epoch %d (delta=%.6f)",
                    epoch,
                    abs(prev_loss - mean_loss),
                )
                break
            prev_loss = mean_loss

        self._trained = True
        self._training_metrics = {
            "status": "completed",
            "model": VARIANT_ID,
            "epochs_run": len(losses),
            "final_loss": losses[-1] if losses else 0.0,
            "num_entities": len(entities),
            "num_relations": len(relations),
        }
        return self._training_metrics

    # ------------------------------------------------------------------ #
    # Inference                                                            #
    # ------------------------------------------------------------------ #

    def score_triple(self, head: str, relation: str, tail: str) -> float:
        """Score (head, relation, tail). Returns [0,1], 1 = best match.

        Correct form: sigmoid(gamma - dist) so dist=0 → sigmoid(gamma) → 1.0
        (Fixes v1 inversion: sigmoid(dist - gamma) would score 0 at perfect match)
        """
        if not self._trained:
            return 0.0
        dist = self._distance(head, relation, tail)
        return float(1.0 / (1.0 + np.exp(-(self.config.gamma - dist))))

    def embed(self, entity_id: str) -> npt.NDArray[np.float64] | None:
        """Canonical (dim,) embedding: (re + im) / 2.

        Matches CompoundE3D.embed() output shape for consistent downstream use
        in NeuroSymbolicEngine and HyperRelationalEncoder.
        """
        re = self._entity_re.get(entity_id)
        im = self._entity_im.get(entity_id)
        if re is None or im is None:
            return None
        result: npt.NDArray[np.float64] = (re + im) / 2.0
        return result

    def embed_complex(self, entity_id: str) -> npt.NDArray[np.float64] | None:
        """Full (2*dim,) complex embedding: [re, im] concatenated.

        Use when full complex structure is required (e.g., direct RotatE scoring).
        """
        re = self._entity_re.get(entity_id)
        im = self._entity_im.get(entity_id)
        if re is None or im is None:
            return None
        return np.concatenate([re, im])

    def predict_tail(
        self,
        head: str,
        relation: str,
        candidates: list[str] | None = None,
        top_k: int = 10,
    ) -> list[tuple[str, float]]:
        """Rank candidate tails for (head, relation, ?). Descending by score."""
        if not self._trained:
            return []
        pool = candidates or self._all_entities
        scored = [(eid, self.score_triple(head, relation, eid)) for eid in pool]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def to_variant_score(
        self,
        head: str,
        relation: str,
        tail: str,
        confidence: float | None = None,
    ) -> VariantScore:
        """Produce VariantScore for EnsembleController.predict().

        confidence defaults to score_triple value (self-reported).
        Caller should override with val-set MRR-derived confidence when available.
        """
        score = self.score_triple(head, relation, tail)
        return VariantScore(
            variant_id=VARIANT_ID,
            variant_type="rotate3d",
            score=score,
            confidence=confidence if confidence is not None else score,
            metadata={
                "head": head,
                "relation": relation,
                "tail": tail,
                "gamma": self.config.gamma,
                "trained": self._trained,
            },
        )

    def compute_kge_scores(
        self,
        head: str,
        relation: str,
        candidate_ids: list[str],
    ) -> dict[str, float]:
        """Batch-compute kge_score for candidates.

        Output matches CompoundE3D.compute_kge_scores() signature for assembler
        compatibility. Maps entity_id → score [0,1].
        """
        return {cid: self.score_triple(head, relation, cid) for cid in candidate_ids}

    def write_to_graph(
        self,
        head: str,
        relation: str,
        candidate_ids: list[str],
    ) -> dict[str, float]:
        """Persist kge_score properties consumed by assembler._compile_kge().

        Returns scores dict (Neo4j writeback is handled by assembler).
        Mirrors CompoundE3D.compute_kge_scores() contract exactly.
        """
        scores = self.compute_kge_scores(head, relation, candidate_ids)
        logger.debug(
            "RotatE3D.write_to_graph: head=%s relation=%s candidates=%d",
            head,
            relation,
            len(candidate_ids),
        )
        return scores

    # ------------------------------------------------------------------ #
    # Internal                                                             #
    # ------------------------------------------------------------------ #

    def _distance(self, head: str, relation: str, tail: str) -> float:
        """RotatE distance: ||h ∘ r - t|| in complex embedding space."""
        h_re = self._entity_re.get(head)
        h_im = self._entity_im.get(head)
        t_re = self._entity_re.get(tail)
        t_im = self._entity_im.get(tail)
        phase = self._relation_phase.get(relation)

        if h_re is None or t_re is None:
            return float("inf")

        if phase is None:
            # Cold-start fallback: L2 in real subspace
            return float(np.linalg.norm(h_re - t_re))

        r_re = np.cos(phase)
        r_im = np.sin(phase)
        h_im_safe = h_im if h_im is not None else np.zeros_like(h_re)
        t_im_safe = t_im if t_im is not None else np.zeros_like(t_re)

        hr_re = h_re * r_re - h_im_safe * r_im
        hr_im = h_re * r_im + h_im_safe * r_re

        diff_re = hr_re - t_re
        diff_im = hr_im - t_im_safe
        return float(np.linalg.norm(np.concatenate([diff_re, diff_im])))

    @staticmethod
    def _softmax_weights(
        logits: npt.NDArray[np.float64],
        temperature: float,
    ) -> npt.NDArray[np.float64]:
        """Temperature-scaled softmax for adversarial weighting."""
        scaled = logits / (temperature + 1e-9)
        shifted = scaled - np.max(scaled)  # numerical stability
        exp_s = np.exp(shifted)
        result: npt.NDArray[np.float64] = exp_s / (exp_s.sum() + 1e-9)
        return result
