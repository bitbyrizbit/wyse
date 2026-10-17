# MCP Interface

WYSE exposes its engine to agents as an MCP server over stdio.

## Identity

The server is started for one actor. Tenant, agent id, and role come from environment variables:

| Variable | Meaning |
|---|---|
| WYSE_TENANT | The shared memory the agent belongs to |
| WYSE_AGENT | The agent's id, lowercase letters and digits |
| WYSE_ROLE | `agent` or `operator` |

No tool accepts a tenant, an agent id, or a trust tier.

## Authority

- Agents declare sources as `agent`, `tool`, or `web`. `system` and `user` are operator-only.
- Agents write to a private scratch scope and publish through `promote`. Promotion caps source tiers at TOOL.
- Changing shared memory directly, including retraction and quarantine, needs the operator role. Agents may retract their own private claims.
- Decisions may only cite claims the gateway would release.

## Tools

| Tool | Purpose |
|---|---|
| remember | Store an observation and the claim it supports |
| recall | Read through the gateway: usable, contested, withheld |
| explain_belief | Proof tree behind a claim |
| inspect_impact | Preview the effect of a withdrawal |
| retract | Withdraw a claim and report the cascade |
| quarantine | Block a source and report the cascade |
| record_decision | Freeze a decision against usable claims |
| reassess | Compare a decision with present evidence |
| as_of | Recorded context of a decision |
| promote | Publish private claims with their proofs |
| handoff | Send a provenance-carrying context package |
| open_handoff | Open a handoff and see drift |

## Running it

```
python -m wyse.mcp_server
```

Host configuration, for example for a desktop agent client:

```json
{
  "mcpServers": {
    "wyse": {
      "command": "C:\\path\\to\\wyse\\.venv\\Scripts\\python.exe",
      "args": ["-m", "wyse.mcp_server"],
      "env": {
        "WYSE_TENANT": "demo",
        "WYSE_AGENT": "alice",
        "WYSE_ROLE": "agent"
      }
    }
  }
}
```

FalkorDB must be running. `scripts/mcp_smoke.py` exercises the server over the real protocol.

## Known limits

- An agent-declared source kind is a claim and not a proof. A real deployment binds kinds to registered connectors. Promotion caps the tier regardless.
- Identity is trusted from the server environment. Authentication belongs to the host that launches the server.
