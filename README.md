# herdr-mcp

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![release](https://img.shields.io/github/v/release/thomasfossum/herdr-mcp)](https://github.com/thomasfossum/herdr-mcp/releases)
[![herdr plugin](https://img.shields.io/badge/herdr-plugin-blueviolet)](https://herdr.dev/plugins/)

**Control a running [Herdr](https://herdr.dev) session from any MCP client.** See
every agent's status, open tabs and panes, start coding agents, send them work,
and run worktree-isolated jobs — over stdio or Streamable HTTP.

Dependency-free: standard-library Python only, so it runs on the system
`python3` with nothing to install.

```text
"what are my agents doing?"     -> herdr_status
"open codex in a new tab"       -> herdr_open_agent
"start a job on branch X"       -> herdr_job_start
"what did the reviewer say?"    -> herdr_agent_read
```

> [!WARNING]
> Access to herdr-mcp is equivalent to a shell as the user running Herdr. Read
> [SECURITY.md](SECURITY.md) before exposing it to anything but your own local
> client.

## Quick start

Requirements: [Herdr](https://herdr.dev/docs/install/) 0.9.1+ with a running
server, and Python 3.9+.

From a clone (nothing to install — the self-test runs straight from the repo):

```bash
git clone https://github.com/thomasfossum/herdr-mcp.git
cd herdr-mcp
python3 bin/check.py                                 # read-only self-test
```

Or as a Herdr plugin (pin a release so you know what code you run):

```bash
herdr plugin install thomasfossum/herdr-mcp --ref v0.3.0
herdr plugin action invoke herdr.mcp.check          # read-only self-test
```

Then register it with your client (Claude Code shown; others below). Use the
absolute path of the checkout or, for a plugin, `plugin_root` from
`herdr plugin list --json`:

```bash
claude mcp add --scope user \
  -e HERDR_MCP_DEFAULT_KIND=claude \
  -e HERDR_MCP_CWD_ALLOW="$HOME/src" \
  herdr -- /absolute/path/to/herdr-mcp/bin/herdr-mcp --stdio
```

Restart the client and ask *"use herdr_status to show my agents"*. You should see
the same counts as `check.py`.

**[docs/SETUP.md](docs/SETUP.md)** is the full walkthrough — a fresh machine to a
working setup, with a check after every step, for stdio, HTTP on the host, and
Docker.

## What you can do

| Flow | Tools |
|---|---|
| **See the board** — who is running, what they are doing, what is blocked | `herdr_status`, `herdr_agents`, `herdr_agent_read` |
| **Arrange the layout** — open tabs and panes, move, resize, zoom | `herdr_tab_create`, `herdr_pane_split`, `herdr_pane_move`, … |
| **Drive an agent** — start one, prompt it, send keys, wait for a state | `herdr_agent_start`, `herdr_agent_prompt`, `herdr_agent_wait` |
| **Run a job** — new tab, start an agent, optionally in an isolated git worktree | `herdr_open_agent`, `herdr_job_start` |

Full reference with every parameter and MCP annotation: [docs/TOOLS.md](docs/TOOLS.md).

The server also sends MCP `instructions`, so a capable client's model knows to
start with `herdr_status` and to treat `*_read` output as untrusted data.

## Install paths

| Path | When | Start at |
|---|---|---|
| **stdio** (recommended) | The client spawns herdr-mcp. No network surface. | [SETUP A](docs/SETUP.md#a-stdio-recommended) |
| **Streamable HTTP** | One long-running server, clients over loopback or a private network. Bearer token is mandatory. | [SETUP B](docs/SETUP.md#b-http-on-the-host) |
| **Docker** | An assistant in a container on the same Linux host as Herdr. | [SETUP C](docs/SETUP.md#c-http-in-docker-linux-hosts) |

### Client snippets

Policy is optional but recommended: set `HERDR_MCP_CWD_ALLOW` to the roots agents
may work in. **Omitting it means every path is allowed**, so a copy-paste config
with only `HERDR_MCP_DEFAULT_KIND` is unrestricted. See
[Configuration](#configuration) and [SECURITY.md](SECURITY.md).

Claude Code:

```bash
claude mcp add --scope user \
  -e HERDR_MCP_DEFAULT_KIND=claude \
  -e HERDR_MCP_CWD_ALLOW="$HOME/src" \
  herdr -- /absolute/path/to/herdr-mcp/bin/herdr-mcp --stdio
```

Claude Desktop (`claude_desktop_config.json`) — GUI apps do not inherit your
shell `PATH`, so set `HERDR_MCP_HERDR`:

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

opencode (`~/.config/opencode/opencode.json`) — restart opencode afterwards; it
loads MCP servers at startup:

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

More, including HTTP and a generic client: [examples/](examples/).


## Configuration

Every setting is an environment variable, read on each call.

| Env var | Default | Meaning |
|---|---|---|
| `HERDR_MCP_HERDR` | `herdr` on `PATH` | Herdr binary when not run by Herdr (set it for GUI clients). |
| `HERDR_BIN_PATH` | | Herdr binary; Herdr sets this for plugin commands. |
| `HERDR_SOCKET_PATH` | Herdr's default | Socket to talk to (honoured by the `herdr` CLI). |
| `HERDR_MCP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` (same as `--http`). |
| `HERDR_MCP_BIND` | `127.0.0.1:8765` | HTTP `host:port`. |
| `HERDR_MCP_TOKEN_FILE` | | File with the HTTP bearer token (preferred). |
| `HERDR_MCP_TOKEN` | | HTTP bearer token (`MCP_AUTH_TOKEN` accepted as a fallback). |
| `HERDR_MCP_ALLOWED_ORIGINS` | (none) | Browser origins allowed to call HTTP. |
| `HERDR_MCP_DEFAULT_KIND` | (none) | Agent kind for `herdr_open_agent` / `herdr_job_start` when the call omits it. |
| `HERDR_MCP_AGENT_KINDS` | (all) | Globs of agent kinds that may be started. |
| `HERDR_MCP_ALLOW` | (all) | Globs of agent names that may be created or targeted; others are hidden and refused. |
| `HERDR_MCP_CWD_ALLOW` | (all) | Roots for `cwd` and worktree `path` (where things open, not a sandbox). |
| `HERDR_MCP_READ_ONLY` | off | `1` exposes only read/wait tools. |
| `HERDR_MCP_DISABLE_TOOLS` | (none) | Globs of tool names to hide and refuse, e.g. `herdr_pane_run,herdr_*_close`. |
| `HERDR_MCP_ALLOW_AGENT_ARGS` | off | `1` allows `agent_args` (native flags such as permission bypasses). |
| `HERDR_MCP_STATE_DIR` | `$XDG_STATE_HOME/herdr-mcp`, else `~/.local/state/herdr-mcp` (`~/Library/Application Support/herdr-mcp` on macOS) | Audit log directory. |

Start strict — `HERDR_MCP_READ_ONLY=1`, `HERDR_MCP_CWD_ALLOW`, `HERDR_MCP_AGENT_KINDS`
— and loosen once you trust the setup. See [SECURITY.md](SECURITY.md) for the
hardening checklist and the accepted risks.

## How it compares

Herdr's marketplace lists several MCP-shaped plugins. They overlap on *drive my
session from a chat client*; they differ in how much they expose and how much you
can bound it.

| Plugin | Transport | Scope | Policy |
|---|---|---|---|
| **herdr-mcp** | stdio + HTTP | read, layout, agents, worktrees, jobs | allowlists, read-only, disable-tools, audit, annotations |
| [herdr-desktop-bridge](https://github.com/yonatangross/herdr-desktop-bridge) | stdio | read + mailbox/doorbell (deliberately not a conductor) | prompt-target allowlist |
| [herdr-spawn](https://github.com/nytafar/herdr-spawn) | stdio/HTTP | start one agent on a host | cwd allowlist |
| [entwurf](https://github.com/junghan0611/entwurf) | — | message sibling agent sessions | — |

Scopes are as published in early 2026; check each project for its current
surface. The tools are a thin wrapper over the same `herdr` CLI you already run;
the value here is the breadth of the surface plus the policy layer on top of it.

## Security model

* **Argv only, never a shell.** No generic "run any herdr command" passthrough.
* **Structural gates** (not configurable): names, ids, keys, git refs, labels,
  numbers and timeouts are validated before any command runs.
* **Policy**: allowlists, read-only mode and disabled tools (above).
* **Annotations** (`readOnlyHint`, `destructiveHint`) on every tool, so clients
  can require approval for the consequential ones.
* **`confirm=true`** on close, remove and send-keys — a guard against slips.
* **Per-target locking**, so two rapid prompts cannot merge into one turn.
* **HTTP**: mandatory bearer token (constant-time compare), Origin and
  Content-Type checks, body cap, read timeout, connection cap.
* **Audit log**: append-only JSONL, `0600`, free-form text hashed.
* Secrets are scrubbed from every `herdr` subprocess environment.

The full review, the accepted risks and a hardening checklist are in
[SECURITY.md](SECURITY.md).

## Running as a Herdr plugin

The repository carries a `herdr-plugin.toml`, so it installs like any plugin and
appears in `herdr plugin list` and the marketplace:

```bash
herdr plugin install thomasfossum/herdr-mcp --ref v0.3.0
herdr plugin action invoke herdr.mcp.check
herdr plugin log list --plugin herdr.mcp
```

The plugin registers one read-only `check` action. The MCP server itself is
launched by your MCP client, not by Herdr.

To bind a key to the check, add to Herdr's `config.toml`:

```toml
[[keys.command]]
key = "prefix+m"
type = "plugin_action"
command = "herdr.mcp.check"
description = "check herdr-mcp"
```

## Development

```bash
python3 -m unittest discover -s tests -v      # pytest also works
```

The suite runs against a fake `herdr` binary and covers the guarantees that
matter: refused calls never run a command, policy and allowlists hold (including
pane-id targets), the HTTP transport rejects missing tokens, foreign origins and
non-JSON bodies, secrets stay out of child environments and the audit log, and two
prompts become two submissions. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).