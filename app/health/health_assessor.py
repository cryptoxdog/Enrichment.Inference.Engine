"""
HEALTH assessment engine.

Computes per-entity health scores from enrichment data + field confidence maps,
aggregates into CRM-wide health, and produces the AI Readiness Score that
powers the Seed tier conversion funnel.
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Protocol, Sequence

from .health_models import (
    AssessmentConfig,
    AssessmentResult,
    AssessmentScope,
    CRMHealth,
    EntityHealth,
    EntityHealthSummary,
    EnrichmentTrigger,
    FieldHealth,
    HealthAction,
    HealthWeights,
    RecommendedAction,
    TriggerReason,
    compute_ai_readiness,
    compute_composite_health,
    compute_freshness,
)


# ─── Data Source Protocols ────────────────────────────────────


class EntityRecord(Protocol):
    """Minimal entity record protocol — adapters for CRM-specific stores."""

    @property
    def entity_id(self) -> str: ...
    @property
    def domain(self) -> str: ...
    @property
    def fields(self) -> dict[str, Any]: ...
    @property
    def field_confidences(self) -> dict[str, float]: ...
    @property
    def field_sources(self) -> dict[str, str]: ...
    @property
    def field_updated_at(self) -> dict[str, datetime]: ...
    @property
    def last_enriched_at(self) -> datetime | None: ...
    @property
    def crm_values(self) -> dict[str, Any]: ...


class DomainSchema(Protocol):
    """Domain YAML schema describing expected fields, gates, scoring dims."""

    @property
    def domain(self) -> str: ...
    @property
    def expected_fields(self) -> list[str]: ...
    @property
    def gate_fields(self) -> list[str]: ...
    @property
    def scoring_fields(self) -> list[str]: ...
    @property
    def field_types(self) -> dict[str, str]: ...


class EntityDataStore(Protocol):
    """Abstract store for querying entity records."""

    def list_entity_ids(self, domain: str) -> list[str]: ...
    def get_entity(self, entity_id: str) -> EntityRecord | None: ...
    def get_entities(self, entity_ids: list[str]) -> list[EntityRecord]: ...
    def count_entities(self, domain: str) -> int: ...
    def count_graph_synced(self, domain: str) -> int: ...


# ─── Entity Health Assessor ──────────────────────────────────


class HealthAssessor:
    """Core HEALTH engine. Assesses entities and produces actionable health data."""

    def __init__(
        self,
        data_store: EntityDataStore,
        domain_schema: DomainSchema,
        config: AssessmentConfig | None = None,
    ) -> None:
        self._store = data_store
        self._schema = domain_schema
        self._config = config or AssessmentConfig(domain=domain_schema.domain)
        self._weights = self._config.weights or HealthWeights()

    def assess_entity(self, record: EntityRecord) -> EntityHealth:
        """Compute full health assessment for a single entity."""
        expected = set(self._schema.expected_fields)
        _filled = {k for k, v in record.fields.items() if v is not None and k in expected}
        total_expected = len(expected)
        completeness = len(_filled) / total_expected if total_expected > 0 else 0.0

        freshness = compute_freshness(
            record.last_enriched_at,
            half_life_days=self._config.staleness_days,
        )

        confidences = record.field_confidences
        conf_values = [v for k, v in confidences.items() if k in expected]
        avg_conf = sum(conf_values) / len(conf_values) if conf_values else 0.0

        consistency = self._compute_consistency(record, expected)

        composite = compute_composite_health(
            completeness, freshness, avg_conf, consistency, self._weights
        )

        gate_missing = [f for f in self._schema.gate_fields if f not in filled]
        scoring_missing = [f for f in self._schema.scoring_fields if f not in filled]

        stale_count = 0
        low_conf_count = 0
        now = datetime.now(timezone.utc)
        stale_threshold_secs = self._config.staleness_days * 86400
        for fname in filled:
            updated = record.field_updated_at.get(fname)
            if updated is not None:
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if (now - updated).total_seconds() > stale_threshold_secs:
                    stale_count += 1
            conf = confidences.get(fname, 0.0)
            if conf < self._config.confidence_floor:
                low_conf_count += 1

        actions = self._recommend_actions(
            record,
            expected,
            gate_missing,
            scoring_missing,
            freshness,
            avg_conf,
            consistency,
        )

        return EntityHealth(
            entity_id=record.entity_id,
            domain=record.domain,
            completeness=round(completeness, 4),
            freshness=round(freshness, 4),
            confidence=round(avg_conf, 4),
            consistency=round(consistency, 4),
            composite_health=round(composite, 4),
            last_enriched_at=record.last_enriched_at,
            field_count_total=total_expected,
            field_count_filled=len(_filled),
            field_count_stale=stale_count,
            field_count_low_confidence=low_conf_count,
            gate_fields_missing=gate_missing,
            scoring_fields_missing=scoring_missing,
            recommended_actions=actions,
        )

    def assess_full_crm(self) -> AssessmentResult:
        """Run assessment across the entire CRM entity base for a domain."""
        start_ms = time.monotonic_ns()
        domain = self._config.domain

        if self._config.scope == AssessmentScope.ENTITY and self._config.entity_ids:
            entity_ids = self._config.entity_ids
        else:
            entity_ids = self._store.list_entity_ids(domain)

        records = self._store.get_entities(entity_ids)
        entity_healths: list[EntityHealth] = []
        for rec in records:
            eh = self.assess_entity(rec)
            entity_healths.append(eh)

        field_health = self._aggregate_field_health(records)
        crm_health = self._build_crm_health(entity_healths, field_health, domain)
        summary = self._build_summary(entity_healths)

        triggers: list[EnrichmentTrigger] = []
        if self._config.auto_trigger_enrichment:
            triggers = self._generate_triggers(entity_healths)

        elapsed_ms = int((time.monotonic_ns() - start_ms) / 1_000_000)

        return AssessmentResult(
            config=self._config,
            crm_health=crm_health,
            entity_health_summary=summary,
            triggers_generated=triggers,
            duration_ms=elapsed_ms,
        )

    # ─── Internal: Consistency ────────────────────────────────

    def _compute_consistency(self, record: EntityRecord, expected: set[str]) -> float:
        """Compare enriched values against CRM originals.

        For fields present in both enriched and CRM, compute agreement ratio.
        Missing CRM values are excluded (not penalized — enrichment fills gaps).
        """
        crm = record.crm_values
        enriched = record.fields
        comparable = 0
        agreed = 0
        for fname in expected:
            crm_val = crm.get(fname)
            enr_val = enriched.get(fname)
            if crm_val is not None and enr_val is not None:
                comparable += 1
                if self._values_agree(crm_val, enr_val):
                    agreed += 1
        return agreed / comparable if comparable > 0 else 1.0

    @staticmethod
    def _values_agree(crm_val: Any, enriched_val: Any) -> bool:
        """Fuzzy equality for CRM/enriched comparison."""
        if crm_val == enriched_val:
            return True
        if isinstance(crm_val, str) and isinstance(enriched_val, str):
            return crm_val.strip().lower() == enriched_val.strip().lower()
        if isinstance(crm_val, (int, float)) and isinstance(enriched_val, (int, float)):
            if crm_val == 0 and enriched_val == 0:
                return True
            denom = max(abs(crm_val), abs(enriched_val))
            return abs(crm_val - enriched_val) / denom < 0.05
        if isinstance(crm_val, list) and isinstance(enriched_val, list):
            return set(str(v).lower() for v in crm_val) == set(str(v).lower() for v in enriched_val)
        return str(crm_val).strip().lower() == str(enriched_val).strip().lower()

    # ─── Internal: Recommendations ───────────────────────────

    def _recommend_actions(
        self,
        record: EntityRecord,
        expected: set[str],
        gate_missing: list[str],
        scoring_missing: list[str],
        freshness: float,
        avg_conf: float,
        consistency: float,
    ) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []

        for gf in gate_missing:
            actions.append(
                RecommendedAction(
                    action=HealthAction.FILL_MISSING,
                    field_name=gf,
                    reason=f"Gate-critical field '{gf}' is missing — blocks all matching",
                    priority=1.0,
                )
            )

        if freshness < 0.30:
            actions.append(
                RecommendedAction(
                    action=HealthAction.REFRESH_STALE,
                    reason=f"Entity freshness {freshness:.2f} below 0.30 — data is stale",
                    priority=0.90,
                )
            )

        for sf in scoring_missing[:5]:
            actions.append(
                RecommendedAction(
                    action=HealthAction.FILL_MISSING,
                    field_name=sf,
                    reason=f"Scoring field '{sf}' is missing — degrades match quality",
                    priority=0.75,
                )
            )

        low_conf_fields = [
            (k, v)
            for k, v in record.field_confidences.items()
            if v < self._config.confidence_floor and k in expected
        ]
        for fname, conf in sorted(low_conf_fields, key=lambda x: x[1])[:5]:
            actions.append(
                RecommendedAction(
                    action=HealthAction.VERIFY_FIELD,
                    field_name=fname,
                    reason=f"Field '{fname}' confidence {conf:.2f} below threshold {self._config.confidence_floor}",
                    priority=0.60,
                )
            )

        if consistency < 0.70:
            crm = record.crm_values
            enriched = record.fields
            conflicts = [
                k
                for k in expected
                if crm.get(k) is not None
                and enriched.get(k) is not None
                and not self._values_agree(crm[k], enriched[k])
            ]
            for cf in conflicts[:3]:
                actions.append(
                    RecommendedAction(
                        action=HealthAction.RESOLVE_CONFLICT,
                        field_name=cf,
                        reason=f"CRM and enriched values disagree for '{cf}'",
                        priority=0.55,
                    )
                )

        actions.sort(key=lambda a: a.priority, reverse=True)
        return actions

    # ─── Internal: Field Health Aggregation ───────────────────

    def _aggregate_field_health(self, records: Sequence[EntityRecord]) -> list[FieldHealth]:
        """Aggregate field-level metrics across all entities."""
        expected = self._schema.expected_fields
        gate_set = set(self._schema.gate_fields)
        scoring_set = set(self._schema.scoring_fields)
        n = len(records)
        if n == 0:
            return []

        stats: dict[str, dict[str, Any]] = {}
        for fname in expected:
            stats[fname] = {
                "fill_count": 0,
                "conf_sum": 0.0,
                "conf_min": 1.0,
                "conf_max": 0.0,
                "ages": [],
                "outlier_count": 0,
                "value_counts": defaultdict(int),
            }

        now = datetime.now(timezone.utc)
        for rec in records:
            for fname in expected:
                s = stats[fname]
                val = rec.fields.get(fname)
                if val is not None:
                    s["fill_count"] += 1
                    conf = rec.field_confidences.get(fname, 0.0)
                    s["conf_sum"] += conf
                    s["conf_min"] = min(s["conf_min"], conf)
                    s["conf_max"] = max(s["conf_max"], conf)
                    updated = rec.field_updated_at.get(fname)
                    if updated is not None:
                        if updated.tzinfo is None:
                            updated = updated.replace(tzinfo=timezone.utc)
                        age = (now - updated).total_seconds() / 86400.0
                        s["ages"].append(age)
                    vkey = str(val)[:100]
                    s["value_counts"][vkey] += 1

        result: list[FieldHealth] = []
        for fname in expected:
            s = stats[fname]
            fc = s["fill_count"]
            fill_rate = fc / n if n > 0 else 0.0
            avg_conf = s["conf_sum"] / fc if fc > 0 else 0.0
            ages = sorted(s["ages"])
            p50 = ages[len(ages) // 2] if ages else 0.0
            p90 = ages[int(len(ages) * 0.9)] if ages else 0.0

            top_values = dict(
                sorted(s["value_counts"].items(), key=lambda x: x[1], reverse=True)[:10]
            )

            result.append(
                FieldHealth(
                    field_name=fname,
                    fill_rate=round(fill_rate, 4),
                    avg_confidence=round(avg_conf, 4),
                    min_confidence=round(s["conf_min"], 4) if fc > 0 else 0.0,
                    max_confidence=round(s["conf_max"], 4) if fc > 0 else 0.0,
                    staleness_p50_days=round(p50, 2),
                    staleness_p90_days=round(p90, 2),
                    outlier_count=s["outlier_count"],
                    total_entities=n,
                    value_distribution=top_values,
                    is_gate_critical=fname in gate_set,
                    is_scoring_dimension=fname in scoring_set,
                )
            )

        result.sort(
            key=lambda fh: (not fh.is_gate_critical, not fh.is_scoring_dimension, fh.health_score)
        )
        return result

    # ─── Internal: CRM Health ─────────────────────────────────

    def _build_crm_health(
        self,
        entity_healths: list[EntityHealth],
        field_health: list[FieldHealth],
        domain: str,
    ) -> CRMHealth:
        n = len(entity_healths)
        if n == 0:
            return CRMHealth(domain=domain, total_entities=0, ai_readiness_score=0.0)

        avg_comp = sum(e.completeness for e in entity_healths) / n
        avg_fresh = sum(e.freshness for e in entity_healths) / n
        avg_conf = sum(e.confidence for e in entity_healths) / n
        avg_cons = sum(e.consistency for e in entity_healths) / n

        enriched_count = sum(1 for e in entity_healths if e.last_enriched_at is not None)
        enrichment_cov = enriched_count / n if n > 0 else 0.0

        total_entities_domain = self._store.count_entities(domain)
        graph_synced = self._store.count_graph_synced(domain)
        graph_cov = graph_synced / total_entities_domain if total_entities_domain > 0 else 0.0

        gate_fhs = [fh for fh in field_health if fh.is_gate_critical]
        gate_fill = sum(fh.fill_rate for fh in gate_fhs) / len(gate_fhs) if gate_fhs else 1.0

        ai_ready = compute_ai_readiness(
            avg_comp, avg_fresh, avg_conf, enrichment_cov, graph_cov, gate_fill
        )

        below = sum(1 for e in entity_healths if e.composite_health < self._config.health_threshold)
        needing = sum(1 for e in entity_healths if e.needs_enrichment)

        return CRMHealth(
            domain=domain,
            total_entities=total_entities_domain,
            ai_readiness_score=round(ai_ready, 4),
            avg_completeness=round(avg_comp, 4),
            avg_freshness=round(avg_fresh, 4),
            avg_confidence=round(avg_conf, 4),
            avg_consistency=round(avg_cons, 4),
            field_health=field_health,
            enrichment_coverage=round(enrichment_cov, 4),
            graph_coverage=round(graph_cov, 4),
            entities_below_threshold=below,
            entities_needing_enrichment=needing,
        )

    # ─── Internal: Summary ────────────────────────────────────

    @staticmethod
    def _build_summary(entity_healths: list[EntityHealth]) -> EntityHealthSummary:
        n = len(entity_healths)
        if n == 0:
            return EntityHealthSummary()

        composites = [e.composite_health for e in entity_healths]
        avg_h = sum(composites) / n
        healthy = sum(1 for c in composites if c >= 0.70)
        needing = sum(1 for e in entity_healths if e.needs_enrichment)

        dist = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}
        for c in composites:
            if c >= 0.90:
                dist["excellent"] += 1
            elif c >= 0.70:
                dist["good"] += 1
            elif c >= 0.50:
                dist["fair"] += 1
            else:
                dist["poor"] += 1

        return EntityHealthSummary(
            total_assessed=n,
            healthy_count=healthy,
            unhealthy_count=n - healthy,
            needs_enrichment_count=needing,
            avg_composite_health=round(avg_h, 4),
            min_composite_health=round(min(composites), 4),
            max_composite_health=round(max(composites), 4),
            health_distribution=dist,
        )

    # ─── Internal: Trigger Generation ─────────────────────────

    def _generate_triggers(self, entity_healths: list[EntityHealth]) -> list[EnrichmentTrigger]:
        """Generate HEALTH → ENRICH re-enrichment triggers for unhealthy entities."""
        triggers: list[EnrichmentTrigger] = []

        for eh in entity_healths:
            if eh.is_healthy:
                continue

            if eh.gate_fields_missing:
                triggers.append(
                    EnrichmentTrigger(
                        entity_id=eh.entity_id,
                        domain=eh.domain,
                        reason=TriggerReason.GATE_FIELD_MISSING,
                        priority=1.0,
                        target_fields=eh.gate_fields_missing,
                        current_health=eh.composite_health,
                        metadata={"gate_fields": eh.gate_fields_missing},
                    )
                )
                continue

            if eh.freshness < 0.30:
                reason = TriggerReason.STALENESS
                priority = 0.90
            elif eh.confidence < self._config.confidence_floor:
                reason = TriggerReason.LOW_CONFIDENCE
                priority = 0.80
            elif eh.completeness < 0.50:
                reason = TriggerReason.LOW_COMPLETENESS
                priority = 0.70
            elif eh.consistency < 0.70:
                reason = TriggerReason.INCONSISTENCY
                priority = 0.60
            else:
                reason = TriggerReason.COMPOSITE_BELOW_THRESHOLD
                priority = 0.50

            target_fields: list[str] = []
            for action in eh.recommended_actions:
                if action.field_name and action.action in (
                    HealthAction.FILL_MISSING,
                    HealthAction.VERIFY_FIELD,
                    HealthAction.REFRESH_STALE,
                ):
                    target_fields.append(action.field_name)

            triggers.append(
                EnrichmentTrigger(
                    entity_id=eh.entity_id,
                    domain=eh.domain,
                    reason=reason,
                    priority=priority,
                    target_fields=target_fields[:20],
                    current_health=eh.composite_health,
                )
            )

        triggers.sort(key=lambda t: t.priority, reverse=True)
        return triggers
