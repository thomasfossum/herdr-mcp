# Streamable HTTP client

`--http` refuses to start without a token.

```bash
umask 077
mkdir -p ~/.config/herdr-mcp
openssl rand -hex 32 > ~/.config/herdr-mcp/token

HERDR_MCP_TOKEN_FILE=~/.config/herdr-mcp/token \
HERDR_MCP_DEFAULT_KIND=claude \
HERDR_MCP_CWD_ALLOW="$HOME/src" \
  /absolute/path/to/herdr-mcp/bin/herdr-mcp --http --bind 127.0.0.1:8765
```

Smoke-test it:

```bash
TOKEN=$(cat ~/.config/herdr-mcp/token)
curl -s http://127.0.0.1:8765/mcp \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"herdr_status","arguments":{}}}'
```

Register it (Claude Code):

```bash
claude mcp add --transport http \
  --header "Authorization: Bearer $TOKEN" \
  herdr http://127.0.0.1:8765/mcp
```

Keep the bind on loopback or a private network; there is no TLS. A
browser-based client also needs its exact origin in `HERDR_MCP_ALLOWED_ORIGINS`.