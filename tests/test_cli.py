from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unittest.mock import patch

from watchclaw.audit import append_jsonl_record
from watchclaw.cli import main


class CliTest(unittest.TestCase):
    def test_print_default_config_emits_json(self) -> None:
        stdout = io.StringIO()
        with patch("sys.argv", ["watchclaw", "print-default-config", "--host-id", "jc-server"]), redirect_stdout(stdout):
            main()
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["host_id"], "jc-server")

    def test_init_config_writes_file_and_rejects_existing_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "config.json"

            first_stdout = io.StringIO()
            with patch(
                "sys.argv",
                ["watchclaw", "init-config", "--output", str(output_path), "--host-id", "jc-server", "--watch-file", "/etc/sudoers"],
            ), redirect_stdout(first_stdout):
                main()

            payload = json.loads(output_path.read_text())
            self.assertEqual(payload["host_id"], "jc-server")
            self.assertEqual(payload["collection"]["files"]["paths"], ["/etc/sudoers"])

            second_stderr = io.StringIO()
            with patch("sys.argv", ["watchclaw", "init-config", "--output", str(output_path)]), redirect_stderr(second_stderr):
                with self.assertRaises(SystemExit) as exc:
                    main()
            self.assertEqual(exc.exception.code, 1)
            self.assertIn("Config already exists", second_stderr.getvalue())

    def test_status_uses_config_file_and_emits_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "host_id": "jc-server",
                        "storage": {"base_dir": "/tmp/watchclaw"},
                        "collection": {
                            "files": {"paths": ["/etc/sudoers"]},
                        },
                    }
                )
            )
            stdout = io.StringIO()
            with patch("sys.argv", ["watchclaw", "status", "--config", str(config_path)]), redirect_stdout(stdout):
                main()
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["host_id"], "jc-server")
            self.assertEqual(payload["watched_files"], ["/etc/sudoers"])
            self.assertEqual(payload["config_path"], str(config_path))
            self.assertIn("package_version", payload)
            self.assertIn("installed_distribution_version", payload)
            self.assertIn("python_executable", payload)
            self.assertIn("module_path", payload)
            self.assertIn("capabilities", payload)
            self.assertTrue(payload["capabilities"]["listener_monitoring"])

    def test_inspect_verifies_logs_and_summarizes_tail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "state"
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "host_id": "jc-server",
                        "storage": {"base_dir": str(base_dir)},
                        "collection": {
                            "files": {"paths": ["/etc/sudoers"]},
                        },
                    }
                )
            )
            append_jsonl_record(base_dir / "actions.jsonl", {"kind": "watchclaw_action", "action": "write_state", "recorded_at": "2026-03-28T00:00:00Z"})
            append_jsonl_record(base_dir / "events.jsonl", {"kind": "new_listener", "summary": "listener appeared", "severity": "warning", "observed_at": "2026-03-28T00:01:00Z"})

            stdout = io.StringIO()
            with patch("sys.argv", ["watchclaw", "inspect", "--config", str(config_path), "--tail", "1"]), redirect_stdout(stdout):
                main()
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["logs"]["actions"]["verified"])
            self.assertTrue(payload["logs"]["events"]["verified"])
            self.assertEqual(len(payload["logs"]["actions"]["tail"]), 1)
            self.assertEqual(payload["logs"]["events"]["tail"][0]["kind"], "new_listener")

    def test_inspect_flags_chain_break(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "state"
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(json.dumps({"host_id": "jc-server", "storage": {"base_dir": str(base_dir)}}))
            log_path = base_dir / "actions.jsonl"
            append_jsonl_record(log_path, {"kind": "watchclaw_action", "action": "write_state", "recorded_at": "2026-03-28T00:00:00Z"})
            lines = log_path.read_text().splitlines()
            bad = json.loads(lines[0])
            bad["previous_record_hash"] = "tampered"
            lines.append(json.dumps(bad))
            log_path.write_text("\n".join(lines) + "\n")

            stdout = io.StringIO()
            with patch("sys.argv", ["watchclaw", "inspect", "--config", str(config_path)]), redirect_stdout(stdout):
                main()
            payload = json.loads(stdout.getvalue())
            self.assertFalse(payload["logs"]["actions"]["verified"])
            self.assertTrue(payload["logs"]["actions"]["obvious_truncation_or_reset"])
            self.assertIn("chain_link_mismatch", {issue["code"] for issue in payload["logs"]["actions"]["issues"]})


if __name__ == "__main__":
    unittest.main()
