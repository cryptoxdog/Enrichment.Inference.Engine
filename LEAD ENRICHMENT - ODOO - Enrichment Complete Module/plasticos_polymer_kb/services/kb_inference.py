# -*- coding: utf-8 -*-
"""KB inference engine -- forward and backward reasoning for buyer matching.

Called between Stage 1 (Python hard gates) and Stage 2 (Cypher scoring)
to annotate each survivor with KB-inferred archetype compatibility.
"""
import logging
from typing import Optional

_logger = logging.getLogger(__name__)


class KBInferenceEngine:
    """Stateless service -- instantiate with ``env``, call methods."""

    def __init__(self, env):
        self.env = env
        self._kb_cache = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_kb(self, polymer_code: str):
        """Return the active KB record for a polymer code, cached."""
        if polymer_code not in self._kb_cache:
            KB = self.env["plasticos.polymer.kb"]
            kb = KB.search(
                [("polymer_type", "=ilike", polymer_code),
                 ("active", "=", True)],
                limit=1,
            )
            self._kb_cache[polymer_code] = kb or KB.browse()
        return self._kb_cache[polymer_code]

    def infer_quality_tier(self, polymer_code: str,
                           contamination_pct: float,
                           sorting_purity_pct: float = 0.0) -> int:
        """Infer scrap quality tier (1-4) from contamination data.

        Returns 0 if no KB or unable to determine.
        """
        kb = self.get_kb(polymer_code)
        if not kb or not kb.tier_ids:
            return 0
        tiers = kb.tier_ids.sorted("tier_key")
        for tier in tiers:
            if (tier.contamination_max_pct
                    and contamination_pct <= tier.contamination_max_pct):
                try:
                    return int(tier.tier_key.split("_")[1])
                except (IndexError, ValueError):
                    pass
        return 4

    def infer_suitable_buyer_archetypes(self, polymer_code: str,
                                         quality_tier: int,
                                         mfi: Optional[float] = None,
                                         process_type: Optional[str] = None):
        """Forward inference: material props -> matching KB buyer archetypes.

        Returns ``plasticos.polymer.kb.buyer.profile`` recordset.
        """
        kb = self.get_kb(polymer_code)
        if not kb:
            return self.env["plasticos.polymer.kb.buyer.profile"].browse()

        matches = self.env["plasticos.polymer.kb.buyer.profile"].browse()
        for bp in kb.buyer_profile_ids:
            required_tiers = set()
            if bp.quality_tiers_required:
                for t in bp.quality_tiers_required.split(","):
                    try:
                        required_tiers.add(int(t.strip()))
                    except ValueError:
                        pass
            if required_tiers and quality_tier not in required_tiers:
                if not required_tiers or quality_tier > max(required_tiers):
                    continue

            if mfi is not None and bp.mi_min and bp.mi_max:
                if mfi < bp.mi_min * 0.8 or mfi > bp.mi_max * 1.2:
                    continue

            matches |= bp

        return matches

    def infer_mfi_application(self, polymer_code: str,
                               mfi: Optional[float]) -> str:
        """Map MFI value to application category using KB grade defs.

        Returns a human-readable application string or empty.
        """
        if mfi is None:
            return ""
        kb = self.get_kb(polymer_code)
        if not kb:
            return ""
        for grade in kb.grade_ids:
            if grade.mi_min and grade.mi_max:
                if grade.mi_min <= mfi <= grade.mi_max:
                    return grade.grade_name or grade.grade_id
        return ""

    def get_safety_rules(self, polymer_code: str):
        """Return all safety-critical rules for a polymer."""
        kb = self.get_kb(polymer_code)
        if not kb:
            return self.env["plasticos.polymer.kb.rule"].browse()
        return kb.rule_ids.filtered(lambda r: r.safety_critical)

    def get_contamination_limits_by_application(
        self, polymer_code: str, application: str,
    ) -> dict:
        """Return cross-polymer contamination limits for an application."""
        kb = self.get_kb(polymer_code)
        if not kb:
            return {}
        for rule in kb.rule_ids:
            if "contamination_tolerance" in (rule.rule_id or "").lower():
                return {
                    "threshold": rule.threshold_value,
                    "unit": rule.threshold_unit,
                    "confidence": rule.confidence,
                }
        return {}
