# Changelog

## 0.3.0 - 2026-09-30

Protocol modernization, onboarding fixes from an agent adoption test, and
packaging for a wider audience.

### Added

* Dual-era MCP support: `2026-07-28` and `2025-11-25` protocol versions
  alongside the legacy `initialize` handshake. `server/discover`, per-request
  `_meta` protocol-version handling, `resultType` on every result, cacheable
  list results (`ttlMs`, `cacheScope`), and `UnsupportedProtocolVersionError`
  (`-32022`). Unsupported `MCP-Protocol-Version` headers on HTTP get `400`.
* MCP `instructions` in the `initialize` and `server/discover` results, so a
  client's model knows where to start.
* `docs/TOOLS.md` (full tool reference), `CONTRIBUTING.md`, `examples/`
  (client configs), issue and pull-request templates, and `[project.urls]`
  metadata.
* `docs/SETUP.md` "Protocol versions" section.
* A neutral "How it compares" table in the README.

### Changed

* README quick start leads with the clone path (`python3 bin/check.py`); client
  snippets are consistent and warn that omitting `HERDR_MCP_CWD_ALLOW` leaves
  every path allowed. opencode example gained a restart/verify step.
* The SETUP stdio hand-check includes `notifications/initialized`.
* Default audit directory honours `XDG_STATE_HOME` and uses
  `~/Library/Application Support/herdr-mcp` on macOS.
* README restructured for onboarding: quick start, flows, install paths, client
  snippets; the large per-tool tables moved to `docs/TOOLS.md`.

## 0.2.0

Generalised for community use and hardened after a security review
(see [SECURITY.md](SECURITY.md)).

### Breaking

* `--http` refuses to start without a token (`HERDR_MCP_TOKEN_FILE`,
  `HERDR_MCP_TOKEN` or `MCP_AUTH_TOKEN`). `--insecure-no-auth` exists for
  loopback-only experiments.
* HTTP requests must be `Content-Type: application/json`; browser `Origin`s are
  rejected unless listed in `HERDR_MCP_ALLOWED_ORIGINS`.
* `agent_args` are refused unless `HERDR_MCP_ALLOW_AGENT_ARGS=1`.
* `herdr_job_start` no longer defaults to `opencode`: pass `kind` or set
  `HERDR_MCP_DEFAULT_KIND`. `herdr_open_agent` accepts the same default.
* `HERDR_MCP_ALLOW` now applies to agent names only (it used to also match
  opaque ids, which made it unusable). It is enforced for pane-id targets, raw
  pane tools and tab/workspace close, and filters `herdr_status` /
  `herdr_agents`.
* Tool errors raised after a herdr command ran are reported as
  `"kind": "failed"` with `commands_run`, not `"refused"`.
* herdr error results carry only the subcommand in `command`.
* `herdr_pane_wait_output` no longer offers the `detection` source (herdr
  rejects it there).
* Docker: `docker/compose.fragment.yml` replaced by `docker/compose.yml` plus
  `docker/.env.example`; the socket directory mounts at `/run/herdr`.
* Plugin manifest: the `herdr.dev` link handler is removed.

### Added

* `HERDR_MCP_READ_ONLY`, `HERDR_MCP_DISABLE_TOOLS`, `HERDR_MCP_AGENT_KINDS`,
  `HERDR_MCP_DEFAULT_KIND`, `HERDR_MCP_TOKEN_FILE`, `HERDR_MCP_ALLOWED_ORIGINS`.
* MCP tool annotations (`readOnlyHint`, `destructiveHint`).
* Validation of git refs, labels, numeric bounds and timeouts; worktree `path`
  honours `HERDR_MCP_CWD_ALLOW`.
* `docs/SETUP.md`, `SECURITY.md`.

### Fixed

* Constant-time token comparison; request body cap, socket timeout,
  32-connection cap, batch cap; non-finite and fractional integers refused.
* Token scrubbed from `herdr` subprocess environments.
* Audit log is `0600`, no longer leaks prompt text through error details, and
  hashes `agent_args`, titles, labels and patterns.
* Slow HTTP startup caused by a reverse-DNS lookup.

## 0.1.0

Initial release.
