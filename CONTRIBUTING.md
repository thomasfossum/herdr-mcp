# Contributing

Thanks for considering a contribution. This is a small, dependency-free project;
keeping it that way is a feature.

## Ground rules

* **No new runtime dependencies.** The server must keep running on a stock
  `python3` (3.9+) with the standard library only. Dev-only tooling is fine.
* **Every new capability gets a refusal test.** Anything that can run a command,
  touch a socket, or reach the filesystem needs a test proving it does *not* act
  on invalid or disallowed input.
* **Secrets never enter logs or child environments.** See the audit scrubber in
  `src/herdr_mcp/audit.py` and the environment scrub in `src/herdr_mcp/herdr.py`.
* **Keep the surface honest.** If a tool can do something dangerous, say so in
  its description, annotate it `destructiveHint`, and add it to the policy gates.

## Development

```bash
git clone https://github.com/thomasfossum/herdr-mcp.git
cd herdr-mcp
python3 -m unittest discover -s tests -v      # or: pytest -q
```

The suite runs against a fake `herdr` binary, so it needs no live Herdr session.

To exercise the real thing locally:

```bash
python3 bin/check.py                 # read-only self-test against your session
herdr plugin link "$PWD"             # register as a plugin
herdr plugin action invoke herdr.mcp.check
```

## Layout

| Path | Role |
|---|---|
| `src/herdr_mcp/tools.py` | Tool registry, validation per tool, handlers |
| `src/herdr_mcp/safety.py` | Structural gates, allowlists, policy |
| `src/herdr_mcp/herdr.py` | CLI wrapper (rc 0/1/2 conventions, timeout) |
| `src/herdr_mcp/mcp.py` | MCP/JSON-RPC dispatch |
| `src/herdr_mcp/transports.py` | stdio and Streamable HTTP |
| `src/herdr_mcp/locks.py` | Per-target prompt serialisation |
| `src/herdr_mcp/audit.py` | Append-only hashed audit log |

## Adding a tool

1. Add a `@tool(...)` handler in `tools.py`. Build the command as an argv list
   (never a shell string) and validate every argument in `safety.py` first.
2. Set `read_only=True` or `destructive=True` where they apply.
3. Add a test in `tests/test_herdr_mcp.py` that covers the happy path *and* a
   refusal (the fake binary's argv log must not exist).
4. Update [docs/TOOLS.md](docs/TOOLS.md).

## Commits and pull requests

* One focused change per pull request.
* Commit subjects are full sentences saying what changed and why.
* `python3 -m unittest discover -s tests` must pass on Python 3.9–3.13.
* Do not bump the version or edit `CHANGELOG.md` release sections; maintainers do
  that at release time. Add your notes under `## Unreleased`.

## Security

Report vulnerabilities through GitHub's private advisory flow (Security →
Report a vulnerability), not a public issue. See [SECURITY.md](SECURITY.md) for
the threat model and the hardening checklist.