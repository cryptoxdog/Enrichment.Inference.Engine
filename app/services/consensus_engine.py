"""
Multi-variation weighted consensus synthesis.

Algorithm:
  For each field across N validated responses:
    weighted_score = (agreement_ratio) × (mean_confidence_of_agreeing_responses)
    Keep signal if weighted_score ≥ threshold.

  For list fields: each LIST ITEM is scored independently.
  For scalar fields: the value with highest weighted score wins.

Audit fixes applied:
  - M7: Single-payload penalty — if only 1/N valid, confidence is halved.
  - LOW: Case-normalizes strings before counting agreement.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Any

import structlog

logger = structlog.get_logger("consensus_engine")


def synthesize(
    payloads: list[dict[str, Any]],
    threshold: float,
    total_attempted: int | None = None,
) -> dict[str, Any]:
    """
    Synthesize N validated responses into one consensus result.

    Args:
        payloads: Validated response dicts (each has 'confidence' key).
        threshold: Minimum weighted score to accept a signal.
        total_attempted: Original variation count (for quorum penalty).

    Returns:
        {"fields": {..}, "confidence": float}
    """
    n = len(payloads)
    attempted = total_attempted or n

    if n == 0:
        return {"fields": {}, "confidence": 0.0}

    # ── Single-payload penalty ───────────────────────
    if n == 1:
        p = payloads[0].copy()
        conf = p.pop("confidence", 0.5)
        # If we attempted multiple but only 1 validated, penalize
        if attempted > 1:
            conf *= 0.5
            logger.info("single_payload_penalty", original_conf=conf * 2, penalized=conf)
        return {"fields": p, "confidence": conf}

    # ── Separate confidence from fields ──────────────
    confidences: list[float] = []
    field_payloads: list[dict] = []
    for p in payloads:
        p = p.copy()
        confidences.append(p.pop("confidence", 0.5))
        field_payloads.append(p)

    # ── Count agreement ──────────────────────────────
    list_counter: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    scalar_counter: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for i, payload in enumerate(field_payloads):
        conf = confidences[i]
        for field_name, value in payload.items():
            if isinstance(value, list):
                for item in value:
                    key = str(item).strip().lower()
                    if key:
                        list_counter[field_name][key].append(conf)
            else:
                key = str(value).strip().lower()
                if key:
                    scalar_counter[field_name][(key, str(value).strip())].append(conf)

    final_fields: dict[str, Any] = {}
    weights: list[float] = []

    # ── Synthesize list fields ───────────────────────
    for field_name, items in list_counter.items():
        accepted = []
        for item_key, item_confs in items.items():
            agreement = len(item_confs) / n
            avg_conf = statistics.mean(item_confs)
            weighted = agreement * avg_conf
            if weighted >= threshold:
                accepted.append(item_key)
                weights.append(weighted)
        if accepted:
            final_fields[field_name] = accepted

    # ── Synthesize scalar fields ─────────────────────
    for field_name, values in scalar_counter.items():
        best_display: str | None = None
        best_weight = 0.0
        for (norm_key, display_val), value_confs in values.items():
            agreement = len(value_confs) / n
            avg_conf = statistics.mean(value_confs)
            weighted = agreement * avg_conf
            if weighted > best_weight:
                best_weight = weighted
                best_display = display_val
        if best_display is not None and best_weight >= threshold:
            final_fields[field_name] = best_display
            weights.append(best_weight)

    final_confidence = statistics.mean(weights) if weights else 0.0

    logger.info(
        "consensus_synthesized",
        variations_valid=n,
        variations_attempted=attempted,
        fields_accepted=len(final_fields),
        confidence=round(final_confidence, 4),
    )

    return {"fields": final_fields, "confidence": final_confidence}
