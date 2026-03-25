# -*- coding: utf-8 -*-
"""
PlastOS Mack v7.0 Reasoning Engine - KB-Grounded Hybrid Architecture
=====================================================================

Combines deterministic KB-driven scoring with AI Agent augmentation:
- Hard gates (purity, contamination) enforced via KB buyer_profiles
- 10-dimension weighted scoring from v8.0 KB structure
- Inference rules evaluation from KB inference_rules section
- AI Agent fallback for borderline cases (0.5-0.8 confidence)

Author: PlastOS Dev Team
Version: 7.0.0
Date: 2026-02-23
"""

from odoo import models, fields, api
import yaml
import json
import logging
from datetime import datetime
from pathlib import Path

_logger = logging.getLogger(__name__)

# === SCORING CONFIGURATION ===
DIMENSION_WEIGHTS = {
    "purity": 0.15,
    "mfi": 0.15,
    "contamination": 0.15,
    "tensile": 0.10,
    "impact": 0.10,
    "pe_contamination": 0.10,
    "quality_tier": 0.10,
    "density": 0.05,
    "moisture": 0.05,
    "color": 0.05,
}

HARD_GATE_DIMENSIONS = {"purity", "contamination"}

TIER_BONUSES = {
    "tier1_premium": 1.15,
    "tier2_standard": 1.00,
    "tier3_economy": 0.90,
    "tier4_marginal": 0.75,
}

SOURCE_BONUS = 0.15  # Bonus for matching_priority: highest


class MackReasoningEngine(models.AbstractModel):
    """
    Mack v7.0 Modular Reasoning Engine with KB-grounded inference.
    
    Replaces hardcoded heuristics with actual YAML KB lookups for:
    - material_grades matching
    - source_quality_tiers classification
    - contamination_profiles validation
    - buyer_profiles 10-dimension scoring
    - inference_rules evaluation
    
    Maintains audit trail and supports AI Agent augmentation.
    """
    
    _name = "mack.reasoning.engine"
    _description = "Mack v7.0 KB-Grounded Reasoning Engine"

    # ============================================================================
    # MAIN ENTRY POINT
    # ============================================================================

    @api.model
    def run(self, context: dict):
        """
        Main reasoning engine entry point.
        
        Args:
            context (dict): Input data with keys:
                - agent: str - Agent type (intake|matching|offer|governance)
                - polymer: str - Polymer type (PP, HDPE, etc.)
                - [material properties] - purity_pct, contamination_pct, mfi, etc.
        
        Returns:
            dict: Reasoning result with status, confidence, insights, blocks
        """
        if not context:
            _logger.warning("Empty context provided to reasoning engine")
            return self._get_error_result("Empty context provided")
            
        try:
            # Load reasoning configuration
            config = self._load_reasoning_config()
            if not config:
                return self._get_error_result("Failed to load reasoning configuration")
            
            # Determine agent type
            agent_type = context.get("agent", "intake")
            if not agent_type:
                return self._get_error_result("No agent type specified")
            
            # Execute reasoning based on agent type
            reasoning_result = self._execute_reasoning(agent_type, context, config)
            
            # Validate result
            if not reasoning_result:
                return self._get_error_result(f"No result from {agent_type} reasoning")
            
            # Log reasoning trace
            self._log_reasoning_trace(agent_type, context, reasoning_result)
            
            return reasoning_result
            
        except Exception as e:
            _logger.error(f"Reasoning engine error: {str(e)}", exc_info=True)
            return self._get_error_result(str(e))

    # ============================================================================
    # CONFIGURATION & UTILITIES
    # ============================================================================

    def _get_error_result(self, error_msg):
        """Get standardized error result."""
        return {
            "status": "error",
            "confidence": 0.0,
            "error": error_msg,
            "mack_insights": [f"❌ Error: {error_msg}"]
        }
    
    def _load_reasoning_config(self):
        """Load reasoning configuration from KB or use defaults."""
        try:
            kb_config = self.env['plastic_ai.kb_config']
            config = kb_config.get_config('reasoning_config', as_dict=True)
            
            if not config:
                # Default configuration
                config = {
                    "active_agents": ["intake", "matching", "offer", "governance"],
                    "block_weights": {
                        "contamination_validation": 0.85,
                        "buyer_confidence": 0.80,
                        "offer_quality": 0.78,
                        "governance_escalation": 0.92
                    },
                    "learning_rate": 0.05,
                    "persona": "mack_sales",
                    "ai_augmentation_enabled": True,
                    "ai_augmentation_threshold_low": 0.5,
                    "ai_augmentation_threshold_high": 0.8,
                }
            
            return config
        except Exception as e:
            _logger.error(f"Failed to load reasoning config: {str(e)}")
            return None

    def _load_polymer_kb(self, polymer_type):
        """
        Load specific polymer KB from knowledge_base directory.
        
        Args:
            polymer_type (str): Polymer abbreviation (PP, HDPE, HIPS, etc.)
        
        Returns:
            dict: Parsed KB data with material_grades, buyer_profiles, etc.
        """
        try:
            kb_config = self.env['plastic_ai.kb_config']
            kb_name = f'plasticos_kb_{polymer_type.lower()}_v8.0'
            kb_data = kb_config.get_config(kb_name, as_dict=True)
            
            if not kb_data:
                _logger.warning(f"No KB found for polymer: {polymer_type}")
            
            return kb_data
        except Exception as e:
            _logger.error(f"Failed to load KB for {polymer_type}: {e}")
            return None

    # ============================================================================
    # AGENT DISPATCH
    # ============================================================================

    def _execute_reasoning(self, agent_type, context, config):
        """Execute reasoning based on agent type."""
        agent_map = {
            "intake": self._intake_reasoning,
            "matching": self._matching_reasoning,
            "offer": self._offer_reasoning,
            "governance": self._governance_reasoning,
        }
        
        reasoning_method = agent_map.get(agent_type, self._default_reasoning)
        result = reasoning_method(context, config)
        
        # AI augmentation for borderline cases
        if config.get("ai_augmentation_enabled", True):
            confidence = result.get("confidence", 0)
            low = config.get("ai_augmentation_threshold_low", 0.5)
            high = config.get("ai_augmentation_threshold_high", 0.8)
            
            if low <= confidence <= high:
                result = self._augment_with_ai(agent_type, context, result, config)
        
        return result

    # ============================================================================
    # INTAKE REASONING (KB-GROUNDED)
    # ============================================================================

    def _intake_reasoning(self, context, config):
        """
        KB-grounded supplier intake reasoning.
        
        Evaluates:
        - material_grades matching
        - source_quality_tiers classification
        - contamination_profiles validation
        - inference_rules evaluation
        
        Returns validated status, confidence, and insights.
        """
        polymer = (context.get("polymer") or "").upper()
        purity = context.get("purity_pct", 0)
        contamination = context.get("contamination_pct", 0)
        mfi = context.get("mfi", 0)
        source = context.get("source_type", "")
        qty = context.get("quantity_lbs", context.get("offtake_capacity_lbs_month", 0))
        region = context.get("region", "")

        insights = []
        confidence = 0.80

        # === LOAD KB DATA ===
        kb_data = self._load_polymer_kb(polymer)
        if not kb_data:
            return {
                "status": "review_required",
                "confidence": 0.3,
                "mack_insights": [
                    f"⚠️  No KB found for polymer '{polymer}' — manual review required"
                ],
                "reasoning_blocks": {"kb_loaded": False, "polymer": polymer}
            }

        insights.append(f"✅ KB loaded: {polymer}")

        # === GRADE MATCHING ===
        matched_grade = self._match_grade(mfi, purity, contamination, kb_data)
        if matched_grade:
            insights.append(f"✅ Material matches grade: {matched_grade}")
            confidence += 0.10
        else:
            insights.append("⚠️  No exact grade match — closest grade analysis needed")
            confidence -= 0.10

        # === TIER CLASSIFICATION ===
        assigned_tier = self._classify_tier(purity, contamination, kb_data)
        insights.append(f"✅ Quality tier: {assigned_tier}")

        # === CONTAMINATION PROFILE VALIDATION ===
        if source:
            contam_check = self._validate_contamination_profile(
                source, contamination, kb_data
            )
            insights.extend(contam_check["insights"])
            confidence += contam_check["confidence_delta"]

        # === QUANTITY ANALYSIS ===
        if qty:
            if qty >= 50000:
                insights.append(f"✅ Capacity: {qty:,.0f} lbs/month — High volume supplier")
                confidence += 0.05
            elif qty >= 10000:
                insights.append(f"✅ Capacity: {qty:,.0f} lbs/month — Medium volume supplier")
            else:
                insights.append(f"⚠️  Capacity: {qty:,.0f} lbs/month — Low volume supplier")
                confidence -= 0.05

        # === REGIONAL ANALYSIS ===
        if region:
            if region in ['NA', 'EU']:
                insights.append(f"✅ Region: {region} — Established market with good logistics")
                confidence += 0.05
            else:
                insights.append(f"⚠️  Region: {region} — Emerging market, verify logistics")

        # === INFERENCE RULES ===
        fired_rules = self._evaluate_inference_rules(kb_data, context)
        for rule in fired_rules:
            insights.append(f"🔍 Rule: {rule['message']}")
            confidence += rule.get("confidence_adjustment", 0)

        # Apply block weight
        weighted_confidence = confidence * config.get("block_weights", {}).get(
            "contamination_validation", 0.85
        )

        return {
            "status": "validated" if weighted_confidence > 0.7 else "review_required",
            "confidence": min(max(weighted_confidence, 0.0), 1.0),
            "mack_insights": insights,
            "matched_grade": matched_grade,
            "quality_tier": assigned_tier,
            "reasoning_blocks": {
                "kb_loaded": True,
                "polymer": polymer,
                "grade_match": matched_grade or "none",
                "tier": assigned_tier,
                "rules_fired": len(fired_rules),
            }
        }

    def _match_grade(self, mfi, purity, contamination, kb_data):
        """Match material properties against KB material_grades."""
        grades = kb_data.get("material_grades", {})
        
        for grade_id, grade_def in grades.items():
            props = grade_def.get("properties", {})
            
            if self._property_in_range(mfi, props.get("mfi_g_10min")) and \
               self._property_in_range(purity, props.get("purity_pct")) and \
               self._property_at_most(contamination, props.get("contamination_pct")):
                return grade_id
        
        return None

    def _classify_tier(self, purity, contamination, kb_data):
        """Classify into quality tier using KB source_quality_tiers."""
        tiers = kb_data.get("source_quality_tiers", {})
        
        for tier_name in ["tier1_premium", "tier2_standard", "tier3_economy", "tier4_marginal"]:
            tier_def = tiers.get(tier_name, {})
            purity_min = tier_def.get("purity_min", 0)
            contam_max = tier_def.get("contamination_max", 100)
            
            if purity >= purity_min and contamination <= contam_max:
                return tier_name
        
        return "tier4_marginal"

    def _validate_contamination_profile(self, source, contamination, kb_data):
        """Validate contamination against KB contamination_profiles."""
        contam_profiles = kb_data.get("contamination_profiles", {})
        source_profile = contam_profiles.get(source, {})
        
        insights = []
        confidence_delta = 0
        
        if source_profile:
            expected_contam_def = source_profile.get("typical_contamination_pct", {})
            expected_contam = expected_contam_def.get("typical", 0)
            
            if contamination > expected_contam * 1.5:
                insights.append(
                    f"⚠️  Contamination {contamination}% is 1.5x above typical for {source} "
                    f"source (expected ~{expected_contam}%)"
                )
                confidence_delta = -0.15
            else:
                insights.append(
                    f"✅ Contamination within expected range for {source} source"
                )
        
        return {"insights": insights, "confidence_delta": confidence_delta}

    # ============================================================================
    # MATCHING REASONING (KB-GROUNDED 10-DIMENSION SCORING)
    # ============================================================================

    def _matching_reasoning(self, context, config):
        """
        KB-grounded buyer matching using buyer_profiles.
        
        Implements 10-dimension weighted scoring:
        - Hard gates: purity, contamination
        - Soft scores: MFI, tensile, impact, PE contamination, density, moisture, color
        - Tier bonus: tier1=1.15x, tier4=0.75x
        - Source priority bonus: +0.15 if matching_priority: highest
        """
        polymer = (context.get("polymer") or "").upper()
        kb_data = self._load_polymer_kb(polymer)

        if not kb_data:
            return self._get_error_result(f"No KB found for {polymer}")

        buyer_profiles = kb_data.get("buyer_profiles", {})
        if not buyer_profiles:
            return {
                "matches": [],
                "confidence": 0.0,
                "mack_insights": [f"⚠️  No buyer profiles found in {polymer} KB"],
                "reasoning_blocks": {"kb_profiles_evaluated": 0}
            }

        material = {
            "mfi": context.get("mfi", 0),
            "purity_pct": context.get("purity_pct", 0),
            "contamination_pct": context.get("contamination_pct", 0),
            "tensile_mpa": context.get("tensile_mpa", 0),
            "impact_j_m": context.get("impact_j_m", 0),
            "pe_contamination_pct": context.get("pe_contamination_pct", 0),
            "density": context.get("density", 0),
            "moisture_ppm": context.get("moisture_ppm", 0),
            "color": context.get("color", "any"),
            "quality_tier": context.get("quality_tier", ""),
            "source_type": context.get("source_type", ""),
        }

        matches = []
        
        for bp_id, bp in buyer_profiles.items():
            score = 0.0
            failed_hard = False
            reasons = []

            # === HARD GATE: PURITY ===
            purity_min = bp.get("puritymin", 0)
            if material["purity_pct"] and purity_min:
                if material["purity_pct"] >= purity_min:
                    score += DIMENSION_WEIGHTS["purity"]
                else:
                    failed_hard = True
                    reasons.append(
                        f"HARD FAIL: purity {material['purity_pct']}% < {purity_min}% min"
                    )

            # === HARD GATE: CONTAMINATION ===
            contam_max = bp.get("contaminationmax", 100)
            if material["contamination_pct"] is not None and contam_max:
                if material["contamination_pct"] <= contam_max:
                    score += DIMENSION_WEIGHTS["contamination"]
                else:
                    failed_hard = True
                    reasons.append(
                        f"HARD FAIL: contamination {material['contamination_pct']}% > "
                        f"{contam_max}% max"
                    )

            if failed_hard:
                continue  # Skip this buyer entirely

            # === SOFT SCORE: MFI RANGE ===
            mfi_range = bp.get("mfirange", [])
            if material["mfi"] and isinstance(mfi_range, list) and len(mfi_range) == 2:
                if mfi_range[0] <= material["mfi"] <= mfi_range[1]:
                    score += DIMENSION_WEIGHTS["mfi"]
                    reasons.append(f"MFI {material['mfi']} in range {mfi_range}")

            # === SOFT SCORES: MECHANICAL PROPERTIES ===
            if material["tensile_mpa"] >= bp.get("tensilestrengthmin", 0):
                score += DIMENSION_WEIGHTS["tensile"]
            if material["impact_j_m"] >= bp.get("impactstrengthmin", 0):
                score += DIMENSION_WEIGHTS["impact"]
            if material["pe_contamination_pct"] <= bp.get("pecontaminationmax", 100):
                score += DIMENSION_WEIGHTS["pe_contamination"]
            if material["moisture_ppm"] <= bp.get("moisturemaxppm", 99999):
                score += DIMENSION_WEIGHTS["moisture"]

            # === SOFT SCORE: COLOR ===
            buyer_color = bp.get("color", "any")
            if buyer_color == "any" or material["color"] == "any":
                score += DIMENSION_WEIGHTS["color"]
            elif material["color"] == buyer_color:
                score += DIMENSION_WEIGHTS["color"]
            elif material["color"] == "mixed":
                score += DIMENSION_WEIGHTS["color"] * 0.5  # Penalty for mixed

            # === TIER BONUS ===
            tier = material.get("quality_tier", "")
            if tier in TIER_BONUSES:
                score *= TIER_BONUSES[tier]

            # === SOURCE PRIORITY BONUS ===
            matching_priority = bp.get("matching_priority", {})
            source = material.get("source_type", "").lower()
            if source and matching_priority.get(source) == "highest":
                score += SOURCE_BONUS
                reasons.append(f"Source bonus: {source} is highest priority")

            matches.append({
                "buyer_profile_id": bp_id,
                "name": bp.get("name", bp_id),
                "score": round(score, 3),
                "reasons": reasons,
            })

        # Sort by score descending
        matches.sort(key=lambda x: x["score"], reverse=True)

        confidence = matches[0]["score"] if matches else 0.0
        weighted_confidence = confidence * config.get("block_weights", {}).get(
            "buyer_confidence", 0.80
        )

        return {
            "matches": matches[:10],  # Top 10
            "confidence": min(weighted_confidence, 1.0),
            "mack_insights": [
                f"✅ {polymer}: {len(matches)} buyer profiles evaluated from KB",
                f"🏆 Top match: {matches[0]['buyer_profile_id']} "
                f"({matches[0]['score']:.0%})" if matches else "❌ No matches found"
            ],
            "reasoning_blocks": {
                "kb_profiles_evaluated": len(buyer_profiles),
                "matches_found": len(matches),
                "hard_gate_dimensions": list(HARD_GATE_DIMENSIONS),
                "top_score": matches[0]["score"] if matches else 0,
            }
        }

    # ============================================================================
    # OFFER & GOVERNANCE REASONING
    # ============================================================================

    def _offer_reasoning(self, context, config):
        """Offer generation reasoning logic."""
        buyer = context.get("buyer", "Unnamed Buyer")
        polymer = context.get("polymer", "Unknown")
        price = context.get("price", "TBD")
        quantity = context.get("quantity_lbs", 0)
        
        msg = f"Offer generated for {buyer}: {polymer}"
        if price != "TBD":
            msg += f" at ${price}/lb"
        if quantity:
            msg += f" ({quantity:,.0f} lbs)"
        msg += ". Includes quality assurance and compliance terms."
        
        confidence = config.get("block_weights", {}).get("offer_quality", 0.78)
        
        if price != "TBD":
            confidence += 0.1
        if quantity > 0:
            confidence += 0.05
        
        return {
            "status": "offer_ready",
            "confidence": min(confidence, 1.0),
            "message": msg,
            "mack_insights": [f"✅ Offer structured for {buyer} with market-competitive terms"],
            "reasoning_blocks": {
                "pricing_complete": price != "TBD",
                "quantity_specified": quantity > 0,
                "buyer_identified": buyer != "Unnamed Buyer"
            }
        }
    
    def _governance_reasoning(self, context, config):
        """Governance audit reasoning logic."""
        confidence = context.get("confidence", 0)
        escalation_threshold = config.get("block_weights", {}).get(
            "governance_escalation", 0.92
        )
        
        if confidence < 0.6:
            verdict = "escalate"
            note = "Confidence below threshold; requires human review"
        elif confidence < escalation_threshold:
            verdict = "flag"
            note = "Moderate confidence; monitor for quality"
        else:
            verdict = "approved"
            note = "Within compliance parameters"
        
        return {
            "status": verdict,
            "confidence": confidence,
            "governance_note": note,
            "mack_insights": [f"🔍 Governance assessment: {verdict} — {note}"],
            "reasoning_blocks": {
                "threshold_check": confidence >= 0.6,
                "escalation_required": confidence < 0.6,
                "compliance_status": verdict
            }
        }
    
    def _default_reasoning(self, context, config):
        """Default reasoning for unknown agent types."""
        return {
            "status": "unknown_agent",
            "confidence": 0.5,
            "mack_insights": ["⚠️  Unknown agent type — using default reasoning"],
            "reasoning_blocks": {"agent_recognized": False, "fallback_used": True}
        }

    # ============================================================================
    # INFERENCE RULES ENGINE
    # ============================================================================

    def _evaluate_inference_rules(self, kb_data, material_context):
        """
        Evaluate KB inference_rules section against material data.
        
        Rules have format:
        {
          "rule_id": {
            "condition": {"field": {"min": X, "max": Y}, ...},
            "action": {"type": "flag", "message": "...", "confidence_adjustment": 0.1}
          }
        }
        """
        rules = kb_data.get("inference_rules", {})
        fired_rules = []

        for rule_id, rule_def in rules.items():
            condition = rule_def.get("condition", {})
            action = rule_def.get("action", {})

            if self._condition_matches(condition, material_context):
                fired_rules.append({
                    "rule_id": rule_id,
                    "action": action.get("type", "flag"),
                    "message": action.get("message", f"Rule {rule_id} triggered"),
                    "confidence_adjustment": action.get("confidence_adjustment", 0),
                })

        return fired_rules

    def _condition_matches(self, condition, context):
        """Check if a KB inference rule condition matches the context."""
        for field, check in condition.items():
            value = context.get(field)
            if value is None:
                continue
            
            if isinstance(check, dict):
                if "min" in check and value < check["min"]:
                    return False
                if "max" in check and value > check["max"]:
                    return False
                if "equals" in check and value != check["equals"]:
                    return False
                if "in" in check and value not in check["in"]:
                    return False
            elif value != check:
                return False
        
        return True

    # ============================================================================
    # AI AGENT AUGMENTATION
    # ============================================================================

    def _augment_with_ai(self, agent_type, context, deterministic_result, config):
        """
        Augment borderline results with Odoo 19 AI Agent reasoning.
        
        Triggered when confidence falls in [0.5, 0.8] range.
        AI Agent has RAG access to all 22 v8.0 KBs.
        """
        try:
            ai_agent = self.env['ai.agent'].search([
                ('name', 'ilike', 'PlastOS Material Intelligence')
            ], limit=1)

            if not ai_agent:
                _logger.warning("PlastOS AI Agent not found; skipping augmentation")
                return deterministic_result

            polymer = context.get("polymer", "")
            confidence = deterministic_result.get("confidence", 0)
            
            prompt = self._build_ai_prompt(agent_type, polymer, context, confidence)
            
            # Use Odoo 19's native AI agent execution
            ai_response = ai_agent._generate_response(prompt)

            deterministic_result["ai_augmented"] = True
            deterministic_result["ai_insight"] = ai_response
            deterministic_result["mack_insights"].append(
                f"🤖 AI Agent analysis: {ai_response[:250]}..."
            )
            
        except Exception as e:
            _logger.warning(f"AI Agent augmentation failed: {e}")
        
        return deterministic_result

    def _build_ai_prompt(self, agent_type, polymer, context, confidence):
        """Build prompt for AI Agent based on agent type."""
        if agent_type == "intake":
            return (
                f"Evaluate this borderline intake for {polymer}:\n"
                f"- Purity: {context.get('purity_pct')}%\n"
                f"- Contamination: {context.get('contamination_pct')}%\n"
                f"- MFI: {context.get('mfi')}\n"
                f"- Source: {context.get('source_type')}\n\n"
                f"The deterministic engine scored it {confidence:.0%}. "
                f"Should we accept, flag, or reject? "
                f"Cross-reference KB quality_indicators and inference_rules for {polymer}."
            )
        elif agent_type == "matching":
            return (
                f"Review buyer matching for {polymer} with confidence {confidence:.0%}:\n"
                f"Material: MFI {context.get('mfi')}, purity {context.get('purity_pct')}%, "
                f"contamination {context.get('contamination_pct')}%\n\n"
                f"Are there alternative buyers in related polymer KBs that could accept this? "
                f"Check cross-polymer substitution patterns."
            )
        else:
            return (
                f"Agent {agent_type} produced borderline result ({confidence:.0%}) "
                f"for {polymer}. Provide strategic guidance."
            )

    # ============================================================================
    # PROPERTY MATCHING UTILITIES
    # ============================================================================

    def _property_in_range(self, value, prop_def):
        """Check if value falls within KB property {value: [lo, hi]} range."""
        if not prop_def or not value:
            return True  # No constraint = pass
        
        val_range = prop_def.get("value", [])
        if isinstance(val_range, list) and len(val_range) == 2:
            return val_range[0] <= value <= val_range[1]
        
        return True

    def _property_at_most(self, value, prop_def):
        """Check if value is at most the KB max."""
        if not prop_def or value is None:
            return True
        
        val_range = prop_def.get("value", [])
        if isinstance(val_range, list) and len(val_range) >= 2:
            return value <= val_range[1]
        
        return True

    # ============================================================================
    # AUDIT LOGGING
    # ============================================================================

    def _log_reasoning_trace(self, agent_type, context, result):
        """Log reasoning trace to audit log."""
        try:
            self.env['plastic_ai.audit_log'].sudo().create({
                'event_type': 'AI_DECISION',
                'action_type': 'ai_decision',
                'agent_name': f'Mack Reasoning Engine v7.0 — {agent_type.title()}',
                'model_name': 'mack.reasoning.engine',
                'record_id': context.get('record_id', 0),
                'actor': 'Mack AI v7.0',
                'message': (
                    f"Reasoning executed: {agent_type} | "
                    f"Confidence: {result.get('confidence', 0):.2f} | "
                    f"Status: {result.get('status', 'unknown')}"
                ),
                'input_data': json.dumps(context, indent=2),
                'output_data': json.dumps(result, indent=2),
                'confidence_score': result.get('confidence', 0)
            })
        except Exception as e:
            _logger.warning(f"Failed to log reasoning trace: {str(e)}")
