from __future__ import annotations

import io
import json
import tempfile
import unittest
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unittest.mock import patch

from watchclaw.cli import main
from watchclaw.delivery import (
    DELIVERY_STATUS_PREPARED,
    DELIVERY_STATUS_SENT,
    decide_telegram_delivery,
    load_delivery_state,
    prepare_pending_telegram_deliveries,
)


class TelegramDeliveryTest(unittest.TestCase):
    def test_default_delivery_policy_includes_ssh_success_and_warning_security_events(self) -> None:
        info_decision = decide_telegram_delivery({"kind": "ssh_login_success", "severity": "info"})
        warning_decision = decide_telegram_delivery({"kind": "ssh_invalid_user", "severity": "warning"})
        self.assertTrue(info_decision.should_notify)
        self.assertIn("operator-notifiable", info_decision.reason)
        self.assertTrue(warning_decision.should_notify)

    def test_prepare_pending_delivery_marks_operator_notifiable_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            events = [
                {
                    "event_id": "evt-warning",
                    "kind": "ssh_invalid_user",
                    "severity": "warning",
                    "host_id": "jc-server",
                    "observed_at": "2026-03-28T16:05:00Z",
                    "summary": "SSH invalid user attempt for oracle from 10.0.0.2",
                    "details": {"username": "oracle", "source_ip": "10.0.0.2", "source_port": 2200},
                    "explain": {"source": "journalctl", "comparison": "matched Invalid user pattern"},
                    "dedupe_key": "ssh_invalid_user:oracle:10.0.0.2",
                },
                {
                    "event_id": "evt-info",
                    "kind": "ssh_login_success",
                    "severity": "info",
                    "host_id": "jc-server",
                    "observed_at": "2026-03-28T16:06:00Z",
                    "summary": "SSH login succeeded for jc from 10.0.0.3",
                    "details": {"username": "jc", "source_ip": "10.0.0.3", "auth_method": "publickey"},
                    "explain": {"source": "journalctl", "comparison": "matched Accepted pattern"},
                    "dedupe_key": "ssh_login_success:jc:10.0.0.3:publickey",
                },
            ]
            events_path = base_dir / "events.jsonl"
            events_path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")

            prepared = prepare_pending_telegram_deliveries(base_dir=base_dir, host_id="jc-server")
            self.assertEqual(prepared["prepared_count"], 2)
            self.assertEqual([delivery["event_id"] for delivery in prepared["deliveries"]], ["evt-warning", "evt-info"])
            self.assertIn("SSH INVALID USER", prepared["deliveries"][0]["payload"]["text"])
            self.assertIn("SSH LOGIN SUCCESS", prepared["deliveries"][1]["payload"]["text"])

            state = load_delivery_state(base_dir / "delivery-state.json")
            channel_events = state["channels"]["telegram"]["events"]
            self.assertEqual(channel_events["evt-warning"]["status"], DELIVERY_STATUS_PREPARED)
            self.assertEqual(channel_events["evt-info"]["status"], DELIVERY_STATUS_PREPARED)

            second = prepare_pending_telegram_deliveries(base_dir=base_dir, host_id="jc-server")
            self.assertEqual(second["prepared_count"], 0)

    def test_cli_prepare_and_ack_flow_updates_terminal_delivery_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir) / "state"
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(json.dumps({"host_id": "jc-server", "storage": {"base_dir": str(base_dir)}}), encoding="utf-8")
            event = {
                "event_id": "evt-ack",
                "kind": "watched_file_deleted",
                "severity": "critical",
                "host_id": "jc-server",
                "observed_at": "2026-03-28T16:07:00Z",
                "summary": "Watched file deleted: /etc/sudoers",
                "details": {"path": "/etc/sudoers"},
                "explain": {"source": "files.snapshot", "comparison": "file existed in previous baseline, absent from current snapshot"},
                "dedupe_key": "watched_file_deleted:/etc/sudoers",
            }
            base_dir.mkdir(parents=True, exist_ok=True)
            (base_dir / "events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")

            prepare_stdout = io.StringIO()
            with patch("sys.argv", ["watchclaw", "prepare-telegram-delivery", "--config", str(config_path)]), redirect_stdout(prepare_stdout):
                main()
            prepared_payload = json.loads(prepare_stdout.getvalue())
            self.assertEqual(prepared_payload["prepared_count"], 1)
            batch_id = prepared_payload["batch_id"]

            ack_stdout = io.StringIO()
            with patch(
                "sys.argv",
                [
                    "watchclaw",
                    "ack-telegram-delivery",
                    "--config",
                    str(config_path),
                    "--batch-id",
                    batch_id,
                    "--status",
                    "sent",
                    "--reason",
                    "delivered by integration test",
                ],
            ), redirect_stdout(ack_stdout):
                main()
            ack_payload = json.loads(ack_stdout.getvalue())
            self.assertEqual(ack_payload["delivery_status"], DELIVERY_STATUS_SENT)
            self.assertEqual(ack_payload["updated_count"], 1)

            state = load_delivery_state(base_dir / "delivery-state.json")
            self.assertEqual(state["channels"]["telegram"]["events"]["evt-ack"]["status"], DELIVERY_STATUS_SENT)
            self.assertEqual(state["channels"]["telegram"]["events"]["evt-ack"]["reason"], "delivered by integration test")


if __name__ == "__main__":
    unittest.main()
