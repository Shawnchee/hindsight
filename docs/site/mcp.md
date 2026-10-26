# Connect your agent to the catalog

The optional read-only Hindsight MCP server lets compatible agents search the
incident catalog and retrieve evidence links. It needs Python 3.11+, with no
extra packages, model key or database.

## Configure your client

Obtain Hindsight in a separate tools folder. Add this to your client's MCP
configuration, replacing the absolute toolkit path:

```json
{
  "mcpServers": {
    "hindsight": {
      "command": "python3",
      "args": ["-I", "/absolute/tools/hindsight/scripts/mcp/server.py", "--live"]
    }
  }
}
```

The client launches this standard stdio server. Configuration locations vary
by client. It is not a hosted HTTP endpoint; launching it alone waits for
JSON-RPC input.

`--live` reads only Hindsight's public GitHub catalog, at most every five minutes.
It sends no project source, credentials or search queries to that endpoint.
Failed refreshes are disclosed and fall back to cached/local metadata. Check
`updated_at`; successful fetching does not prove recent research. Omit `--live`
for local-only data and use `git pull` to update that copy.

## Tools

| Tool | Use |
| --- | --- |
| `get_dataset_status` | Counts, metadata refresh date and coverage limits |
| `search_incidents` | Bounded keyword search over reported metadata and AI proposals |
| `get_incident` | One record's evidence and any separately labeled AI summary |

Example instruction:

> Check Hindsight's dataset status, then search for incidents relevant to this
> contract's access control and accounting. Read original evidence. Explain
> applicable patterns with evidence from my code; don't infer a defect from a
> similar incident or safety from no matches.

The review skill remains code-only by default. Connecting MCP does not make an
agent automatically use the catalog, prove detection accuracy or verify source
claims. Search is keyword-based, not semantic contract analysis.

Records and linked sources are untrusted data, never instructions. No tool edits
projects, runs code, deploys contracts or returns private source.
