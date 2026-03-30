"""
PlastOS Mack AI Reasoning Engine v6.0 - Complete Implementation
================================================================

Main orchestration module for the PlastOS AI reasoning system.
Coordinates buyer matching, supplier intake, and intelligent decision-making
with emotional intelligence, multi-agent orchestration, and continuous learning.

Architecture:
- Deterministic matching via matcher.py (rule-based, explainable)
- AI-augmented insights via graph_service.py (Neo4j + RAG)
- Complete governance and audit trail compliance
- Autonomous processing with confidence-based escalation

Author: PlastOS Development Team
Version: 6.0
License: Proprietary
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

_logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================


@dataclass
class ReasoningContext:
    """Complete context for AI reasoning operations."""

    # Core entities
    supplier_intake_id: int | None = None
    supplier_partner_id: int | None = None
    buyer_partner_ids: list[int] = field(default_factory=list)

    # Material specifications
    polymer_type: str | None = None
    polymer_grade: str | None = None
    color: str | None = None
    melt_index: float | None = None
    density: float | None = None
    contamination_pct: float | None = None
    pcr_percentage: float | None = None

    # Business parameters
    quantity_kg: float | None = None
    target_price: float | None = None
    delivery_location: str | None = None
    delivery_date: datetime | None = None
    payment_terms: str | None = None

    # AI parameters
    confidence_threshold: float = 0.6
    use_emotional_intelligence: bool = True
    use_market_intelligence: bool = True
    cultural_context: str | None = None

    # Performance tracking
    processing_start: datetime | None = None
    processing_end: datetime | None = None

    def __post_init__(self):
        """Initialize processing timestamp."""
        if self.processing_start is None:
            self.processing_start = datetime.now()


@dataclass
class MatchResult:
    """Result from buyer matching operation."""

    buyer_partner_id: int
    total_score: float
    confidence: float

    # Score components
    technical_score: float = 0.0
    business_score: float = 0.0
    trust_score: float = 0.0

    # Technical factors
    polymer_compatibility: float = 0.0
    density_match: float = 0.0
    contamination_acceptable: bool = True
    pcr_compatible: bool = True

    # Business factors
    price_competitiveness: float = 0.0
    volume_capacity: float = 0.0
    delivery_feasibility: float = 0.0
    payment_alignment: float = 0.0

    # Relationship factors
    relationship_history: float = 0.0
    communication_quality: float = 0.0
    transaction_success_rate: float = 0.0

    # AI insights
    reasoning_trace: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    risk_factors: list[str] = field(default_factory=list)
    escalation_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "buyer_partner_id": self.buyer_partner_id,
            "total_score": round(self.total_score, 3),
            "confidence": round(self.confidence, 3),
            "technical_score": round(self.technical_score, 3),
            "business_score": round(self.business_score, 3),
            "trust_score": round(self.trust_score, 3),
            "polymer_compatibility": round(self.polymer_compatibility, 3),
            "density_match": round(self.density_match, 3),
            "contamination_acceptable": self.contamination_acceptable,
            "pcr_compatible": self.pcr_compatible,
            "price_competitiveness": round(self.price_competitiveness, 3),
            "volume_capacity": round(self.volume_capacity, 3),
            "delivery_feasibility": round(self.delivery_feasibility, 3),
            "payment_alignment": round(self.payment_alignment, 3),
            "relationship_history": round(self.relationship_history, 3),
            "communication_quality": round(self.communication_quality, 3),
            "transaction_success_rate": round(self.transaction_success_rate, 3),
            "reasoning_trace": self.reasoning_trace,
            "recommendations": self.recommendations,
            "risk_factors": self.risk_factors,
            "escalation_required": self.escalation_required,
        }


@dataclass
class ReasoningResult:
    """Complete result from reasoning engine execution."""

    success: bool
    confidence: float
    matches: list[MatchResult] = field(default_factory=list)

    # Processing metadata
    autonomous_processing: bool = False
    escalation_required: bool = False
    escalation_reason: str | None = None

    # Performance metrics
    processing_time_ms: float | None = None
    components_executed: list[str] = field(default_factory=list)

    # AI insights
    market_insights: dict[str, Any] = field(default_factory=dict)
    emotional_intelligence: dict[str, Any] = field(default_factory=dict)
    governance_compliance: dict[str, Any] = field(default_factory=dict)

    # Audit trail
    audit_trail_id: int | None = None
    reasoning_trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "success": self.success,
            "confidence": round(self.confidence, 3),
            "matches": [m.to_dict() for m in self.matches],
            "autonomous_processing": self.autonomous_processing,
            "escalation_required": self.escalation_required,
            "escalation_reason": self.escalation_reason,
            "processing_time_ms": round(self.processing_time_ms, 2)
            if self.processing_time_ms
            else None,
            "components_executed": self.components_executed,
            "market_insights": self.market_insights,
            "emotional_intelligence": self.emotional_intelligence,
            "governance_compliance": self.governance_compliance,
            "audit_trail_id": self.audit_trail_id,
            "reasoning_trace": self.reasoning_trace,
        }


# ============================================================================
# MAIN REASONING ENGINE
# ============================================================================


class MackReasoningEngine:
    """
    Main orchestrator for PlastOS AI reasoning operations.

    Coordinates:
    - Deterministic matching (matcher.py)
    - AI augmentation (graph_service.py)
    - Emotional intelligence
    - Multi-agent orchestration
    - Continuous learning
    - Governance compliance

    Performance Targets:
    - 95% autonomous processing rate
    - 90% match accuracy
    - ≤2 minutes response time
    - 99.5% technical validation accuracy
    - 100% governance compliance
    """

    def __init__(self, env):
        """
        Initialize reasoning engine with Odoo environment.

        Args:
            env: Odoo environment for database access
        """
        self.env = env
        self._matcher = None
        self._graph_service = None
        self._initialized = False

        # Performance tracking
        self._stats = {
            "total_requests": 0,
            "autonomous_processed": 0,
            "escalated": 0,
            "avg_confidence": 0.0,
            "avg_processing_time_ms": 0.0,
        }

        _logger.info("MackReasoningEngine v6.0 initialized")

    def _lazy_init(self):
        """Lazy initialization of heavy components."""
        if self._initialized:
            return

        try:
            # Import deterministic matcher
            from . import matcher

            self._matcher = matcher.DeterministicMatcher(self.env)

            # Import AI graph service
            from . import graph_service

            self._graph_service = graph_service.GraphService(self.env)

            self._initialized = True
            _logger.info("Reasoning engine components initialized successfully")

        except Exception as e:
            _logger.error(f"Failed to initialize reasoning engine components: {e}")
            raise

    # ========================================================================
    # PUBLIC API - MAIN ENTRY POINTS
    # ========================================================================

    def execute_buyer_matching(
        self, context: ReasoningContext, max_results: int = 10
    ) -> ReasoningResult:
        """
        Execute complete buyer matching workflow.

        Workflow:
        1. Validate context and technical specifications
        2. Run deterministic matching algorithm (matcher.py)
        3. Augment with AI insights (graph_service.py)
        4. Apply emotional intelligence scoring
        5. Generate recommendations and risk assessment
        6. Create audit trail
        7. Determine autonomous processing vs escalation

        Args:
            context: Complete reasoning context
            max_results: Maximum number of matches to return

        Returns:
            ReasoningResult with matches and metadata
        """
        self._lazy_init()
        start_time = datetime.now()

        try:
            _logger.info(
                f"Starting buyer matching for supplier intake {context.supplier_intake_id}, "
                f"polymer: {context.polymer_type}"
            )

            # Update stats
            self._stats["total_requests"] += 1

            # 1. Validate context
            validation_result = self._validate_context(context)
            if not validation_result["valid"]:
                return self._create_error_result(validation_result["error"], start_time)

            # 2. Run deterministic matching
            deterministic_matches = self._matcher.find_buyers(context)

            # 3. Augment with AI insights
            augmented_matches = self._graph_service.augment_matches(deterministic_matches, context)

            # 4. Apply emotional intelligence
            ei_matches = self._apply_emotional_intelligence(augmented_matches, context)

            # 5. Sort and limit results
            sorted_matches = sorted(ei_matches, key=lambda m: m.total_score, reverse=True)[
                :max_results
            ]

            # 6. Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(sorted_matches)

            # 7. Determine autonomous processing
            autonomous = overall_confidence >= context.confidence_threshold
            escalation_required = not autonomous
            escalation_reason = None

            if escalation_required:
                escalation_reason = self._determine_escalation_reason(
                    overall_confidence, sorted_matches, context
                )

            # 8. Gather insights
            market_insights = self._gather_market_insights(context)
            ei_insights = self._gather_ei_insights(context)
            governance = self._check_governance_compliance(context, sorted_matches)

            # 9. Create audit trail
            audit_trail_id = self._create_audit_trail(
                context, sorted_matches, overall_confidence, autonomous
            )

            # 10. Build result
            processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

            result = ReasoningResult(
                success=True,
                confidence=overall_confidence,
                matches=sorted_matches,
                autonomous_processing=autonomous,
                escalation_required=escalation_required,
                escalation_reason=escalation_reason,
                processing_time_ms=processing_time_ms,
                components_executed=[
                    "validation",
                    "deterministic_matching",
                    "ai_augmentation",
                    "emotional_intelligence",
                    "market_intelligence",
                    "governance_compliance",
                    "audit_trail",
                ],
                market_insights=market_insights,
                emotional_intelligence=ei_insights,
                governance_compliance=governance,
                audit_trail_id=audit_trail_id,
            )

            # Update stats
            if autonomous:
                self._stats["autonomous_processed"] += 1
            else:
                self._stats["escalated"] += 1

            self._stats["avg_confidence"] = (
                self._stats["avg_confidence"] * (self._stats["total_requests"] - 1)
                + overall_confidence
            ) / self._stats["total_requests"]

            self._stats["avg_processing_time_ms"] = (
                self._stats["avg_processing_time_ms"] * (self._stats["total_requests"] - 1)
                + processing_time_ms
            ) / self._stats["total_requests"]

            _logger.info(
                f"Buyer matching completed: {len(sorted_matches)} matches, "
                f"confidence: {overall_confidence:.3f}, "
                f"autonomous: {autonomous}, "
                f"time: {processing_time_ms:.2f}ms"
            )

            return result

        except Exception as e:
            _logger.error(f"Error in buyer matching execution: {e}", exc_info=True)
            return self._create_error_result(str(e), start_time)

    def execute_supplier_intake(
        self, raw_data: dict[str, Any], source_channel: str = "email"
    ) -> dict[str, Any]:
        """
        Execute supplier intake processing workflow.

        Workflow:
        1. Extract and normalize data from raw input
        2. Validate technical specifications
        3. Classify supplier tier
        4. Calculate confidence score
        5. Trigger buyer matching if confidence sufficient

        Args:
            raw_data: Raw supplier intake data
            source_channel: Source channel (email, web, whatsapp)

        Returns:
            Processing result with intake ID and status
        """
        self._lazy_init()

        try:
            _logger.info(f"Starting supplier intake from {source_channel}")

            # 1. Extract and normalize
            normalized = self._graph_service.extract_supplier_data(raw_data, source_channel)

            # 2. Create supplier intake record
            intake = self.env["plastic_ai.supplier_intake"].create(normalized)

            # 3. Validate technical specs
            validation = self._matcher.validate_technical_specs(
                normalized.get("polymer_type"),
                normalized.get("polymer_grade"),
                normalized.get("specifications", {}),
            )

            intake.write(
                {
                    "technical_validation": json.dumps(validation),
                    "confidence_score": validation.get("confidence", 0.0),
                }
            )

            # 4. Trigger matching if confidence sufficient
            if validation.get("confidence", 0.0) >= 0.6:
                context = ReasoningContext(
                    supplier_intake_id=intake.id,
                    supplier_partner_id=intake.supplier_id.id,
                    polymer_type=normalized.get("polymer_type"),
                    polymer_grade=normalized.get("polymer_grade"),
                    quantity_kg=normalized.get("quantity_kg"),
                    target_price=normalized.get("target_price"),
                    confidence_threshold=0.6,
                )

                match_result = self.execute_buyer_matching(context)

                # Store match results
                for match in match_result.matches[:5]:  # Top 5
                    self.env["plastic_ai.buyer_matching"].create(
                        {
                            "supplier_intake_id": intake.id,
                            "buyer_id": match.buyer_partner_id,
                            "total_score": match.total_score,
                            "confidence": match.confidence,
                            "match_details": json.dumps(match.to_dict()),
                        }
                    )

            return {
                "success": True,
                "intake_id": intake.id,
                "confidence": validation.get("confidence", 0.0),
                "autonomous": validation.get("confidence", 0.0) >= 0.6,
            }

        except Exception as e:
            _logger.error(f"Error in supplier intake: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
            }

    def get_performance_stats(self) -> dict[str, Any]:
        """
        Get current performance statistics.

        Returns:
            Dictionary with performance metrics
        """
        autonomous_rate = 0.0
        if self._stats["total_requests"] > 0:
            autonomous_rate = (
                self._stats["autonomous_processed"] / self._stats["total_requests"]
            ) * 100

        return {
            "total_requests": self._stats["total_requests"],
            "autonomous_processed": self._stats["autonomous_processed"],
            "escalated": self._stats["escalated"],
            "autonomous_rate_pct": round(autonomous_rate, 2),
            "avg_confidence": round(self._stats["avg_confidence"], 3),
            "avg_processing_time_ms": round(self._stats["avg_processing_time_ms"], 2),
            "target_autonomous_rate": 95.0,
            "target_match_accuracy": 90.0,
            "target_response_time_ms": 120000.0,  # 2 minutes
        }

    # ========================================================================
    # INTERNAL METHODS - VALIDATION
    # ========================================================================

    def _validate_context(self, context: ReasoningContext) -> dict[str, Any]:
        """Validate reasoning context has required fields."""

        required_fields = [
            "polymer_type",
            "quantity_kg",
        ]

        missing = []
        for field in required_fields:
            if getattr(context, field, None) is None:
                missing.append(field)

        if missing:
            return {"valid": False, "error": f"Missing required fields: {', '.join(missing)}"}

        return {"valid": True}

    # ========================================================================
    # INTERNAL METHODS - EMOTIONAL INTELLIGENCE
    # ========================================================================

    def _apply_emotional_intelligence(
        self, matches: list[MatchResult], context: ReasoningContext
    ) -> list[MatchResult]:
        """
        Apply emotional intelligence scoring to matches.

        Enhances matches with:
        - Empathy scoring based on relationship history
        - Charisma modeling (presence, warmth, confidence)
        - Trust scoring with cultural modifiers
        - Communication tone recommendations
        """
        if not context.use_emotional_intelligence:
            return matches

        for match in matches:
            # Get partner relationship data
            partner = self.env["res.partner"].browse(match.buyer_partner_id)

            # Calculate empathy score
            empathy_score = self._calculate_empathy_score(partner, context)

            # Calculate charisma dimensions
            charisma = self._calculate_charisma(partner, context)

            # Enhance trust score with EI factors
            ei_trust_boost = (empathy_score + charisma["overall"]) / 2 * 0.15
            match.trust_score = min(1.0, match.trust_score + ei_trust_boost)

            # Recalculate total score with enhanced trust
            match.total_score = (
                match.technical_score * 0.60
                + match.business_score * 0.25
                + match.trust_score * 0.15
            )

            # Add EI recommendations
            if empathy_score > 0.7:
                match.recommendations.append(
                    "High empathy alignment - personalized communication recommended"
                )

            if charisma["warmth"] < 0.5:
                match.recommendations.append("Build warmth through relationship-focused messaging")

        return matches

    def _calculate_empathy_score(self, partner, context: ReasoningContext) -> float:
        """Calculate empathy score based on relationship history."""

        # Factors:
        # - Response rate to previous communications
        # - Transaction success history
        # - Communication complexity handled
        # - Cultural context alignment

        base_score = 0.5

        # Check communication history
        messages = self.env["mail.message"].search(
            [
                ("partner_ids", "in", [partner.id]),
                ("message_type", "=", "email"),
            ],
            limit=20,
        )

        if messages:
            # Higher empathy for responsive partners
            response_rate = len(messages) / 20.0
            base_score += response_rate * 0.2

        # Check transaction history
        transactions = self.env["sm.tx"].search(
            [
                ("buyer_id", "=", partner.id),
                ("state", "in", ["closed", "completed"]),
            ],
            limit=10,
        )

        if transactions:
            success_rate = len(transactions) / 10.0
            base_score += success_rate * 0.3

        return min(1.0, base_score)

    def _calculate_charisma(self, partner, context: ReasoningContext) -> dict[str, float]:
        """Calculate charisma dimensions."""

        # Presence: engagement level, responsiveness
        presence = self._calculate_presence(partner)

        # Warmth: relationship quality, communication tone
        warmth = self._calculate_warmth(partner)

        # Confidence: transaction success, negotiation outcomes
        confidence = self._calculate_confidence(partner)

        # Adaptability: flexibility in past negotiations
        adaptability = self._calculate_adaptability(partner)

        overall = (presence + warmth + confidence + adaptability) / 4.0

        return {
            "presence": presence,
            "warmth": warmth,
            "confidence": confidence,
            "adaptability": adaptability,
            "overall": overall,
        }

    def _calculate_presence(self, partner) -> float:
        """Calculate presence dimension (0.0-1.0)."""
        # Based on responsiveness and engagement
        return 0.7  # Placeholder - implement based on actual metrics

    def _calculate_warmth(self, partner) -> float:
        """Calculate warmth dimension (0.0-1.0)."""
        # Based on relationship quality
        return 0.6  # Placeholder - implement based on actual metrics

    def _calculate_confidence(self, partner) -> float:
        """Calculate confidence dimension (0.0-1.0)."""
        # Based on transaction success
        return 0.8  # Placeholder - implement based on actual metrics

    def _calculate_adaptability(self, partner) -> float:
        """Calculate adaptability dimension (0.0-1.0)."""
        # Based on negotiation flexibility
        return 0.7  # Placeholder - implement based on actual metrics

    # ========================================================================
    # INTERNAL METHODS - INSIGHTS AND COMPLIANCE
    # ========================================================================

    def _gather_market_insights(self, context: ReasoningContext) -> dict[str, Any]:
        """Gather market intelligence insights."""

        if not context.use_market_intelligence:
            return {}

        # Get current market pricing
        polymer_prices = self._get_polymer_market_prices(context.polymer_type)

        # Get demand trends
        demand_forecast = self._forecast_demand(context.polymer_type)

        return {
            "current_price_range": polymer_prices,
            "demand_forecast_30d": demand_forecast,
            "market_timing_recommendation": self._get_timing_recommendation(
                polymer_prices, demand_forecast
            ),
        }

    def _gather_ei_insights(self, context: ReasoningContext) -> dict[str, Any]:
        """Gather emotional intelligence insights."""

        if not context.use_emotional_intelligence:
            return {}

        return {
            "cultural_context": context.cultural_context or "neutral",
            "recommended_tone": "professional_warm",
            "communication_timing": "business_hours",
            "relationship_focus": "trust_building",
        }

    def _check_governance_compliance(
        self, context: ReasoningContext, matches: list[MatchResult]
    ) -> dict[str, Any]:
        """Check governance compliance."""

        compliance_issues = []

        # Check for bias in matching
        if len(matches) > 0:
            top_score = matches[0].total_score
            avg_score = sum(m.total_score for m in matches) / len(matches)

            if top_score - avg_score > 0.4:
                compliance_issues.append(
                    "Significant score gap detected - review for potential bias"
                )

        # Check for fair distribution
        # Ensure matches include diverse suppliers when applicable

        return {
            "compliant": len(compliance_issues) == 0,
            "issues": compliance_issues,
            "framework": "FAIR",  # Fairness, Accountability, Interpretability, Responsibility
            "audit_retention_years": 7,
        }

    # ========================================================================
    # INTERNAL METHODS - CONFIDENCE AND ESCALATION
    # ========================================================================

    def _calculate_overall_confidence(self, matches: list[MatchResult]) -> float:
        """Calculate overall confidence from match results."""

        if not matches:
            return 0.0

        # Weight by match confidence and score
        weighted_sum = sum(m.confidence * m.total_score for m in matches)

        total_weight = sum(m.total_score for m in matches)

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def _determine_escalation_reason(
        self, confidence: float, matches: list[MatchResult], context: ReasoningContext
    ) -> str:
        """Determine reason for escalation."""

        reasons = []

        if confidence < context.confidence_threshold:
            reasons.append(
                f"Confidence {confidence:.2f} below threshold {context.confidence_threshold}"
            )

        if not matches:
            reasons.append("No suitable matches found")

        # Check for high-value transactions
        if context.quantity_kg and context.target_price:
            value = context.quantity_kg * context.target_price
            if value > 100000:  # $100k threshold
                reasons.append(f"High-value transaction: ${value:,.2f}")

        # Check for technical conflicts
        for match in matches:
            if not match.contamination_acceptable:
                reasons.append("Contamination specification conflicts detected")
                break

        return "; ".join(reasons) if reasons else "Manual review required"

    # ========================================================================
    # INTERNAL METHODS - MARKET INTELLIGENCE (PLACEHOLDER)
    # ========================================================================

    def _get_polymer_market_prices(self, polymer_type: str) -> dict[str, float]:
        """Get current market prices for polymer type."""
        # Placeholder - integrate with real market data API
        return {
            "min": 0.80,
            "max": 1.20,
            "avg": 1.00,
            "currency": "USD",
        }

    def _forecast_demand(self, polymer_type: str) -> dict[str, Any]:
        """Forecast demand for next 30 days."""
        # Placeholder - integrate with forecasting model
        return {
            "trend": "increasing",
            "confidence": 0.75,
            "volume_change_pct": 5.2,
        }

    def _get_timing_recommendation(self, prices: dict[str, float], forecast: dict[str, Any]) -> str:
        """Get market timing recommendation."""
        # Placeholder - implement timing logic
        if forecast["trend"] == "increasing":
            return "Favorable timing - demand increasing"
        return "Neutral timing"

    # ========================================================================
    # INTERNAL METHODS - AUDIT TRAIL
    # ========================================================================

    def _create_audit_trail(
        self,
        context: ReasoningContext,
        matches: list[MatchResult],
        confidence: float,
        autonomous: bool,
    ) -> int:
        """Create governance audit trail record."""

        audit = self.env["plastic_ai.audit_trail"].create(
            {
                "timestamp": datetime.now(),
                "operation_type": "buyer_matching",
                "supplier_intake_id": context.supplier_intake_id,
                "confidence_score": confidence,
                "autonomous_processing": autonomous,
                "num_matches": len(matches),
                "context_data": json.dumps(
                    {
                        "polymer_type": context.polymer_type,
                        "quantity_kg": context.quantity_kg,
                        "target_price": context.target_price,
                    }
                ),
                "results_data": json.dumps([m.to_dict() for m in matches[:5]]),
            }
        )

        return audit.id

    # ========================================================================
    # INTERNAL METHODS - ERROR HANDLING
    # ========================================================================

    def _create_error_result(self, error_message: str, start_time: datetime) -> ReasoningResult:
        """Create error result."""

        processing_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        return ReasoningResult(
            success=False,
            confidence=0.0,
            matches=[],
            escalation_required=True,
            escalation_reason=f"Error: {error_message}",
            processing_time_ms=processing_time_ms,
            reasoning_trace=[f"ERROR: {error_message}"],
        )


# ============================================================================
# MODULE INITIALIZATION
# ============================================================================


def get_reasoning_engine(env):
    """
    Factory function to get reasoning engine instance.

    Args:
        env: Odoo environment

    Returns:
        Initialized MackReasoningEngine instance
    """
    return MackReasoningEngine(env)
