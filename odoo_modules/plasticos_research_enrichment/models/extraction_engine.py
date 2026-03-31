from .signal_schema import REQUIRED_KEYS


class ExtractionEngine:
    """Validate enrichment payloads against the strict signal schema."""

    @staticmethod
    def validate(payload) -> bool:
        if not isinstance(payload, dict):
            return False
        for key, expected_type in REQUIRED_KEYS.items():
            if key not in payload:
                return False
            if not isinstance(payload[key], expected_type):
                return False
        return True
