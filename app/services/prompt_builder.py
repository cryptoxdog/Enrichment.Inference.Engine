"""
Dynamic per-entity prompt builder.

Audit fixes applied:
  - H13: Builds a REAL system prompt with schema definition, field types,
         output format example — not a one-liner.
  - H14: Passes ALL non-empty entity fields, not just name+country.
  - M10: Computes real schema hash from actual schema content.

Search intelligence integration:
  - Accepts optional SonarConfig for message_strategy-aware prompt construction
  - SYSTEM_USER_ASSISTANT strategy injects known fields as assistant context
    (primes the model with prior-pass knowledge for surgical targeting)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SYSTEM_TEMPLATE = """You are a domain research analyst. Your task is to research
the given entity and extract structured data matching the requested schema.

RULES:
1. Return ONLY valid JSON — no markdown fences, no commentary, no explanation.
2. Your response must be a JSON object with exactly two top-level keys:
   - "confidence": a float between 0.0 and 1.0 indicating your overall certainty
   - "fields": an object containing the requested field values
3. Base answers on verifiable, current facts. If uncertain, lower confidence.
4. For list fields, return arrays of non-empty strings.
5. For boolean fields, return true or false (not strings).
6. If you cannot determine a field value with any confidence, omit it from "fields".
7. Never fabricate data. Absence is better than hallucination.

EXAMPLE OUTPUT FORMAT:
{{"confidence": 0.82, "fields": {{"Industry": "Plastics Recycling", "employee_count": 150}}}}
{kb_context}
TARGET SCHEMA:
{schema_block}"""


def _build_assistant_context(entity: dict[str, Any]) -> str | None:
    """Build an assistant message summarizing known fields from prior passes.

    This primes the model with existing knowledge so targeted passes don't
    re-research what's already known — they focus on gaps.
    """
    non_null = {k: v for k, v in entity.items() if v is not None and v != "" and v != []}
    if not non_null:
        return None

    lines = ["I already have the following verified data for this entity:"]
    for key, value in sorted(non_null.items()):
        if key.startswith("_"):
            continue  # skip internal fields
        str_val = str(value)
        if len(str_val) > 300:
            str_val = str_val[:297] + "..."
        lines.append(f"  {key}: {str_val}")
    lines.append("\nFocus your research on the fields I'm still missing from the target schema.")
    return "\n".join(lines)


def build_prompt(
    entity: dict[str, Any],
    object_type: str,
    objective: str,
    target_schema: dict[str, str] | None = None,
    kb_context_text: str = "",
    model: str = "sonar-reasoning",
    sonar_config=None,
) -> dict:
    """Build a Perplexity chat completion payload tailored to this entity.

    Parameters
    ----------
    sonar_config : SonarConfig | None
        When provided, uses message_strategy to determine prompt structure.
        SYSTEM_USER_ASSISTANT injects known fields as an assistant turn.
    """

    # ── Schema block ─────────────────────────────────
    if target_schema:
        schema_lines = [f"  {k} ({v})" for k, v in target_schema.items()]
        schema_block = "\n".join(schema_lines)
    else:
        schema_block = "  (no schema specified — return any relevant structured data)"

    # ── KB context block ─────────────────────────────
    kb_block = ""
    if kb_context_text:
        kb_block = f"\n\nDOMAIN KNOWLEDGE CONTEXT:\n{kb_context_text}\n"

    system = SYSTEM_TEMPLATE.format(
        kb_context=kb_block,
        schema_block=schema_block,
    )

    # ── Entity description — ALL non-empty fields ────
    entity_lines = []
    for key, value in sorted(entity.items()):
        if value is None or value == "" or value == [] or value == {}:
            continue
        str_val = str(value)
        if len(str_val) > 500:
            str_val = str_val[:497] + "..."
        entity_lines.append(f"  {key}: {str_val}")

    entity_block = "\n".join(entity_lines) if entity_lines else "  (minimal data available)"

    user_content = (
        f"OBJECTIVE: {objective}\n\n"
        f"ENTITY TYPE: {object_type}\n\n"
        f"ENTITY DATA:\n{entity_block}\n\n"
        f"Research this entity thoroughly. Return strictly valid JSON."
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]

    # ── Message strategy: inject assistant context if applicable ──
    if sonar_config is not None:
        # Import here to avoid circular imports
        from ..engines.search_optimizer import MessageStrategy

        if sonar_config.message_strategy == MessageStrategy.SYSTEM_USER_ASSISTANT:
            assistant_ctx = _build_assistant_context(entity)
            if assistant_ctx:
                messages.append({"role": "assistant", "content": assistant_ctx})

    return {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 4000,
    }


def build_schema_hash(target_schema: dict[str, str] | None) -> str:
    """Deterministic hash of the target schema for caching/dedup."""
    schema_str = json.dumps(sorted((target_schema or {}).items()), sort_keys=True)
    return hashlib.sha256(schema_str.encode()).hexdigest()[:16]
