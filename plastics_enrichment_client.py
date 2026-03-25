#!/usr/bin/env python3
"""
plastics_enrichment_client.py — Reference implementation for the Perplexity Super Prompt
Uses the YAML config to execute multi-pass facility enrichment via Perplexity Sonar Pro.
"""

import yaml
import json
import time
from typing import Optional
from dataclasses import dataclass
from perplexity import Perplexity  # pip install perplexity-sdk


@dataclass
class FacilityQuery:
    company_name: str
    city: str
    state: str
    additional_context: str = ""


def load_config(path: str = "plastics_recycling_super_prompt.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def build_pass_request(config: dict, pass_id: str, query: FacilityQuery) -> dict:
    """Construct a Perplexity API request from config + pass template + query."""
    api = config["api_config"]
    template = config["user_prompt_templates"][pass_id]
    guardrails = config["guardrails"]["inject_into_all_prompts"]

    # Variable substitution in input template
    user_input = template["input"].format(
        company_name=query.company_name,
        city=query.city,
        state=query.state,
        additional_context=query.additional_context,
    )

    # Merge API-level config with pass-level overrides
    domain_filter = template.get("api_overrides", {}).get(
        "search_domain_filter", api.get("search_domain_filters", {}).get(pass_id, [])
    )
    recency = template.get("api_overrides", {}).get(
        "search_recency_filter", api.get("search_recency_filter", "year")
    )
    context_size = template.get("api_overrides", {}).get(
        "search_context_size", api.get("search_context_size", "high")
    )

    return {
        "preset": "pro-search",
        "input": user_input,
        "instructions": config["system_prompt"] + "\n\n" + guardrails,
        "tools": [
            {
                "type": "web_search",
                "filters": {
                    "search_domain_filter": domain_filter[:20],  # API max 20
                    "search_recency_filter": recency,
                },
            }
        ],
        "response_format": api["response_format"],
        "temperature": api.get("temperature", 0.1),
        "max_tokens": api.get("max_tokens", 4096),
        "stream": True,
        "web_search_options": {
            "search_type": api.get("search_type", "pro"),
            "search_context_size": context_size,
        },
    }


def execute_pass(client: Perplexity, request: dict) -> dict:
    """Execute a single enrichment pass and parse JSON response."""
    response = client.responses.create(**request)

    # For streaming, accumulate content
    content = ""
    if hasattr(response, "__iter__"):
        for chunk in response:
            if hasattr(chunk, "choices") and chunk.choices[0].delta.content:
                content += chunk.choices[0].delta.content
    else:
        content = response.output_text

    # Strip any accidental markdown fences
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    content = content.strip()

    return json.loads(content)


def merge_results(base: dict, new: dict, strategy: str = "merge_non_null") -> dict:
    """Merge enrichment pass results according to configured strategy."""
    if strategy == "overwrite":
        base.update({k: v for k, v in new.items() if v is not None})
    elif strategy == "merge_arrays":
        for k, v in new.items():
            if isinstance(v, list) and isinstance(base.get(k), list):
                existing = {json.dumps(i, sort_keys=True) for i in base[k]}
                for item in v:
                    if json.dumps(item, sort_keys=True) not in existing:
                        base[k].append(item)
            elif v is not None:
                base[k] = v
    elif strategy == "merge_non_null":
        for k, v in new.items():
            if v is not None and (base.get(k) is None or base.get(k) == [] or base.get(k) == ""):
                base[k] = v
    elif strategy == "append_arrays":
        for k, v in new.items():
            if isinstance(v, list) and isinstance(base.get(k), list):
                base[k].extend(v)
            elif v is not None and base.get(k) is None:
                base[k] = v
    return base


def enrich_facility(
    query: FacilityQuery,
    config_path: str = "plastics_recycling_super_prompt.yaml",
    passes: Optional[list] = None,
) -> dict:
    """Full multi-pass enrichment pipeline for a single facility."""
    config = load_config(config_path)
    client = Perplexity()  # uses PERPLEXITY_API_KEY env var
    orch = config["orchestration"]

    if passes is None:
        passes = [p["pass_id"] for p in orch["pass_sequence"]]

    result = {}
    rate = orch.get("rate_limiting", {})

    for pass_config in orch["pass_sequence"]:
        pid = pass_config["pass_id"]
        if pid not in passes:
            continue

        print(f"  → Executing {pid}...")
        request = build_pass_request(config, pid, query)

        try:
            pass_result = execute_pass(client, request)
            strategy = pass_config.get("merge_strategy", "merge_non_null")
            result = merge_results(result, pass_result, strategy)
            print(f"    ✓ {pid} complete")
        except Exception as e:
            print(f"    ✗ {pid} failed: {e}")
            if pass_config.get("on_failure") == "abort":
                raise
            # continue_with_gaps — record the failure
            if "data_confidence" not in result:
                result["data_confidence"] = {}
            missing = result["data_confidence"].get("fields_missing", [])
            missing.append(f"[{pid}_failed: {str(e)[:100]}]")
            result["data_confidence"]["fields_missing"] = missing

        time.sleep(rate.get("delay_between_passes_ms", 1000) / 1000)

    return result


# ── Example Usage ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    facility = FacilityQuery(
        company_name="Star Plastics, Inc.",
        city="Ravenswood",
        state="WV",
        additional_context="Focus on their PCR pellet product lines.",
    )

    profile = enrich_facility(facility)
    print(json.dumps(profile, indent=2))
