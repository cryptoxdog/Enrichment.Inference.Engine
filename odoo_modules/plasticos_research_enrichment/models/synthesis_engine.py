import statistics
from collections import defaultdict


class SynthesisEngine:
    """Weighted synthesis across multiple enrichment payloads.

    Aggregates signals by cross-source agreement × average confidence.
    Only signals with weighted score >= 0.6 are included in the final output.
    """

    SIGNAL_FIELDS = [
        "industry_tags",
        "material_indicators",
        "contamination_flags",
        "compliance_signals",
    ]
    THRESHOLD = 0.6

    @staticmethod
    def synthesize(valid_payloads: list) -> dict:
        signal_counter: dict = defaultdict(list)

        for payload in valid_payloads:
            confidence = payload["confidence"]
            for key in SynthesisEngine.SIGNAL_FIELDS:
                for value in payload[key]:
                    signal_counter[(key, value)].append(confidence)

        final_signals: dict = {}
        weighted_scores: list = []
        total = len(valid_payloads)

        for (field, value), confidences in signal_counter.items():
            agreement = len(confidences) / total
            avg_conf = statistics.mean(confidences)
            weighted = agreement * avg_conf

            if weighted >= SynthesisEngine.THRESHOLD:
                final_signals.setdefault(field, []).append(value)
                weighted_scores.append(weighted)

        final_confidence = statistics.mean(weighted_scores) if weighted_scores else 0.0

        return {
            "signals": final_signals,
            "confidence": final_confidence,
        }
