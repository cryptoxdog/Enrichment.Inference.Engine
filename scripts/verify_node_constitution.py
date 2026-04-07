#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION_PATH = REPO_ROOT / "docs/contracts/node.constitution.yaml"
PACKET_PROTOCOL_PATH = REPO_ROOT / "docs/contracts/agents/protocols/packet-envelope.yaml"
MCP_INDEX_PATH = REPO_ROOT / "docs/contracts/agents/tool-schemas/_index.yaml"
ASYNCAPI_PATH = REPO_ROOT / "docs/contracts/events/asyncapi.yaml"
DEPENDENCY_INDEX_PATH = REPO_ROOT / "docs/contracts/dependencies/_index.yaml"
ATTESTATION_SCHEMA_PATH = REPO_ROOT / "docs/contracts/runtime-attestation.schema.json"


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []

    constitution = _load_yaml(CONSTITUTION_PATH)
    packet_protocol = _load_yaml(PACKET_PROTOCOL_PATH)
    mcp_index = _load_yaml(MCP_INDEX_PATH)
    asyncapi = _load_yaml(ASYNCAPI_PATH)
    dependency_index = _load_yaml(DEPENDENCY_INDEX_PATH)
    attestation_schema = _load_json(ATTESTATION_SCHEMA_PATH)

    for relative_path in constitution["node"]["tracked_contracts"]:
        if not (REPO_ROOT / relative_path).exists():
            errors.append(f"tracked contract missing: {relative_path}")

    constitution_actions = set(constitution["actions"].keys())
    packet_actions = {item["action"] for item in packet_protocol["registered_handlers"]}
    if constitution_actions != packet_actions:
        errors.append(
            f"action inventory mismatch: constitution={sorted(constitution_actions)} "
            f"packet={sorted(packet_actions)}"
        )

    constitution_tools = set(constitution["tools"].keys())
    mcp_tools = {item["name"] for item in mcp_index["tools"]}
    if constitution_tools != mcp_tools:
        errors.append(
            f"tool inventory mismatch: constitution={sorted(constitution_tools)} "
            f"mcp={sorted(mcp_tools)}"
        )

    constitution_events = set(constitution["events"].keys())
    asyncapi_events = {message["name"] for message in asyncapi["components"]["messages"].values()}
    if constitution_events != asyncapi_events:
        errors.append(
            f"event inventory mismatch: constitution={sorted(constitution_events)} "
            f"asyncapi={sorted(asyncapi_events)}"
        )

    constitution_dependencies = set(constitution["dependencies"].keys())
    dependency_names = {item["name"] for item in dependency_index["dependencies"]}
    if not constitution_dependencies.issubset(dependency_names):
        missing = sorted(constitution_dependencies - dependency_names)
        errors.append(f"constitution dependencies missing from dependency index: {missing}")

    writeback_action = constitution["actions"].get("writeback", {})
    if writeback_action.get("mutation_class") != "external_mutation":
        errors.append("writeback action must be external_mutation")
    if writeback_action.get("approval_mode") != "threshold_or_human":
        errors.append("writeback action must require threshold_or_human approval")

    writeback_tool = constitution["tools"].get("writeback", {})
    if writeback_tool.get("chassis_action") != "writeback":
        errors.append("writeback tool must map to writeback chassis action")

    required_fields = set(constitution["runtime_attestation"]["required_fields"])
    schema_required = set(attestation_schema["required"])
    if required_fields != schema_required:
        errors.append(
            f"runtime attestation required fields mismatch: constitution={sorted(required_fields)} "
            f"schema={sorted(schema_required)}"
        )

    if errors:
        for error in errors:
            print(f"[constitution-verify] {error}")
        return 1

    print("[constitution-verify] node constitution aligned with current contract pack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
