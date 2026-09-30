# Security

## Threat model in one paragraph

`herdr-mcp` exists to hand an MCP client control of a Herdr session. Anyone who
can call its tools can run shell commands as the user who owns the Herdr server
(`herdr_pane_run`), and can make other coding agents act for them
(`herdr_agent_prompt`, `herdr_job_start`). **Treat access to herdr-mcp as
equivalent to a shell as that user.** The controls below exist to keep that
power with the one client you intended, to limit what a well-behaved client can
do by accident or under prompt injection, and to leave a trail.

## Reporting a vulnerability

Please open a private security advisory on the GitHub repository
(Security → Report a vulnerability) rather than a public issue.

## Review findings (v0.1.0 → v0.2.0)

A review of v0.1.0 found the issues below. Severity is for a default install.
"Fixed" items are covered by tests in `tests/test_herdr_mcp.py`.

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | Critical | **Browser CSRF / DNS rebinding on the HTTP transport.** No `Origin` check and any `Content-Type` accepted, so a web page could `fetch("http://127.0.0.1:8765/mcp", {mode: "no-cors", body: ...})` as a CORS "simple request" and call `herdr_pane_run`. With no token (allowed on loopback) this was remote code execution from a website the user visited, in any browser that does not enforce Private Network Access / local-network permission prompts (and via DNS rebinding in those that do). | Fixed: requests with an `Origin` not in `HERDR_MCP_ALLOWED_ORIGINS` get 403; `Content-Type` must be `application/json` (415 otherwise); a token is required. |
| 2 | High | **HTTP could run unauthenticated.** On loopback silently, off loopback with only a warning. On a shared host any local user or process could drive Herdr as its owner. | Fixed: `--http` refuses to start without `HERDR_MCP_TOKEN` / `HERDR_MCP_TOKEN_FILE`. `--insecure-no-auth` exists for loopback-only experiments and is refused on other binds. |
| 3 | High | **`agent_args` allowed privilege escalation.** A client could spawn an agent with e.g. `--dangerously-skip-permissions` / `--yolo`, escaping the approval model of the client that asked. | Fixed: `agent_args` refused unless `HERDR_MCP_ALLOW_AGENT_ARGS=1`. |
| 4 | High | **`HERDR_MCP_ALLOW` was bypassable and unusable.** Pane-id targets skipped the name check, auto-generated names were never checked, raw pane tools (`herdr_pane_run` types straight into an agent's pane) and tab/workspace close ignored it entirely, and the same globs were applied to opaque ids, so any real allowlist (`job-*`) also rejected every pane id. | Fixed: the allowlist applies to agent names. Agent tools resolve pane-id targets and check the name; pane tools (`read`, `run`, `wait_output`, `move`, `close`, `agent_start`) refuse a pane hosting a non-permitted or unnamed agent; tab/workspace close and worktree remove refuse when such an agent is inside; `herdr_status` and `herdr_agents` hide those agents; generated names are checked. Panes with no agent stay usable (see accepted risks). |
| 5 | Medium | Bearer token compared with `==` (timing side channel). | Fixed: `hmac.compare_digest`. |
| 6 | Medium | HTTP resource exhaustion: unbounded or negative `Content-Length` (memory, or a read that blocks until EOF), no socket timeout, unlimited threads (slowloris), unbounded JSON-RPC batches, unread bodies parsed as the next request on keep-alive. | Mitigated: 1 MiB body cap, 60 s per-read timeout, at most 32 concurrent connections (extra ones are closed), batches capped at 32, `Connection: close` on every error response. A client that trickles bytes can still occupy slots, so a token holder or anyone who can reach the port can deny service; keep the port private. |
| 7 | Medium | The bearer token was passed in the environment of every `herdr` subprocess. | Fixed: `MCP_AUTH_TOKEN`, `HERDR_MCP_TOKEN`, `HERDR_MCP_TOKEN_FILE` scrubbed from child environments. |
| 8 | Medium | **Audit log leaked what it claimed to hash.** Timeout and "no JSON" error messages embedded the full argv (prompt text, commands) into `detail`; `agent_args`, `title`, `label`, `match`, `regex` were stored verbatim; the file was created world-readable (umask 022) and a symlink at its path was followed. | Fixed: messages carry only the subcommand; those keys are hashed; directory `0700`, file `0600`, opened with `O_NOFOLLOW`. |
| 9 | Medium | `herdr_worktree_create` `path` bypassed `HERDR_MCP_CWD_ALLOW`; `branch` / `base` went to git (via herdr) unvalidated. | Fixed: `path` goes through the cwd allowlist; refs must match a conservative `git check-ref-format` subset (no leading `-`, no `..`, no whitespace). |
| 10 | Low | Unvalidated `kind`, labels and titles (control characters / escape sequences into Herdr's UI), unbounded `lines` and timeouts (a call could pin a thread for hours), `NaN` / `Infinity` numbers, wrong types crashing into a generic internal error that skipped the audit log. | Fixed: `kind` shape plus optional `HERDR_MCP_AGENT_KINDS`, labels single-line and bounded, finite bounded ints/floats (no silent truncation of `1.5`), every exception audited. Errors raised before any command ran are reported as `refused`; errors after a command ran are reported as `failed` with `commands_run`, so a partly completed job is not mistaken for a no-op. |
| 11 | Low | Tools carried no MCP annotations, so clients could not tell `herdr_status` from `herdr_pane_run`. `confirm=true` is chosen by the model and is not a human approval. | Mitigated: `readOnlyHint` / `destructiveHint` annotations on every tool; `HERDR_MCP_READ_ONLY` and `HERDR_MCP_DISABLE_TOOLS` hide tools from the catalog and refuse them. Human approval remains your MCP client's job. |
| 12 | Low | Internal exception text returned to the caller, and herdr error results echoed the full argv (host path of the herdr binary plus the caller's prompt text). | Fixed: generic message for internal errors, detail to stderr; herdr errors report only the subcommand (`"command": "agent prompt"`). |
| 13 | Low | The plugin manifest's link handler ran the check action on every `https://herdr.dev/` link. | Removed. |
| 14 | Low | Container: compose file hard-coded one user's uid and home paths; the image ran as root when `user:` was omitted; token passed as a plain environment variable; Herdr's config directory (including `config.toml`, which can define commands) mounted writable. | Fixed: image defaults to `nobody`; compose takes uid/gid/paths from `docker/.env`, mounts the socket directory read-only, runs with a read-only root, all capabilities dropped and `no-new-privileges`, reads the token from a Docker secret, publishes on loopback only. |

Checked and **not** an issue with Herdr 0.9.1: option injection through free
text. Herdr's CLI fills positional slots first (`agent prompt <TARGET> <TEXT>`
takes `--wait` as the text) and option values take the next token verbatim, so a
prompt or label shaped like a flag cannot become one. herdr-mcp never inserts
`--` before free text because, with that parser, `--` would itself become the
text.

## Accepted risks (by design, documented)

* **Tool access is code execution** as the Herdr user. That is the product.
* **Prompt injection across agents.** `herdr_agent_read` / `herdr_pane_read`
  return terminal output written by other agents, web pages they fetched,
  files they printed. A controlling model that obeys instructions in that text
  can be steered into driving other agents. Tool descriptions mark this output
  as untrusted; use `HERDR_MCP_ALLOW`, `HERDR_MCP_CWD_ALLOW` and read-only
  mode to limit the blast radius.
* **`HERDR_MCP_ALLOW` scopes agents, not the machine.** Panes without an agent
  are not covered, `herdr_panes` / `herdr_tabs` / `herdr_workspaces` still list
  everything, and a shell in any usable pane can reach the rest of the session
  through the `herdr` CLI. It stops a client from addressing other agents by
  mistake; it is not a sandbox. Combine it with `HERDR_MCP_DISABLE_TOOLS`
  (e.g. `herdr_pane_run`) when the boundary matters.
* **`HERDR_MCP_CWD_ALLOW` limits where tabs, workspaces and worktrees open**,
  not what happens next: `herdr_pane_run "cd /"` or a prompt asking an agent to
  work elsewhere gets around it.
* **The socket is the crown jewel.** A compromised herdr-mcp container has full
  control of the host's Herdr, which means code execution on the host as that
  user. Container hardening limits persistence, not that.
* **No TLS.** Keep HTTP on loopback or a private container network. Put a TLS
  reverse proxy in front if it must cross a network.
* **`HERDR_MCP_CWD_ALLOW` is checked at call time** (after `realpath`); a symlink
  swapped between validation and use is not caught.
* **Audit hashes are unsalted and truncated.** They show that two calls carried
  the same text; they do not protect short, guessable prompts.
* **Plugin installs run repository code.** Pin a tag or commit:
  `herdr plugin install thomasfossum/herdr-mcp --ref v0.3.1`.
* **Prompt serialisation is per target string.** Addressing one agent by name
  and by pane id at the same moment uses two locks.

## Hardening checklist

1. Prefer **stdio**: no network surface at all.
2. For HTTP: `HERDR_MCP_TOKEN_FILE` with `openssl rand -hex 32`, bind
   `127.0.0.1` or a private network only.
3. Set `HERDR_MCP_CWD_ALLOW` to the directories agents may work in.
4. Set `HERDR_MCP_AGENT_KINDS` to the agents you actually use.
5. Start read-only (`HERDR_MCP_READ_ONLY=1`) and widen with
   `HERDR_MCP_DISABLE_TOOLS` (e.g. `herdr_pane_run,herdr_*_close`).
6. Leave `HERDR_MCP_ALLOW_AGENT_ARGS` unset.
7. Keep your MCP client's per-tool approval on for tools with `destructiveHint`.
8. Review `~/.local/state/herdr-mcp/audit.jsonl` (or `HERDR_MCP_STATE_DIR`).
