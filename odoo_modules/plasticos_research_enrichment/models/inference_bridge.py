class InferenceBridge:
    """Apply synthesis results to a partner record via the PlasticOS inference pipeline.

    Writes grade, tier, and confidence back to the partner record.
    """

    @staticmethod
    def apply(env, partner, synthesis: dict) -> None:
        feature_vector = {
            "industry_tags": synthesis["signals"].get("industry_tags", []),
            "material_indicators": synthesis["signals"].get("material_indicators", []),
            "contamination_flags": synthesis["signals"].get("contamination_flags", []),
            "compliance_signals": synthesis["signals"].get("compliance_signals", []),
            "confidence_score": synthesis["confidence"],
        }

        pipeline = env["plasticos.inference.engine"]
        result = pipeline.run(feature_vector)

        partner.write(
            {
                "x_material_grade": result.get("grade"),
                "x_material_tier": result.get("tier"),
                "x_enrichment_confidence": synthesis["confidence"],
            }
        )
