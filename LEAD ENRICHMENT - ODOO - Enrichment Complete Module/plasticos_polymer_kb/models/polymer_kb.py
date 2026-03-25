# -*- coding: utf-8 -*-
"""Master polymer knowledge-base record.

One record per polymer type (PP, HDPE, ...).  Owns all sub-records via
One2many relations.  Provides ``load_from_yaml()`` for import and
``action_sync_to_graph()`` for Neo4j push.
"""
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PlasticosPolymerKB(models.Model):
    _name = "plasticos.polymer.kb"
    _description = "Polymer Knowledge Base"
    _rec_name = "display_name"
    _order = "polymer_type"

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    polymer_type = fields.Char(
        required=True, index=True,
        help="Short code: PP, HDPE, LDPE, PET ...",
    )
    polymer_id = fields.Many2one(
        "plasticos.polymer", string="Polymer Registry",
        help="Link to plasticos.polymer master record.",
    )
    full_name = fields.Char()
    resin_id_code = fields.Integer(string="Resin ID Code")
    polymer_family = fields.Char()
    structure = fields.Text()
    version = fields.Char()
    last_updated = fields.Date()
    data_quality = fields.Selection(
        [("verified", "Verified"), ("unverified", "Unverified")],
        default="unverified",
    )
    source_tier = fields.Char()
    note = fields.Text()
    yaml_content = fields.Text("Raw YAML")

    display_name = fields.Char(compute="_compute_display_name", store=True)
    active = fields.Boolean(default=True)

    # Sub-records
    grade_ids = fields.One2many(
        "plasticos.polymer.kb.grade", "kb_id", string="Material Grades",
    )
    tier_ids = fields.One2many(
        "plasticos.polymer.kb.tier", "kb_id", string="Quality Tiers",
    )
    rule_ids = fields.One2many(
        "plasticos.polymer.kb.rule", "kb_id", string="Recycling Rules",
    )
    buyer_profile_ids = fields.One2many(
        "plasticos.polymer.kb.buyer.profile", "kb_id",
        string="KB Buyer Profiles",
    )
    inference_rule_ids = fields.One2many(
        "plasticos.polymer.kb.inference.rule", "kb_id",
        string="Inference Rules",
    )
    contamination_profile_ids = fields.One2many(
        "plasticos.polymer.kb.contamination.profile", "kb_id",
        string="Contamination Profiles",
    )
    product_mapping_ids = fields.One2many(
        "plasticos.polymer.kb.product.mapping", "kb_id",
        string="Product-Scrap Mappings",
    )

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends("polymer_type", "version")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = (
                f"{rec.polymer_type or '?'} KB v{rec.version or '0'}"
            )

    # ------------------------------------------------------------------
    # YAML Import
    # ------------------------------------------------------------------
    def action_reload_yaml(self):
        """Re-parse ``yaml_content`` field and refresh sub-records."""
        self.ensure_one()
        if not self.yaml_content:
            raise UserError("No YAML content to parse.")
        try:
            import yaml
        except ImportError:
            raise UserError("PyYAML is not installed. Run: pip install pyyaml")
        data = yaml.safe_load(self.yaml_content)
        self._sync_metadata(data.get("metadata", {}))
        self._sync_grades(data.get("material_grades", []))
        self._sync_tiers(data.get("source_quality_tiers", {}))
        self._sync_rules(data.get("recycling_rules", []))
        self._sync_contamination_profiles(data.get("contamination_profiles", []))
        self._sync_buyer_profiles(data.get("buyer_profiles", []))
        self._sync_inference_rules(data.get("inference_rules", []))
        self._sync_product_mappings(data.get("product_scrap_mapping", {}))
        _logger.info("KB %s reloaded from YAML", self.polymer_type)

    @api.model
    def load_from_yaml(self, yaml_text):
        """Parse raw YAML text, create-or-update KB + sub-records."""
        try:
            import yaml
        except ImportError:
            raise UserError("PyYAML not installed.")
        data = yaml.safe_load(yaml_text)
        meta = data.get("metadata", {})
        ptype = meta.get("polymer_type")
        if not ptype:
            raise UserError("YAML metadata must contain polymer_type.")
        kb = self.search([("polymer_type", "=", ptype)], limit=1)
        vals = {
            "polymer_type": ptype,
            "version": meta.get("version"),
            "data_quality": meta.get("data_quality", "unverified"),
            "yaml_content": yaml_text,
        }
        if kb:
            kb.write(vals)
        else:
            kb = self.create(vals)
        kb._sync_metadata(meta)
        kb._sync_grades(data.get("material_grades", []))
        kb._sync_tiers(data.get("source_quality_tiers", {}))
        kb._sync_rules(data.get("recycling_rules", []))
        kb._sync_contamination_profiles(data.get("contamination_profiles", []))
        kb._sync_buyer_profiles(data.get("buyer_profiles", []))
        kb._sync_inference_rules(data.get("inference_rules", []))
        kb._sync_product_mappings(data.get("product_scrap_mapping", {}))
        return kb

    # ------------------------------------------------------------------
    # Private sync helpers
    # ------------------------------------------------------------------
    def _sync_metadata(self, meta):
        self.write({
            "full_name": meta.get("full_name", ""),
            "resin_id_code": meta.get("resin_id_code", 0),
            "polymer_family": meta.get("polymer_family", ""),
            "structure": meta.get("structure", ""),
            "source_tier": meta.get("source_tier", ""),
            "note": meta.get("note", ""),
            "last_updated": meta.get("last_updated") or False,
        })

    def _sync_grades(self, grades_list):
        Grade = self.env["plasticos.polymer.kb.grade"]
        Grade.search([("kb_id", "=", self.id)]).unlink()
        for g in grades_list:
            mfr = g.get("melt_flow_rate") or g.get("melt_index") or {}
            dens = g.get("density") or {}
            mech = g.get("mechanical_properties") or {}
            therm = g.get("thermal_properties") or {}
            pcr = g.get("pcr_compatibility") or {}
            mi_min, mi_max = self._extract_range(mfr)
            d_min, d_max = self._extract_range(dens, key="value_g_cm3")
            Grade.create({
                "kb_id": self.id,
                "grade_id": g.get("grade_id", ""),
                "grade_name": g.get("grade_name", ""),
                "description": g.get("description", ""),
                "grade_type": g.get("type", "virgin"),
                "polymer_structure": g.get("polymer_structure", ""),
                "mi_min": mi_min,
                "mi_max": mi_max,
                "density_min": d_min,
                "density_max": d_max,
                "tensile_strength_min": (
                    mech.get("tensile_strength_mpa", [None])[0]
                    if isinstance(mech.get("tensile_strength_mpa"), list)
                    else mech.get("tensile_strength_mpa")
                ) or 0.0,
                "impact_strength_min": (
                    mech.get("impact_strength_j_m", [None])[0]
                    if isinstance(mech.get("impact_strength_j_m"), list)
                    else mech.get("impact_strength_j_m")
                ) or 0.0,
                "processing_temp_min": (
                    therm.get("processing_temp_c", [None])[0]
                    if isinstance(therm.get("processing_temp_c"), list)
                    else therm.get("processing_temp_c")
                ) or 0.0,
                "processing_temp_max": (
                    therm.get("processing_temp_c", [None, None])[-1]
                    if isinstance(therm.get("processing_temp_c"), list)
                    else therm.get("processing_temp_c")
                ) or 0.0,
                "max_pcr_pct": pcr.get("max_pcr_pct", 0.0) or 0.0,
            })

    def _sync_tiers(self, tiers_dict):
        Tier = self.env["plasticos.polymer.kb.tier"]
        Tier.search([("kb_id", "=", self.id)]).unlink()
        for key, t in tiers_dict.items():
            Tier.create({
                "kb_id": self.id,
                "tier_key": key,
                "definition": t.get("definition", ""),
                "contamination_max_pct": t.get("contamination_max_pct", 0),
                "cross_polymer_contam_max_pct": (
                    t.get("pp_contamination_max_pct")
                    or t.get("pe_contamination_max_pct")
                    or 0.0
                ),
                "moisture_max_pct": t.get("moisture_max_pct", 0),
                "moisture_max_ppm": t.get("moisture_max_ppm", 0),
                "ash_max_pct": t.get("ash_max_pct", 0),
                "property_retention_min_pct": t.get("property_retention_min_pct", 0),
                "sorting_purity_min_pct": t.get("sorting_purity_min_pct", 0),
                "processing_history": t.get("processing_history", ""),
                "mi_change_max_pct": (
                    t.get("mi_change_max_pct")
                    or t.get("mfr_increase_max_pct")
                    or 0.0
                ),
            })

    def _sync_rules(self, rules_list):
        Rule = self.env["plasticos.polymer.kb.rule"]
        Rule.search([("kb_id", "=", self.id)]).unlink()
        for r in rules_list:
            Rule.create({
                "kb_id": self.id,
                "rule_id": r.get("rule_id", ""),
                "material_type": r.get("material_type", ""),
                "rule_text": r.get("rule", ""),
                "reasoning": r.get("reasoning", ""),
                "confidence": r.get("confidence", 0.0),
                "safety_critical": r.get("safety_critical", False),
                "action": r.get("action", ""),
                "threshold_value": (
                    r.get("pvc_contamination_max_ppm")
                    or r.get("pp_contamination_max_pct")
                    or r.get("pe_contamination_max_pct")
                    or r.get("moisture_max_ppm")
                    or 0.0
                ),
                "threshold_unit": (
                    "ppm" if r.get("pvc_contamination_max_ppm")
                    or r.get("moisture_max_ppm")
                    else "pct"
                ),
            })

    def _sync_contamination_profiles(self, profiles_list):
        CP = self.env["plasticos.polymer.kb.contamination.profile"]
        CP.search([("kb_id", "=", self.id)]).unlink()
        for p in profiles_list:
            CP.create({
                "kb_id": self.id,
                "profile_id": p.get("profile_id", ""),
                "source": p.get("source", ""),
                "contamination_level": p.get("contamination_level", ""),
                "quality_tier": p.get("quality_tier", 0),
                "sorting_purity_pct": p.get("sorting_purity_pct", 0),
                "typical_contaminants": "\n".join(
                    p.get("typical_contaminants", [])
                ),
                "suitable_applications": "\n".join(
                    p.get("suitable_applications", [])
                ),
            })

    def _sync_buyer_profiles(self, profiles_list):
        BP = self.env["plasticos.polymer.kb.buyer.profile"]
        BP.search([("kb_id", "=", self.id)]).unlink()
        for bp in profiles_list:
            reqs = bp.get("material_requirements", {})
            specs = bp.get("quality_specifications", {})
            mi_range = specs.get("mi_range_g_10min") or specs.get("mfi_range_g_10min")
            mi_min = mi_range[0] if isinstance(mi_range, list) else 0.0
            mi_max = mi_range[-1] if isinstance(mi_range, list) else 0.0
            vol = bp.get("volume_range_tons_month", [0, 0])
            tiers = reqs.get("quality_tier_required", [])
            BP.create({
                "kb_id": self.id,
                "buyer_id": bp.get("buyer_id", ""),
                "buyer_type": bp.get("buyer_type", ""),
                "industry_segment": bp.get("industry_segment", ""),
                "polymer_types": ",".join(reqs.get("polymer_types", [])),
                "purity_min_pct": reqs.get("purity_min_pct", 0),
                "max_pcr_pct": reqs.get("max_pcr_pct", 0),
                "quality_tiers_required": ",".join(str(t) for t in tiers),
                "cross_polymer_contam_max_pct": (
                    reqs.get("pp_contamination_max_pct")
                    or reqs.get("pe_contamination_max_pct")
                    or 0.0
                ),
                "pvc_contamination_max_ppm": reqs.get("pvc_contamination_max_ppm", 0),
                "color_preference": reqs.get("color_preference", ""),
                "form_preference": reqs.get("form_preference", ""),
                "mi_min": mi_min or 0.0,
                "mi_max": mi_max or 0.0,
                "contamination_max_pct": specs.get("contamination_max_pct", 0),
                "density_min": specs.get("density_min_g_cm3", 0),
                "volume_min_tons": vol[0] if isinstance(vol, list) else 0,
                "volume_max_tons": vol[-1] if isinstance(vol, list) else 0,
                "applications": "\n".join(bp.get("applications", [])),
                "certifications_required": "\n".join(
                    bp.get("certifications_required")
                    or reqs.get("certifications_required", [])
                    or specs.get("certifications_required", [])
                    or []
                ),
            })

    def _sync_inference_rules(self, rules_list):
        IR = self.env["plasticos.polymer.kb.inference.rule"]
        IR.search([("kb_id", "=", self.id)]).unlink()
        for r in rules_list:
            IR.create({
                "kb_id": self.id,
                "rule_id": r.get("rule_id", ""),
                "inference_type": r.get("inference_type", ""),
                "logic": r.get("logic", ""),
                "reasoning": r.get("reasoning", ""),
                "confidence": r.get("confidence", 0.0),
            })

    def _sync_product_mappings(self, mapping_dict):
        PM = self.env["plasticos.polymer.kb.product.mapping"]
        PM.search([("kb_id", "=", self.id)]).unlink()
        for category, items in mapping_dict.items():
            if not isinstance(items, list):
                continue
            for item in items:
                tiers = item.get("scrap_quality_tier", [])
                contam = item.get("typical_contamination_pct", [0, 0])
                PM.create({
                    "kb_id": self.id,
                    "category": category,
                    "product": item.get("product", ""),
                    "scrap_grade": item.get("scrap_grade", ""),
                    "quality_tier_min": tiers[0] if tiers else 0,
                    "quality_tier_max": tiers[-1] if tiers else 0,
                    "contamination_min_pct": (
                        contam[0] if isinstance(contam, list) else 0
                    ),
                    "contamination_max_pct": (
                        contam[-1] if isinstance(contam, list) else 0
                    ),
                    "typical_contaminants": "\n".join(
                        item.get("typical_contaminants", [])
                    ),
                    "suitable_buyers": ",".join(
                        item.get("suitable_buyers", [])
                    ),
                    "reverse_reasoning": item.get("reverse_reasoning", ""),
                    "note": item.get("note", ""),
                })

    # ------------------------------------------------------------------
    # Neo4j sync
    # ------------------------------------------------------------------
    def action_sync_to_graph(self):
        """Push KB buyer profiles + grade nodes to Neo4j."""
        self.ensure_one()
        graph = self.env["plasticos.graph.service"]
        try:
            from ..services.kb_graph_sync import sync_kb_to_graph
            sync_kb_to_graph(graph, self)
        except Exception as e:
            raise UserError(f"Neo4j KB sync failed: {e}")

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_range(d, key=None):
        """Return (min, max) from a dict that may have list values."""
        if key and key in d:
            val = d[key]
            if isinstance(val, list) and len(val) >= 2:
                return float(val[0]), float(val[-1])
        for v in d.values():
            if isinstance(v, list) and len(v) >= 2:
                try:
                    return float(v[0]), float(v[-1])
                except (ValueError, TypeError):
                    continue
        return 0.0, 0.0
