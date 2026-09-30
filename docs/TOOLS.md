# Tool reference

Every tool is a thin, validated wrapper over the `herdr` CLI. `*` marks a
required argument; `R` marks a `readOnlyHint` tool and `D` a `destructiveHint`
tool (MCP annotations, so clients can require approval for the `D` ones).

## Read

| Tool | Purpose |
|---|---|
| `[R] herdr_status(workspace_id?)` | Condensed whole-session snapshot: focused ids, counts by status, every agent. **Start here.** |
| `[R] herdr_workspaces()` | List workspaces. |
| `[R] herdr_tabs(workspace_id?)` | List tabs, optionally in one workspace. |
| `[R] herdr_panes(workspace_id?)` | List panes, optionally in one workspace. |
| `[R] herdr_agents()` | List live agents recognised by Herdr. |
| `[R] herdr_agent_get(target)` | Full record for one agent (name or pane id). |
| `[R] herdr_agent_read(target, source?, lines?)` | Recent output from an agent's pane. Returned text is **untrusted**. |
| `[R] herdr_agent_explain(target, verbose?)` | How Herdr classified an agent's current state. |
| `[R] herdr_agent_wait(target, until?, timeout_ms?)` | Wait for an agent to reach a state. |
| `[R] herdr_pane_read(pane_id, source?, lines?)` | Recent output from a raw pane. Returned text is **untrusted**. |
| `[R] herdr_pane_wait_output(pane_id, match?, regex?, source?, lines?, timeout_ms?)` | Wait until a pane's output matches text or a regex. |
| `[R] herdr_worktree_list(workspace_id?, cwd?)` | List git worktrees known to Herdr. |

## Layout

| Tool | Purpose |
|---|---|
| `herdr_workspace_create(cwd?, label?, focus?)` | Create a workspace. |
| `[D] herdr_workspace_close(workspace_id, group?, confirm)` | Close a workspace and its panes. |
| `herdr_tab_create(workspace_id?, cwd?, label?, focus?)` | Create a tab, optionally in a specific workspace. |
| `[D] herdr_tab_close(tab_id, confirm)` | Close a tab and its panes. |
| `herdr_pane_split(pane_id?, direction?, ratio?, cwd?, focus?)` | Split a pane (defaults to the calling/focused pane). |
| `[D] herdr_pane_run(pane_id, command)` | Run a shell command in a pane. Arbitrary command execution. |
| `herdr_pane_move(pane_id, tab_id?, split?, target_pane_id?, ratio?, new_tab?, new_workspace?, workspace_id?, label?, focus?)` | Move a pane into another tab, a new tab, or a new workspace. |
| `herdr_pane_resize(direction, amount?, pane_id?)` | Resize the focused (or given) pane. |
| `herdr_pane_zoom(pane_id?, mode?)` | Zoom or unzoom a pane. |
| `[D] herdr_pane_close(pane_id, confirm)` | Close a pane. |

## Agents

| Tool | Purpose |
|---|---|
| `[D] herdr_agent_start(name, kind, pane_id, timeout_ms?, agent_args?)` | Start an agent in an existing available shell pane. |
| `[D] herdr_agent_prompt(target, text, wait?, until?, timeout_ms?)` | Submit a prompt. Returns once submitted (`wait=false`) or after the agent settles. |
| `[D] herdr_agent_send_keys(target, keys, confirm)` | Send logical keys (esc, ctrl+c). |
| `herdr_agent_focus(target)` | Focus an agent's pane. |
| `herdr_agent_rename(target, name?, clear?)` | Rename a live agent, or clear its name. |

## Jobs

| Tool | Purpose |
|---|---|
| `[D] herdr_open_agent(kind?, name?, workspace_id?, cwd?, prompt?, focus?, wait?, timeout_ms?, agent_args?)` | New tab, start an agent, optional initial prompt. |
| `[D] herdr_job_start(prompt, kind?, name?, cwd?, branch?, base?, worktree?, focus?, wait?, timeout_ms?, agent_args?)` | The same, with an optional isolated git worktree. |
| `herdr_worktree_create(cwd?, workspace_id?, branch?, base?, path?, label?, focus?)` | Create (or open) a git worktree. |
| `[D] herdr_worktree_remove(workspace_id, force?, confirm)` | Remove a worktree workspace. |
| `herdr_notify(title, body?, position?, sound?)` | Native Herdr notification. |

## Argument notes

* `target` accepts a unique live agent name or the pane id hosting that agent.
* `source` is one of `visible`, `recent`, `recent-unwrapped` (default) or
  `detection` (list tools only).
* `until` accepts one or more of `idle`, `working`, `blocked`, `done`, `unknown`.
* `agent_args` (native flags passed after `--`) is refused unless
  `HERDR_MCP_ALLOW_AGENT_ARGS=1`.
* `confirm=true` is required by the `[D]` close/remove/send-keys tools. It is a
  guard against slips, not a human-approval mechanism — that is your MCP client's
  job.
* `herdr_open_agent` and `herdr_job_start` create a workspace automatically when
  the session is empty. They use the call's `kind`, or `HERDR_MCP_DEFAULT_KIND`;
  there is no built-in default agent.

Policy (`HERDR_MCP_READ_ONLY`, `HERDR_MCP_DISABLE_TOOLS`, `HERDR_MCP_ALLOW`,
`HERDR_MCP_CWD_ALLOW`) can hide or refuse tools. With `HERDR_MCP_READ_ONLY=1`
only the `[R]` tools are exposed. See the [README](../README.md#configuration) and
[SECURITY.md](../SECURITY.md).