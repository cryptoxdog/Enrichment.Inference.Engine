class EntropyEngine:
    """Compute data entropy score for a partner record.

    Score 1–5: higher = more missing data = higher enrichment priority.
    """

    @staticmethod
    def compute(partner) -> int:
        missing = 0
        if not partner.industry_id:
            missing += 1
        if not partner.country_id:
            missing += 1
        if not getattr(partner, "material_profile_id", False):
            missing += 1

        age_factor = 1
        entropy = (missing * 0.4) + (age_factor * 0.2)

        score = max(1, min(5, round(entropy * 5)))
        return score
