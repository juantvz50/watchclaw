from __future__ import annotations

import io
import json
import tempfile
import unittest
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unittest.mock import patch

from watchclaw.cli import main
from watchclaw.telegram import build_telegram_payload, render_event_file, render_event_notification


class TelegramRenderTest(unittest.TestCase):
    def test_render_notification_for_sensitive_file_change_is_structured_and_searchable(self) -> None:
        event = {
            "schema_version": 1,
            "event_id": "evt-1",
            "kind": "sensitive_file_hash_changed",
            "severity": "critical",
            "host_id": "jc-server",
            "observed_at": "2026-03-28T16:00:00Z",
            "summary": "Sensitive file hash changed: /etc/sudoers",
            "details": {
                "path": "/etc/sudoers",
                "previous": {"sha256": "before"},
                "current": {"sha256": "after"},
            },
            "explain": {
                "source": "files.snapshot",
                "comparison": "file exists in both snapshots but content hash differs from previous baseline",
            },
            "dedupe_key": "sensitive_file_hash_changed:/etc/sudoers",
        }
        rendered = render_event_notification(event)
        text = rendered["payload"]["text"]
        self.assertEqual(rendered["channel"], "telegram")
        self.assertEqual(rendered["payload"]["parse_mode"], "HTML")
        self.assertIn("🔴 CRITICAL", text)
        self.assertIn("WATCHCLAW", text)
        self.assertIn("What happened:", text)
        self.assertIn("What WatchClaw did:", text)
        self.assertIn("Why it matters:", text)
        self.assertIn("#watchclaw", text)
        self.assertIn("#integrity", text)
        self.assertIn("#host_jc_server", text)

    def test_build_payload_escapes_html(self) -> None:
        payload = build_telegram_payload(
            {
                "event_id": "evt-2",
                "kind": "ssh_invalid_user",
                "severity": "warning",
                "host_id": "jc<server>",
                "observed_at": "2026-03-28T16:05:00Z",
                "summary": "SSH invalid user attempt for <admin> from 1.2.3.4",
                "details": {"username": "<admin>", "source_ip": "1.2.3.4"},
                "explain": {"source": "journalctl"},
                "dedupe_key": "ssh_invalid_user:<admin>:1.2.3.4",
            }
        )
        self.assertIn("&lt;admin&gt;", payload.text)
        self.assertIn("&lt;server&gt;", payload.text)
        self.assertNotIn("<admin>", payload.text)

    def test_render_event_file_reads_jsonl(self) -> None:
        event = {
            "event_id": "evt-3",
            "kind": "new_listener",
            "severity": "warning",
            "host_id": "jc-server",
            "observed_at": "2026-03-28T16:10:00Z",
            "summary": "New listening socket detected on 127.0.0.1:8080/tcp",
            "details": {"proto": "tcp", "local_address": "127.0.0.1", "local_port": 8080, "process_name": "python3", "pid": 123},
            "explain": {"source": "ss -ltnup", "comparison": "present in current snapshot, absent in previous baseline"},
            "dedupe_key": "new_listener:tcp:127.0.0.1:8080:python3",
        }
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "events.jsonl"
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            rendered = render_event_file(path)
        self.assertEqual(len(rendered), 1)
        self.assertIn("NEW LISTENER", rendered[0]["payload"]["text"])

    def test_cli_render_telegram_supports_single_event_json(self) -> None:
        event = {
            "event_id": "evt-4",
            "kind": "ssh_login_success",
            "severity": "info",
            "host_id": "jc-server",
            "observed_at": "2026-03-28T16:11:00Z",
            "summary": "SSH login succeeded for jc from 1.2.3.4",
            "details": {"username": "jc", "source_ip": "1.2.3.4", "source_port": 5555, "auth_method": "publickey"},
            "explain": {"source": "journal"},
            "dedupe_key": "ssh_login_success:jc:1.2.3.4:publickey",
        }
        stdout = io.StringIO()
        with patch("sys.argv", ["watchclaw", "render-telegram", "--event-json", json.dumps(event)]), redirect_stdout(stdout):
            main()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["channel"], "telegram")
        self.assertIn("SSH LOGIN SUCCESS", payload["payload"]["text"])

    def test_cli_render_telegram_requires_exactly_one_input_mode(self) -> None:
        stderr = io.StringIO()
        with patch("sys.argv", ["watchclaw", "render-telegram"]), redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as exc:
                main()
        self.assertEqual(exc.exception.code, 1)
        self.assertIn("exactly one", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
