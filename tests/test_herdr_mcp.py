"""Tests for herdr-mcp. Standard library unittest; no runtime dependencies."""

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import threading
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from herdr_mcp import herdr, mcp, tools  # noqa: E402

FAKE = '''#!/usr/bin/env python3
import json, os, sys
log = os.environ.get("FAKE_HERDR_LOG")
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(sys.argv[1:]) + "\\n")
sys.stdout.write(os.environ.get("FAKE_HERDR_OUT", "{}"))
sys.stderr.write(os.environ.get("FAKE_HERDR_ERR", ""))
sys.exit(int(os.environ.get("FAKE_HERDR_RC", "0")))
'''


class FakeHerdr:
    def __init__(self, tmp: str):
        self.dir = tmp
        self.bin = os.path.join(tmp, "herdr")
        with open(self.bin, "w", encoding="utf-8") as fh:
            fh.write(FAKE)
        os.chmod(self.bin, os.stat(self.bin).st_mode | stat.S_IEXEC)
        self.log = os.path.join(tmp, "argv.log")

    def env(self, **extra: str):
        env = dict(os.environ)
        env["HERDR_BIN_PATH"] = self.bin
        env["FAKE_HERDR_LOG"] = self.log
        env.update(extra)
        return env

    def argv_lines(self):
        if not os.path.exists(self.log):
            return []
        with open(self.log, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]


class EnvMixin(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.fake = FakeHerdr(self._tmp.name)
        self._saved = dict(os.environ)
        os.environ.update(self.fake.env())

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._saved)
        self._tmp.cleanup()


class SafetyTests(EnvMixin):
    def test_destructive_without_confirm_never_runs(self):
        payload, is_error = tools.invoke("herdr_pane_close", {"pane_id": "w1:p1"})
        self.assertTrue(is_error)
        self.assertEqual(payload["kind"], "refused")
        self.assertFalse(os.path.exists(self.fake.log))

    def test_invalid_agent_name_never_runs(self):
        payload, is_error = tools.invoke(
            "herdr_agent_prompt", {"target": "../etc/passwd", "text": "hi"}
        )
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_bad_id_never_runs(self):
        payload, is_error = tools.invoke("herdr_pane_read", {"pane_id": "x; whoami"})
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_confirm_allows_the_call(self):
        os.environ["FAKE_HERDR_OUT"] = '{"id":"x","result":{"ok":true}}'
        payload, is_error = tools.invoke(
            "herdr_pane_close", {"pane_id": "w1:p1", "confirm": True}
        )
        self.assertFalse(is_error)
        self.assertEqual(len(self.fake.argv_lines()), 1)

    def test_cwd_allowlist(self):
        os.environ["HERDR_MCP_CWD_ALLOW"] = "/srv/allowed"
        payload, is_error = tools.invoke(
            "herdr_workspace_create", {"cwd": "/tmp/elsewhere"}
        )
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))


class HerdrWrapperTests(EnvMixin):
    def test_rc2_is_plain_text_and_does_not_crash(self):
        os.environ["FAKE_HERDR_RC"] = "2"
        os.environ["FAKE_HERDR_ERR"] = "unknown flag --bogus"
        with self.assertRaises(herdr.HerdrError) as ctx:
            herdr.run(["agent", "start", "x", "--bogus"])
        self.assertIn("rc=2", str(ctx.exception))

    def test_rc2_surfaces_as_tool_error(self):
        os.environ["FAKE_HERDR_RC"] = "2"
        os.environ["FAKE_HERDR_ERR"] = "unknown flag --bogus"
        payload, is_error = tools.invoke(
            "herdr_agents", {}
        )
        self.assertTrue(is_error)
        self.assertIn("error", payload)

    def test_rc1_json_error_envelope(self):
        os.environ["FAKE_HERDR_RC"] = "1"
        os.environ["FAKE_HERDR_ERR"] = '{"error":{"code":"nope","message":"bad"}}'
        payload, is_error = tools.invoke("herdr_agents", {})
        self.assertTrue(is_error)
        self.assertEqual(payload["rc"], 1)

    def test_success_returns_json(self):
        os.environ["FAKE_HERDR_OUT"] = '{"id":"cli:workspace:list","result":{"workspaces":[]}}'
        payload, is_error = tools.invoke("herdr_workspaces", {})
        self.assertFalse(is_error)
        self.assertEqual(payload["result"]["workspaces"], [])


class ConcurrencyTests(EnvMixin):
    def test_two_prompts_produce_two_submissions(self):
        os.environ["FAKE_HERDR_OUT"] = '{"id":"cli:agent:prompt","result":{}}'
        errors = []

        def send(text: str) -> None:
            try:
                tools.invoke("herdr_agent_prompt", {"target": "probe", "text": text})
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [
            threading.Thread(target=send, args=(f"message {i}",)) for i in range(2)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertFalse(errors)
        lines = self.fake.argv_lines()
        self.assertEqual(len(lines), 2)
        texts = sorted(line[-1] for line in lines)
        self.assertEqual(texts, ["message 0", "message 1"])


class MappingTests(EnvMixin):
    def test_agent_name_is_sanitised(self):
        import re

        name = tools._agent_name("OpenCode!", None)
        self.assertRegex(name, r"^[a-z][a-z0-9_-]{0,31}$")

    def test_pick_pane_finds_nested(self):
        payload = {"result": {"tab": {"tab_id": "w1:t1"}, "root_pane": {"pane_id": "w1:p9"}}}
        self.assertEqual(tools._pick_pane(payload), "w1:p9")

    def test_open_agent_starts_in_new_tab(self):
        os.environ["FAKE_HERDR_OUT"] = json.dumps(
            {"id": "cli:tab:create", "result": {"root_pane": {"pane_id": "w1:p5"}}}
        )
        payload, is_error = tools.invoke(
            "herdr_open_agent", {"kind": "opencode", "name": "job1", "cwd": "/tmp"}
        )
        self.assertFalse(is_error)
        self.assertEqual(payload["pane_id"], "w1:p5")
        joiners = [line[0] for line in self.fake.argv_lines()]
        self.assertIn("tab", joiners)
        self.assertIn("agent", joiners)


class ProtocolTests(unittest.TestCase):
    def test_unknown_method(self):
        response = mcp.dispatch({"jsonrpc": "2.0", "id": 1, "method": "nope"})
        self.assertEqual(response["error"]["code"], -32601)

    def test_parse_error(self):
        out = json.loads(mcp.handle_raw("{not json"))
        self.assertEqual(out["error"]["code"], -32700)

    def test_notification_has_no_response(self):
        self.assertIsNone(
            mcp.dispatch({"jsonrpc": "2.0", "method": "notifications/initialized"})
        )

    def test_initialize_and_catalog(self):
        init = mcp.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(init["result"]["serverInfo"]["name"], "herdr-mcp")
        listing = mcp.dispatch({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in listing["result"]["tools"]}
        self.assertIn("herdr_status", names)
        self.assertIn("herdr_open_agent", names)
        self.assertIn("herdr_job_start", names)

    def test_unknown_tool_is_error_result(self):
        response = mcp.dispatch(
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "nope"}}
        )
        self.assertTrue(response["result"]["isError"])

    def test_results_carry_result_type_and_server_meta(self):
        response = mcp.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        result = response["result"]
        self.assertEqual(result["resultType"], "complete")
        self.assertEqual(
            result["_meta"]["io.modelcontextprotocol/serverInfo"]["name"], "herdr-mcp"
        )
        # Modern list results are cacheable.
        self.assertIn("ttlMs", result)
        self.assertIn("cacheScope", result)

    def test_server_discover(self):
        response = mcp.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "server/discover",
                "params": {
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                        "io.modelcontextprotocol/clientCapabilities": {},
                    }
                },
            }
        )
        result = response["result"]
        self.assertIn("2026-07-28", result["supportedVersions"])
        self.assertIn("tools", result["capabilities"])
        self.assertTrue(result["instructions"])

    def test_unsupported_modern_version_is_rejected(self):
        response = mcp.dispatch(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "1900-01-01"}},
            }
        )
        self.assertEqual(response["error"]["code"], -32022)
        self.assertIn("2026-07-28", response["error"]["data"]["supported"])

    def test_initialize_carries_instructions(self):
        init = mcp.dispatch({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertTrue(init["result"]["instructions"])

    def test_legacy_initialize_falls_back_to_newest_legacy(self):
        init = mcp.dispatch(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "1"}}
        )
        version = init["result"]["protocolVersion"]
        self.assertNotEqual(version, mcp.MODERN_PROTOCOL_VERSION)
        self.assertIn(version, mcp.SUPPORTED_PROTOCOL_VERSIONS)



class PolicyTests(EnvMixin):
    def test_agent_args_are_off_by_default(self):
        payload, is_error = tools.invoke(
            "herdr_agent_start",
            {"name": "a1", "kind": "claude", "pane_id": "w1:p1", "agent_args": ["--yolo"]},
        )
        self.assertTrue(is_error)
        self.assertIn("HERDR_MCP_ALLOW_AGENT_ARGS", payload["error"])
        self.assertFalse(os.path.exists(self.fake.log))

    def test_agent_args_opt_in(self):
        os.environ["HERDR_MCP_ALLOW_AGENT_ARGS"] = "1"
        payload, is_error = tools.invoke(
            "herdr_agent_start",
            {"name": "a1", "kind": "claude", "pane_id": "w1:p1", "agent_args": ["--model", "x"]},
        )
        self.assertFalse(is_error)
        self.assertEqual(self.fake.argv_lines()[0][-3:], ["--", "--model", "x"])

    def test_open_agent_refuses_before_side_effects(self):
        # agent_args is refused before any tab is created.
        payload, is_error = tools.invoke(
            "herdr_open_agent", {"kind": "claude", "agent_args": ["--yolo"]}
        )
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_kind_is_validated(self):
        for bad in ("--help", "Claude", "a b", ""):
            payload, is_error = tools.invoke(
                "herdr_agent_start", {"name": "a1", "kind": bad, "pane_id": "w1:p1"}
            )
            self.assertTrue(is_error, bad)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_kind_allowlist(self):
        os.environ["HERDR_MCP_AGENT_KINDS"] = "claude,codex"
        _, is_error = tools.invoke(
            "herdr_agent_start", {"name": "a1", "kind": "opencode", "pane_id": "w1:p1"}
        )
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_job_start_needs_a_kind(self):
        os.environ.pop("HERDR_MCP_DEFAULT_KIND", None)
        payload, is_error = tools.invoke("herdr_job_start", {"prompt": "hi"})
        self.assertTrue(is_error)
        self.assertIn("HERDR_MCP_DEFAULT_KIND", payload["error"])
        self.assertFalse(os.path.exists(self.fake.log))

    def test_git_refs_are_validated(self):
        for bad in ("-b", "--upload-pack=x", "a..b", "a b", "x.lock"):
            _, is_error = tools.invoke(
                "herdr_worktree_create", {"cwd": "/tmp", "branch": bad}
            )
            self.assertTrue(is_error, bad)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_worktree_path_obeys_cwd_allowlist(self):
        os.environ["HERDR_MCP_CWD_ALLOW"] = "/srv/allowed"
        _, is_error = tools.invoke(
            "herdr_worktree_create", {"cwd": "/srv/allowed/repo", "path": "/etc/wt"}
        )
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_bounds(self):
        _, is_error = tools.invoke("herdr_pane_read", {"pane_id": "w1:p1", "lines": 10**9})
        self.assertTrue(is_error)
        _, is_error = tools.invoke("herdr_pane_split", {"ratio": float("nan")})
        self.assertTrue(is_error)
        _, is_error = tools.invoke("herdr_tab_create", {"label": "a\nb"})
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_wrong_type_is_refused_not_crashed(self):
        payload, is_error = tools.invoke("herdr_agent_start", {"name": "a1"})
        self.assertTrue(is_error)
        self.assertEqual(payload["kind"], "refused")

    def test_read_only_mode(self):
        os.environ["HERDR_MCP_READ_ONLY"] = "1"
        payload, is_error = tools.invoke("herdr_pane_run", {"pane_id": "w1:p1", "command": "id"})
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))
        names = {t["name"] for t in tools.catalog()}
        self.assertIn("herdr_status", names)
        self.assertNotIn("herdr_pane_run", names)
        self.assertNotIn("herdr_pane_close", names)

    def test_disable_tools(self):
        os.environ["HERDR_MCP_DISABLE_TOOLS"] = "herdr_pane_run,herdr_*_close"
        names = {t["name"] for t in tools.catalog()}
        self.assertNotIn("herdr_pane_run", names)
        self.assertNotIn("herdr_tab_close", names)
        self.assertIn("herdr_agent_prompt", names)

    def test_pane_id_target_is_checked_against_name_allowlist(self):
        os.environ["HERDR_MCP_ALLOW"] = "job-*"
        os.environ["FAKE_HERDR_OUT"] = json.dumps(
            {"result": {"agent": {"name": "private", "pane_id": "w1:p1"}}}
        )
        payload, is_error = tools.invoke("herdr_agent_prompt", {"target": "w1:p1", "text": "hi"})
        self.assertTrue(is_error)
        # Only the lookup ran, never the prompt.
        self.assertEqual([line[:2] for line in self.fake.argv_lines()], [["agent", "get"]])

    def test_generated_names_obey_allowlist(self):
        os.environ["HERDR_MCP_ALLOW"] = "job-*"
        _, is_error = tools.invoke("herdr_open_agent", {"kind": "claude"})
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_annotations(self):
        by_name = {t["name"]: t for t in tools.catalog()}
        self.assertTrue(by_name["herdr_status"]["annotations"]["readOnlyHint"])
        self.assertTrue(by_name["herdr_pane_run"]["annotations"]["destructiveHint"])
        self.assertTrue(by_name["herdr_pane_close"]["annotations"]["destructiveHint"])


class SecretHandlingTests(EnvMixin):
    def test_token_is_not_passed_to_herdr(self):
        os.environ["HERDR_MCP_TOKEN"] = "s3cret"
        os.environ["MCP_AUTH_TOKEN"] = "s3cret"
        env = herdr._child_env()
        self.assertNotIn("HERDR_MCP_TOKEN", env)
        self.assertNotIn("MCP_AUTH_TOKEN", env)

    def test_audit_log_is_private_and_redacted(self):
        state = os.path.join(self._tmp.name, "state")
        os.environ["HERDR_MCP_STATE_DIR"] = state
        os.environ["FAKE_HERDR_OUT"] = "{}"
        tools.invoke("herdr_agent_prompt", {"target": "probe", "text": "top secret prompt"})
        path = os.path.join(state, "audit.jsonl")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        self.assertNotIn("top secret", content)

    def test_timeout_message_has_no_prompt_text(self):
        err = herdr.HerdrError("x", rc=124, argv=["herdr", "agent", "prompt", "t", "secret text"])
        self.assertNotIn("secret", err.summary())


class HTTPTests(unittest.TestCase):
    TOKEN = "t" * 40

    @classmethod
    def setUpClass(cls):
        from herdr_mcp import transports

        handler = type("_H", (transports._Handler,), {"token": cls.TOKEN, "log_message": lambda *a: None})
        cls.httpd = transports.Server(("127.0.0.1", 0), handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def post(self, body=b'{"jsonrpc":"2.0","id":1,"method":"ping"}', **headers):
        import http.client

        base = {"Content-Type": "application/json", "Authorization": f"Bearer {self.TOKEN}"}
        base.update(headers)
        base = {k: v for k, v in base.items() if v is not None}
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/mcp", body=body, headers=base)
        response = conn.getresponse()
        response.read()
        conn.close()
        return response.status

    def test_ok(self):
        self.assertEqual(self.post(), 200)

    def test_wrong_token(self):
        self.assertEqual(self.post(Authorization="Bearer nope"), 401)
        self.assertEqual(self.post(Authorization=None), 401)

    def test_browser_origin_rejected(self):
        self.assertEqual(self.post(Origin="https://evil.example"), 403)

    def test_simple_request_content_type_rejected(self):
        # text/plain is what a CSRF form or no-cors fetch can send without preflight.
        self.assertEqual(self.post(**{"Content-Type": "text/plain"}), 415)

    def test_protocol_version_header(self):
        self.assertEqual(self.post(**{"MCP-Protocol-Version": "1900-01-01"}), 400)
        supported = mcp.SUPPORTED_PROTOCOL_VERSIONS[0]
        self.assertEqual(self.post(**{"MCP-Protocol-Version": supported}), 200)



class ServerStartupTests(unittest.TestCase):
    def test_http_without_token_refuses(self):
        from herdr_mcp import server

        saved = dict(os.environ)
        try:
            for key in ("HERDR_MCP_TOKEN", "MCP_AUTH_TOKEN", "HERDR_MCP_TOKEN_FILE"):
                os.environ.pop(key, None)
            self.assertEqual(server.main(["--http", "--bind", "127.0.0.1:0"]), 2)
            self.assertEqual(
                server.main(["--http", "--bind", "0.0.0.0:0", "--insecure-no-auth"]), 2
            )
        finally:
            os.environ.clear()
            os.environ.update(saved)


class PaneAllowlistTests(EnvMixin):
    LISTING = json.dumps({"result": {"agents": [
        {"name": "private", "pane_id": "w1:p1", "tab_id": "w1:t1", "workspace_id": "w1"},
        {"pane_id": "w1:p2", "tab_id": "w1:t1", "workspace_id": "w1"},
        {"name": "job-1", "pane_id": "w2:p1", "tab_id": "w2:t1", "workspace_id": "w2"},
    ]}})

    def setUp(self):
        super().setUp()
        os.environ["HERDR_MCP_ALLOW"] = "job-*"
        os.environ["FAKE_HERDR_OUT"] = self.LISTING

    def ran(self):
        return [line[:2] for line in self.fake.argv_lines()]

    def test_pane_run_into_foreign_agent_is_refused(self):
        _, is_error = tools.invoke("herdr_pane_run", {"pane_id": "w1:p1", "command": "id"})
        self.assertTrue(is_error)
        self.assertEqual(self.ran(), [["agent", "list"]])

    def test_unnamed_agent_is_foreign(self):
        _, is_error = tools.invoke("herdr_pane_read", {"pane_id": "w1:p2"})
        self.assertTrue(is_error)
        self.assertEqual(self.ran(), [["agent", "list"]])

    def test_close_tab_with_foreign_agent_is_refused(self):
        _, is_error = tools.invoke("herdr_tab_close", {"tab_id": "w1:t1", "confirm": True})
        self.assertTrue(is_error)
        _, is_error = tools.invoke("herdr_workspace_close", {"workspace_id": "w1", "confirm": True})
        self.assertTrue(is_error)
        self.assertNotIn(["tab", "close"], self.ran())
        self.assertNotIn(["workspace", "close"], self.ran())

    def test_permitted_and_empty_panes_are_usable(self):
        _, is_error = tools.invoke("herdr_pane_run", {"pane_id": "w2:p1", "command": "id"})
        self.assertFalse(is_error)
        _, is_error = tools.invoke("herdr_pane_run", {"pane_id": "w9:p9", "command": "id"})
        self.assertFalse(is_error)
        self.assertEqual(self.ran().count(["pane", "run"]), 2)

    def test_listings_hide_foreign_agents(self):
        payload, _ = tools.invoke("herdr_agents", {})
        self.assertEqual([a.get("name") for a in payload["result"]["agents"]], ["job-1"])
        os.environ["FAKE_HERDR_OUT"] = json.dumps({"result": {"snapshot": json.loads(self.LISTING)["result"]}})
        payload, _ = tools.invoke("herdr_status", {})
        self.assertEqual([a["name"] for a in payload["agents"]], ["job-1"])


class FailureAccountingTests(EnvMixin):
    def test_infinite_numbers_are_refused_and_audited(self):
        state = os.path.join(self._tmp.name, "state")
        os.environ["HERDR_MCP_STATE_DIR"] = state
        response = json.loads(mcp.handle_raw(
            '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":'
            '{"name":"herdr_pane_read","arguments":{"pane_id":"w1:p1","lines":Infinity}}}'
        ))
        self.assertTrue(response["result"]["isError"])
        self.assertIn("refused", response["result"]["content"][0]["text"])
        self.assertTrue(os.path.exists(os.path.join(state, "audit.jsonl")))
        _, is_error = tools.invoke("herdr_pane_read", {"pane_id": "w1:p1", "lines": 1.5})
        self.assertTrue(is_error)
        self.assertFalse(os.path.exists(self.fake.log))

    def test_failure_after_side_effects_is_not_called_refused(self):
        # tab create "succeeds" but returns no pane id.
        os.environ["FAKE_HERDR_OUT"] = '{"result": {"workspaces": [{"workspace_id": "w1"}]}}'
        payload, is_error = tools.invoke("herdr_open_agent", {"kind": "claude"})
        self.assertTrue(is_error)
        self.assertEqual(payload["kind"], "failed")
        self.assertGreaterEqual(payload["commands_run"], 1)

    def test_client_error_has_no_free_text(self):
        os.environ["FAKE_HERDR_RC"] = "1"
        os.environ["FAKE_HERDR_ERR"] = '{"error":"nope"}'
        payload, _ = tools.invoke("herdr_agent_prompt", {"target": "probe", "text": "secret words"})
        self.assertNotIn("secret", json.dumps(payload))
        self.assertEqual(payload["command"], "agent prompt")

    def test_git_ref_edge_cases(self):
        for bad in ("/foo", "@", "a/.b", ".x", "a.lock/b"):
            _, is_error = tools.invoke("herdr_worktree_create", {"cwd": "/tmp", "branch": bad})
            self.assertTrue(is_error, bad)
        self.assertFalse(os.path.exists(self.fake.log))


class ConnectionCapTests(unittest.TestCase):
    def test_connections_over_cap_are_closed(self):
        import socket

        from herdr_mcp import transports

        handler = type("_H", (transports._Handler,), {"token": "x" * 40, "log_message": lambda *a: None})
        httpd = transports.Server(("127.0.0.1", 0), handler, max_connections=1)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            port = httpd.server_address[1]
            hog = socket.create_connection(("127.0.0.1", port))  # holds the only slot
            hog.sendall(b"POST /mcp HTTP/1.1\r\n")
            import time
            time.sleep(0.2)
            extra = socket.create_connection(("127.0.0.1", port), timeout=3)
            extra.sendall(b"GET /mcp HTTP/1.1\r\nHost: x\r\n\r\n")
            try:
                data = extra.recv(100)
            except ConnectionResetError:
                data = b""
            self.assertEqual(data, b"")  # closed without a response
            extra.close()
            hog.close()
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()