# Setup: from nothing to a working herdr-mcp

This walks through a fresh machine to an MCP client that can see and drive
Herdr. Every step ends with a check; do not move on until it passes.

Pick a path after step 3:

* **A. stdio** – the MCP client starts herdr-mcp itself. Recommended. No network.
* **B. HTTP on the host** – one long-running server, clients connect over
  loopback.
* **C. HTTP in Docker** – for an assistant that runs in a container on the same
  Linux host.

---

## 1. Install and start Herdr

Install Herdr 0.9.1 or newer ([docs](https://herdr.dev/docs/install/)) and start
it once so the server and its API socket exist:

```bash
herdr            # starts or attaches the server; leave it running
```

**Check** (from any terminal):

```bash
herdr --version                 # 0.9.1 or newer
herdr workspace list            # JSON with "result", not "server_not_running"
command -v herdr                # note this absolute path, you may need it later
```

## 2. Check Python

```bash
python3 --version               # 3.9 or newer; nothing else to install
```

## 3. Get herdr-mcp

Either as a Herdr plugin (pin a release so you know what code you run):

```bash
herdr plugin install thomasfossum/herdr-mcp --ref v0.3.0
herdr plugin list --json        # note "plugin_root": that is the checkout
```

or as a plain checkout:

```bash
git clone https://github.com/thomasfossum/herdr-mcp.git
cd herdr-mcp && git checkout v0.3.0
```

Below, `HERDR_MCP_DIR` is that directory (the plugin root or your clone):

```bash
export HERDR_MCP_DIR=/absolute/path/to/herdr-mcp
```

**Check** — the server can reach your live session:

```bash
python3 "$HERDR_MCP_DIR/bin/check.py"
# {"plugin": "herdr.mcp", ..., "tools": <count>, "ok": true, "counts": {...}}
# ("tools" is the size of your policy: fewer with HERDR_MCP_READ_ONLY or
#  HERDR_MCP_DISABLE_TOOLS)
```

If you installed it as a plugin, the same check runs through Herdr:

```bash
herdr plugin action invoke herdr.mcp.check
herdr plugin log list --plugin herdr.mcp     # "status": "succeeded"
```

`"ok": false` with `herdr binary not found` means `herdr` is not on `PATH`: set
`HERDR_MCP_HERDR=/absolute/path/to/herdr`. `server_not_running` means step 1 is
not done.

## 4. Decide your policy

Write these down now; you will put them in the client config (A), your shell
(B) or `docker/.env` (C). Start strict and loosen later. Full list in the
[README](../README.md#configuration).

| Variable | Suggested start | Why |
|---|---|---|
| `HERDR_MCP_DEFAULT_KIND` | the agent you use, e.g. `claude` | `herdr_open_agent` / `herdr_job_start` need a kind; there is no built-in default. |
| `HERDR_MCP_AGENT_KINDS` | same list, e.g. `claude,codex` | Only these agents can be started. |
| `HERDR_MCP_CWD_ALLOW` | your projects root, e.g. `/home/you/src` | New tabs, workspaces and worktrees stay inside it. |
| `HERDR_MCP_READ_ONLY` | `1` for the first session | Only status/list/read/wait tools. Remove it when you trust the setup. |
| `HERDR_MCP_DISABLE_TOOLS` | `herdr_pane_run` | Keep raw shell execution off unless you need it. |

Leave `HERDR_MCP_ALLOW_AGENT_ARGS` unset (see [SECURITY.md](../SECURITY.md)).

---

## A. stdio (recommended)

The client spawns `bin/herdr-mcp` and talks JSON-RPC over its stdin/stdout.

**Check the binary by hand first:**

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}' \
  '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"herdr_status","arguments":{}}}' \
  | "$HERDR_MCP_DIR/bin/herdr-mcp" --stdio
# The initialize result includes "instructions". The tools/call result has
# "isError": false and your agents. Two responses, one line each.
```

`notifications/initialized` is part of the legacy (pre-2026-07-28) handshake and
many strict clients require it. Modern clients instead call `server/discover`
and carry the protocol version in each request's `_meta`. This server is
dual-era: it answers both. See [Protocol versions](#protocol-versions).


### Claude Code

```bash
claude mcp add --scope user \
  -e HERDR_MCP_DEFAULT_KIND=claude \
  -e HERDR_MCP_CWD_ALLOW="$HOME/src" \
  herdr -- "$HERDR_MCP_DIR/bin/herdr-mcp" --stdio
claude mcp list                 # herdr: ... ✓ Connected
```

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or
`~/.config/Claude/claude_desktop_config.json` (Linux):

```json
{
  "mcpServers": {
    "herdr": {
      "command": "/absolute/path/to/herdr-mcp/bin/herdr-mcp",
      "args": ["--stdio"],
      "env": {
        "HERDR_MCP_HERDR": "/opt/homebrew/bin/herdr",
        "HERDR_MCP_DEFAULT_KIND": "claude",
        "HERDR_MCP_CWD_ALLOW": "/Users/you/src"
      }
    }
  }
}
```

GUI apps do not inherit your shell `PATH`, so set `HERDR_MCP_HERDR` to the
output of `command -v herdr`.

### opencode

`~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "herdr": {
      "type": "local",
      "enabled": true,
      "command": ["/absolute/path/to/herdr-mcp/bin/herdr-mcp", "--stdio"],
      "environment": {
        "HERDR_MCP_DEFAULT_KIND": "opencode",
        "HERDR_MCP_CWD_ALLOW": "/home/you/src"
      }
    }
  }
}
```

Any other client: command `…/bin/herdr-mcp`, argument `--stdio`, environment as
above.

**Check (opencode):** restart opencode — it loads MCP servers at startup — then
ask *"use herdr_status to show my agents"*. The counts must match `check.py`.
If the tools do not appear, run opencode with MCP debug logging and confirm the
`command` path is absolute and `python3` is on `PATH`.

**Check:** restart the client and ask *"use herdr_status to show my agents"*.
You should see the same counts as `check.py`.

---

## B. HTTP on the host

```bash
umask 077
mkdir -p ~/.config/herdr-mcp
openssl rand -hex 32 > ~/.config/herdr-mcp/token

HERDR_MCP_TOKEN_FILE=~/.config/herdr-mcp/token \
HERDR_MCP_DEFAULT_KIND=claude \
HERDR_MCP_CWD_ALLOW="$HOME/src" \
  "$HERDR_MCP_DIR/bin/herdr-mcp" --http --bind 127.0.0.1:8765
# herdr-mcp: streamable HTTP listening on http://127.0.0.1:8765/mcp
```

The server refuses to start without a token. Run it under your service manager
(systemd user unit, launchd agent, or a Herdr pane) as the same user as Herdr.

**Check** from another terminal:

```bash
TOKEN=$(cat ~/.config/herdr-mcp/token)
curl -s http://127.0.0.1:8765/mcp \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"herdr_status","arguments":{}}}'
# {"jsonrpc": "2.0", "id": 1, "result": {... "isError": false ...}}

curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/mcp \
  -H 'Content-Type: application/json' -d '{}'
# 401  (no token)
```

Connect a client, e.g. Claude Code:

```bash
claude mcp add --transport http \
  --header "Authorization: Bearer $TOKEN" \
  herdr http://127.0.0.1:8765/mcp
```

If a browser-based client must connect, add its exact origin to
`HERDR_MCP_ALLOWED_ORIGINS` (e.g. `http://localhost:5173`); every other
browser origin gets 403.

---

## C. HTTP in Docker (Linux hosts)

The container does not bundle Herdr. It bind-mounts the host's `herdr` binary
(so it always matches the running server) and the directory that holds
`herdr.sock`, and runs as the socket's owner because the socket is mode `0600`.
Docker Desktop on macOS/Windows cannot do this; use A or B there.

```bash
cd "$HERDR_MCP_DIR"
cp docker/.env.example docker/.env
$EDITOR docker/.env
```

Fill in:

| Key | How to find it |
|---|---|
| `HERDR_UID` / `HERDR_GID` | `id -u` / `id -g` as the user running Herdr |
| `HERDR_SOCKET_DIR` | the directory containing `herdr.sock`, usually `~/.config/herdr` (inside a Herdr pane: `dirname "$HERDR_SOCKET_PATH"`) |
| `HERDR_BINARY` | `command -v herdr` (must be a Linux build) |
| `HERDR_MCP_HOST_PORT` | loopback port on the host, default `8765` |

Plus the policy values from step 4. Then:

```bash
(umask 077; openssl rand -hex 32 > docker/herdr-mcp-token)
docker compose -f docker/compose.yml up -d --build
docker compose -f docker/compose.yml logs herdr-mcp
# herdr-mcp: streamable HTTP listening on http://0.0.0.0:8000/mcp
```

**Check** with the curl commands from B, using port `HERDR_MCP_HOST_PORT` and
the token in `docker/herdr-mcp-token`.

To serve an assistant in another compose project, attach both to a shared
network and point the assistant at `http://herdr-mcp:8000/mcp` with the bearer
token. Remove the `ports:` entry if nothing on the host needs it.

Troubleshooting:

* `server_not_running … /run/herdr/herdr.sock` – `HERDR_SOCKET_DIR` is wrong, or
  Herdr is not running.
* `Permission denied` on the socket – `HERDR_UID`/`HERDR_GID` do not own it
  (`ls -ln "$HERDR_SOCKET_DIR/herdr.sock"`).
* `exec format error` – `HERDR_BINARY` is not a Linux build for this CPU.
* `Read-only file system` from herdr – the socket directory is mounted `:ro`;
  if your Herdr version needs to write there, drop `:ro` in `docker/compose.yml`
  and accept that the container can then edit Herdr's `config.toml`.

---

## 5. First real run

With `HERDR_MCP_READ_ONLY` removed, ask your client:

> Open a new tab in `~/src/some-repo`, start a claude agent there and ask it to
> list the files.

That maps to `herdr_open_agent`. You should see a new tab appear in Herdr, and
`~/.local/state/herdr-mcp/audit.jsonl` (or `HERDR_MCP_STATE_DIR`) gains one line
per tool call, with prompt text hashed.

Then read [SECURITY.md](../SECURITY.md) and tighten whatever you loosened.

---

## Protocol versions

The server speaks two MCP eras on the same transport:

* **Modern (2026-07-28+)** — stateless. No `initialize` handshake; every request
  carries the protocol version and client capabilities in `_meta`, and
  `server/discover` advertises what the server supports. Every result carries
  `resultType` and the server's identity in `_meta`.
* **Legacy (2025-11-25 and earlier)** — the `initialize` / `notifications/initialized`
  handshake. Kept so existing clients keep working.

Supported versions: `2026-07-28`, `2025-11-25`, `2025-06-18`, `2025-03-26`,
`2024-11-05`. A modern request naming a version the server does not support gets
JSON-RPC `-32022` (Unsupported protocol version) with the supported list; an HTTP
request that sets an unsupported `MCP-Protocol-Version` header gets `400`.
Legacy clients have no fall-forward, so an unknown `initialize` version is
answered with the newest legacy revision.

Nothing to configure — the client picks the version it speaks.

