#!/usr/bin/env bash
# Register herdr-mcp with Claude Code over stdio.
set -euo pipefail
HERDR_MCP_DIR="${HERDR_MCP_DIR:?set HERDR_MCP_DIR to your herdr-mcp checkout}"
claude mcp add --scope user \
  -e HERDR_MCP_DEFAULT_KIND=claude \
  -e HERDR_MCP_CWD_ALLOW="$HOME/src" \
  herdr -- "$HERDR_MCP_DIR/bin/herdr-mcp" --stdio
claude mcp list