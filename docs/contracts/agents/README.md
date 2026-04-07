# Agent Contracts

> MCP tools, protocols, and prompt contracts for the Enrichment Inference Engine.

## Overview

The EIE exposes AI agent capabilities through two channels:

1. **MCP Server** (`app/agents/mcp_server.py`) — Model Context Protocol tools for Odoo AI assistants and any MCP-compatible agent runtime.
2. **Chassis Protocol** (`chassis/envelope.py`) — L9 PacketEnvelope for constellation node-to-node calls.

## Contracts Index

| Contract | Type | Source | Description |
|----------|------|--------|-------------|
| `enrich_contact` | MCP Tool | `app/agents/mcp_server.py:35` | Waterfall entity enrichment |
| `lead_router` | MCP Tool | `app/agents/mcp_server.py:46` | Lead routing via scores |
| `deal_risk` | MCP Tool | `app/agents/mcp_server.py:55` | Opportunity risk assessment |
| `data_hygiene` | MCP Tool | `app/agents/mcp_server.py:64` | CRM data quality assessment |
| `writeback` | MCP Tool | `app/agents/mcp_server.py:73` | CRM enrichment writeback |
| `L9PacketEnvelope` | Protocol | `chassis/envelope.py` | Node-to-node wire format |
| `enrichment_prompt` | Prompt | `app/services/prompt_builder.py` | Dynamic enrichment prompt |
| `meta_prompt` | Prompt | `app/engines/meta_prompt_planner.py` | Per-pass meta-prompt |

## MCP Protocol Usage

```python
# Initialize MCP server
server = MCPServer(chassis_dispatch=my_dispatch_fn)

# List available tools
result = server.handle_request("tools/list")

# Call a tool
result = server.handle_request("tools/call", {
    "name": "enrich_contact",
    "arguments": {
        "domain": "company",
        "entity_name": "Acme Plastics",
        "quality_threshold": 0.70
    }
})
```

## Chassis Protocol Usage

```bash
curl -X POST http://localhost:8000/v1/execute \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "enrich",
    "payload": {
      "entity": {"name": "Acme Plastics"},
      "object_type": "Account",
      "objective": "Enrich polymer grade and tonnage"
    },
    "tenant": "acme-corp",
    "source_node": "score-engine"
  }'
```

