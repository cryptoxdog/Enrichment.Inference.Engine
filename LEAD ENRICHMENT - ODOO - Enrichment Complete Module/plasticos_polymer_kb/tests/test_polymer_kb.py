"""Unit tests for plasticos_polymer_kb module."""

from odoo.tests.common import TransactionCase


class TestPolymerKB(TransactionCase):
    """Test YAML import, sub-record creation, and inference engine."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.KB = cls.env["plasticos.polymer.kb"]

    def _make_minimal_yaml(self, polymer_type="PP"):
        return f"""
metadata:
  polymer_type: "{polymer_type}"
  full_name: "Test {polymer_type}"
  version: "1.0-test"
  data_quality: "verified"
  resin_id_code: 5

material_grades:
  - grade_id: "TEST_GRADE_1"
    grade_name: "Test Injection Grade"
    type: "virgin"
    melt_flow_rate:
      injection_g_10min: [10, 30]
    density:
      value_g_cm3: [0.900, 0.910]
    pcr_compatibility:
      max_pcr_pct: 100

source_quality_tiers:
  tier_1_premium:
    definition: "Manufacturing PIR"
    contamination_max_pct: 0.5
  tier_2_standard:
    definition: "Post-industrial"
    contamination_max_pct: 3.0

recycling_rules:
  - rule_id: "TEST_PVC_ZERO_TOLERANCE"
    material_type: "{polymer_type}"
    rule: "PVC > 0.1% causes HCl"
    confidence: 0.98
    safety_critical: true
    pvc_contamination_max_ppm: 1000
    action: "reject_or_reroute_to_washing"

buyer_profiles:
  - buyer_id: "TEST_BUYER_1"
    buyer_type: "Test manufacturer"
    industry_segment: "Testing"
    material_requirements:
      polymer_types: ["{polymer_type}_homopolymer"]
      quality_tier_required: [1, 2]
      pp_contamination_max_pct: 3.0
    quality_specifications:
      mi_range_g_10min: [10, 30]
      contamination_max_pct: 3.0
    applications:
      - "Test application"

inference_rules:
  - rule_id: "TEST_FORWARD"
    inference_type: "buyer_matching"
    logic: "IF source=injection_pir THEN tier=1"
    confidence: 0.95

contamination_profiles:
  - profile_id: "TEST_PROFILE_1"
    source: "Test source"
    contamination_level: "minimal"
    quality_tier: 1
    sorting_purity_pct: 99.0
    typical_contaminants:
      - "Minimal"
    suitable_applications:
      - "All"

product_scrap_mapping:
  test_products:
    - product: "Test product"
      scrap_grade: "test_grade"
      scrap_quality_tier: [1, 2]
      typical_contamination_pct: [0.1, 0.5]
      suitable_buyers: ["test_buyer_1"]
"""

    def test_load_from_yaml_creates_kb(self):
        """YAML import creates master KB + all sub-records."""
        yaml_text = self._make_minimal_yaml("PP")
        kb = self.KB.load_from_yaml(yaml_text)
        self.assertEqual(kb.polymer_type, "PP")
        self.assertEqual(kb.data_quality, "verified")
        self.assertEqual(len(kb.grade_ids), 1)
        self.assertEqual(len(kb.tier_ids), 2)
        self.assertEqual(len(kb.rule_ids), 1)
        self.assertEqual(len(kb.buyer_profile_ids), 1)
        self.assertEqual(len(kb.inference_rule_ids), 1)
        self.assertEqual(len(kb.contamination_profile_ids), 1)
        self.assertEqual(len(kb.product_mapping_ids), 1)

    def test_grade_mfi_range_parsed(self):
        """Grade MFI min/max extracted from YAML list."""
        kb = self.KB.load_from_yaml(self._make_minimal_yaml())
        grade = kb.grade_ids[0]
        self.assertAlmostEqual(grade.mi_min, 10.0)
        self.assertAlmostEqual(grade.mi_max, 30.0)

    def test_safety_rule_flagged(self):
        """Safety-critical rules have safety_critical=True."""
        kb = self.KB.load_from_yaml(self._make_minimal_yaml())
        rule = kb.rule_ids[0]
        self.assertTrue(rule.safety_critical)
        self.assertEqual(rule.threshold_value, 1000.0)

    def test_reload_yaml_replaces_sub_records(self):
        """Reloading YAML replaces (not appends) sub-records."""
        yaml1 = self._make_minimal_yaml("HDPE")
        kb = self.KB.load_from_yaml(yaml1)
        self.assertEqual(len(kb.grade_ids), 1)
        # Reload same YAML -> still 1 grade, not 2
        kb.yaml_content = yaml1
        kb.action_reload_yaml()
        self.assertEqual(len(kb.grade_ids), 1)

    def test_upsert_same_polymer(self):
        """Loading YAML for same polymer_type updates, not duplicates."""
        yaml1 = self._make_minimal_yaml("PP")
        kb1 = self.KB.load_from_yaml(yaml1)
        kb2 = self.KB.load_from_yaml(yaml1)
        self.assertEqual(kb1.id, kb2.id)

    def test_inference_engine_quality_tier(self):
        """Inference engine correctly maps contamination to tier."""
        from odoo.addons.plasticos_polymer_kb.services.kb_inference import (
            KBInferenceEngine,
        )

        kb = self.KB.load_from_yaml(self._make_minimal_yaml())
        engine = KBInferenceEngine(self.env)
        self.assertEqual(engine.infer_quality_tier("PP", 0.3), 1)
        self.assertEqual(engine.infer_quality_tier("PP", 2.0), 2)
        self.assertEqual(engine.infer_quality_tier("PP", 10.0), 4)

    def test_inference_engine_no_kb(self):
        """Inference engine returns safe defaults when no KB loaded."""
        from odoo.addons.plasticos_polymer_kb.services.kb_inference import (
            KBInferenceEngine,
        )

        engine = KBInferenceEngine(self.env)
        self.assertEqual(engine.infer_quality_tier("NONEXISTENT", 5.0), 0)
        self.assertEqual(engine.infer_mfi_application("NONEXISTENT", 10.0), "")
