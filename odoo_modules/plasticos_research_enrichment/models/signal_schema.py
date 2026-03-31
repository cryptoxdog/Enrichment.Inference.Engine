# Structured Signal Schema — Strict Contract
# All enrichment payloads must conform to this schema before synthesis.

REQUIRED_KEYS = {
    "industry_tags": list,
    "material_indicators": list,
    "contamination_flags": list,
    "compliance_signals": list,
    "confidence": (int, float),
}
