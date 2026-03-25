# -*- coding: utf-8 -*-
"""KB-aware hard gates for Stage 1 Python matcher.

Plug into ``PlasticosMatcher`` to apply polymer-specific safety rules
and contamination constraints that the generic gates miss.
"""
import logging

_logger = logging.getLogger(__name__)


class KBGate:
    """Evaluates KB-derived hard gates against an intake + facility pair.

    Usage in matcher.py::

        from odoo.addons.plasticos_polymer_kb.services.kb_gate import KBGate
        kb_gate = KBGate(self.env)

        for facility in survivors:
            passed, reason = kb_gate.evaluate(intake, facility, material)
            if not passed:
                gate_results[facility.id]["kb_gate"] = reason
                survivors -= facility
    """

    def __init__(self, env):
        self.env = env
        from .kb_inference import KBInferenceEngine
        self.inference = KBInferenceEngine(env)

    def evaluate(self, intake, facility, material) -> tuple:
        """Run all KB hard gates.

        Returns:
            (True, "passed") on success.
            (False, "reason string") on failure.
        """
        polymer_code = (
            material.polymer_id.code
            if material.polymer_id
            else getattr(material, "polymer", None) or ""
        )
        if not polymer_code:
            return True, "no_polymer_code"

        kb = self.inference.get_kb(polymer_code)
        if not kb:
            return True, "no_kb_loaded"

        # Gate A: Safety-critical rules
        passed, reason = self._check_safety_rules(kb, material, facility)
        if not passed:
            return False, reason

        # Gate B: Cross-polymer contamination routing
        passed, reason = self._check_cross_polymer_contamination(
            kb, material, facility,
        )
        if not passed:
            return False, reason

        # Gate C: Food/medical contact restrictions
        passed, reason = self._check_food_medical_restrictions(
            kb, material, facility,
        )
        if not passed:
            return False, reason

        return True, "kb_gates_passed"

    # ------------------------------------------------------------------
    # Private gate implementations
    # ------------------------------------------------------------------
    def _check_safety_rules(self, kb, material, facility) -> tuple:
        """Apply safety_critical=True rules as hard reject."""
        for rule in kb.rule_ids.filtered(lambda r: r.safety_critical):
            rule_id_lower = (rule.rule_id or "").lower()

            # PVC zero-tolerance gate (HDPE / PP)
            if "pvc" in rule_id_lower and "zero" in rule_id_lower:
                pvc_ppm = (
                    getattr(material, "pvc_contamination_ppm", 0)
                    or getattr(material, "pvc_ppm", 0)
                    or 0
                )
                has_pvc = getattr(material, "has_pvc", False)
                if has_pvc and rule.threshold_value:
                    if pvc_ppm > rule.threshold_value:
                        return (
                            False,
                            f"KB {rule.rule_id}: PVC {pvc_ppm} ppm > "
                            f"{rule.threshold_value} ppm threshold "
                            f"(confidence {rule.confidence})",
                        )
                    # Even if within threshold, flag food/medical buyers
                    if has_pvc and (
                        getattr(facility, "food_grade_certified", False)
                        or getattr(facility, "medical_grade_capable", False)
                    ):
                        return (
                            False,
                            f"KB {rule.rule_id}: PVC-contaminated material "
                            f"cannot go to food/medical buyer",
                        )

        return True, "safety_passed"

    def _check_cross_polymer_contamination(self, kb, material,
                                            facility) -> tuple:
        """Check cross-polymer contamination limits from KB tiers."""
        polymer_type = kb.polymer_type.upper()
        contam_pct = 0.0

        if polymer_type == "HDPE":
            contam_pct = (
                getattr(material, "pp_contamination_pct", 0)
                or getattr(material, "cross_polymer_pct", 0)
                or 0.0
            )
        elif polymer_type == "PP":
            contam_pct = (
                getattr(material, "pe_contamination_pct", 0)
                or getattr(material, "cross_polymer_pct", 0)
                or 0.0
            )

        if not contam_pct:
            return True, "no_cross_polymer_data"

        # Check if ALL buyer profile archetypes reject this level
        if kb.buyer_profile_ids:
            any_accepts = any(
                bp.cross_polymer_contam_max_pct
                and contam_pct <= bp.cross_polymer_contam_max_pct
                for bp in kb.buyer_profile_ids
            )
            if not any_accepts:
                max_limit = max(
                    (bp.cross_polymer_contam_max_pct
                     for bp in kb.buyer_profile_ids
                     if bp.cross_polymer_contam_max_pct),
                    default=0,
                )
                if max_limit and contam_pct > max_limit:
                    return (
                        False,
                        f"KB cross-polymer contamination {contam_pct}% "
                        f"exceeds all buyer archetype limits (max {max_limit}%)",
                    )

        return True, "cross_polymer_passed"

    def _check_food_medical_restrictions(self, kb, material,
                                          facility) -> tuple:
        """Enforce KB food-contact / medical PCR restrictions."""
        for rule in kb.rule_ids:
            rule_id_lower = (rule.rule_id or "").lower()

            if "food_contact_restriction" in rule_id_lower:
                is_food_scrap = getattr(material, "food_grade", False)
                buyer_is_food = getattr(facility, "food_grade_certified", False)
                if is_food_scrap and buyer_is_food:
                    source_type = getattr(material, "source_type", "") or ""
                    if "post" in source_type.lower():
                        return (
                            False,
                            f"KB {rule.rule_id}: post-consumer food-contact "
                            f"scrap cannot return to direct food-contact buyer "
                            f"(confidence {rule.confidence})",
                        )

        return True, "food_medical_passed"
