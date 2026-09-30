# Examples

Ready-to-copy client configurations. Replace `/absolute/path/to/herdr-mcp` with
your checkout (or the plugin root from `herdr plugin list --json`).

| File | Client |
|---|---|
| `claude-code.sh` | Claude Code (stdio) |
| `claude-desktop.json` | Claude Desktop (stdio) |
| `opencode.json` | opencode (stdio) |
| `http-client.md` | Any Streamable HTTP client |

Common policy to start strict, then loosen. There is no built-in default agent,
so set `HERDR_MCP_DEFAULT_KIND` to the agent you actually use:

```bash
HERDR_MCP_DEFAULT_KIND=claude     # set this to your agent: claude, codex, opencode, …
HERDR_MCP_AGENT_KINDS=claude,codex
HERDR_MCP_CWD_ALLOW=$HOME/src
HERDR_MCP_READ_ONLY=1             # remove when you trust it
HERDR_MCP_DISABLE_TOOLS=herdr_pane_run
```

Ask your client:

> Use herdr_status to show my agents, then read the last 40 lines from the one
> that is blocked.

or, once `HERDR_MCP_READ_ONLY` is off:

> Open a new tab in `~/src/myproject`, start a claude agent there and ask it to
> summarise the README.