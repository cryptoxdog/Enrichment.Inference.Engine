// Deterministic PlasticOS test data
// Load with: cat tests/fixtures/plasticos_seed.cypher | cypher-shell -u neo4j -p test

CREATE CONSTRAINT facility_id_unique IF NOT EXISTS
FOR (f:Facility) REQUIRE f.id IS UNIQUE;

MERGE (f1:Facility {
  id:                   "facility-abc-001",
  name:                 "ABC Plastics Inc",
  city:                 "Charlotte",
  state:                "NC",
  polymer_types:        ["HDPE", "LDPE"],
  density_min:          0.92,
  density_max:          0.97,
  mfi_min:              2.0,
  mfi_max:              12.0,
  contamination_tolerance: 0.03,
  facility_tier:        "tier_1",
  material_grade:       "A"
});

MERGE (f2:Facility {
  id:                   "facility-beta-002",
  name:                 "Beta Regrind Co",
  city:                 "Atlanta",
  state:                "GA",
  polymer_types:        ["HDPE"],
  density_min:          0.93,
  density_max:          0.96,
  mfi_min:              5.0,
  mfi_max:              20.0,
  contamination_tolerance: 0.05,
  facility_tier:        "tier_2",
  material_grade:       "B"
});
