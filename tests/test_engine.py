from __future__ import annotations

import json
import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from unittest.mock import patch

from watchclaw.auth import AuthLogCursor, AuthSignal
from watchclaw.engine import build_auth_event, build_event, build_file_event, diff_files, diff_listeners, filter_expected_listeners, run_once
from watchclaw.files import FileRecord
from watchclaw.models import ListenerRecord, WatchClawConfig


class EngineTest(unittest.TestCase):
    def test_diff_listeners_finds_added_and_removed_records(self) -> None:
        previous = [
            ListenerRecord(proto="tcp", local_address="0.0.0.0", local_port=22, process_name="sshd", pid=100),
            ListenerRecord(proto="udp", local_address="0.0.0.0", local_port=53, process_name=None, pid=None),
        ]
        current = [
            ListenerRecord(proto="tcp", local_address="0.0.0.0", local_port=22, process_name="sshd", pid=100),
            ListenerRecord(proto="tcp", local_address="127.0.0.1", local_port=8080, process_name="python3", pid=200),
        ]
        added, removed = diff_listeners(previous, current)
        self.assertEqual(
            added,
            [ListenerRecord(proto="tcp", local_address="127.0.0.1", local_port=8080, process_name="python3", pid=200)],
        )
        self.assertEqual(
            removed,
            [ListenerRecord(proto="udp", local_address="0.0.0.0", local_port=53, process_name=None, pid=None)],
        )

    def test_diff_files_finds_created_deleted_and_changed(self) -> None:
        previous = [
            FileRecord(path="/a", exists=True, sha256="old-a", size=1, mode=33188, mtime_ns=1),
            FileRecord(path="/b", exists=True, sha256="same", size=1, mode=33188, mtime_ns=1),
            FileRecord(path="/c", exists=False),
        ]
        current = [
            FileRecord(path="/a", exists=True, sha256="new-a", size=1, mode=33188, mtime_ns=2),
            FileRecord(path="/b", exists=False),
            FileRecord(path="/c", exists=True, sha256="new-c", size=1, mode=33188, mtime_ns=2),
        ]
        created, deleted, changed = diff_files(previous, current)
        self.assertEqual(created, [FileRecord(path="/c", exists=True, sha256="new-c", size=1, mode=33188, mtime_ns=2)])
        self.assertEqual(deleted, [FileRecord(path="/b", exists=True, sha256="same", size=1, mode=33188, mtime_ns=1)])
        self.assertEqual(
            changed,
            [
                (
                    FileRecord(path="/a", exists=True, sha256="old-a", size=1, mode=33188, mtime_ns=1),
                    FileRecord(path="/a", exists=True, sha256="new-a", size=1, mode=33188, mtime_ns=2),
                )
            ],
        )

    def test_filter_expected_listeners_suppresses_declared_noise(self) -> None:
        config = WatchClawConfig(
            host_id="jc-server",
            base_dir="/tmp/watchclaw",
            listener_ignore_process_names=("systemd-resolved",),
            listener_ignore_local_ports=(5353,),
        )
        filtered = filter_expected_listeners(
            [
                ListenerRecord(proto="udp", local_address="0.0.0.0", local_port=5353, process_name="avahi-daemon", pid=1),
                ListenerRecord(proto="tcp", local_address="127.0.0.53", local_port=53, process_name="systemd-resolved", pid=2),
                ListenerRecord(proto="tcp", local_address="127.0.0.1", local_port=8080, process_name="python3", pid=3),
            ],
            config,
        )
        self.assertEqual(
            filtered,
            [ListenerRecord(proto="tcp", local_address="127.0.0.1", local_port=8080, process_name="python3", pid=3)],
        )

    def test_build_event_matches_contract(self) -> None:
        record = ListenerRecord(proto="tcp", local_address="127.0.0.1", local_port=8080, process_name="python3", pid=200)
        event = build_event("new_listener", record, host_id="jc-server", observed_at="2026-03-23T22:00:00Z")
        self.assertEqual(event["kind"], "new_listener")
        self.assertEqual(event["severity"], "warning")
        self.assertEqual(event["host_id"], "jc-server")
        self.assertEqual(
            event["details"],
            {
                "proto": "tcp",
                "local_address": "127.0.0.1",
                "local_port": 8080,
                "process_name": "python3",
                "pid": 200,
            },
        )
        self.assertEqual(
            event["explain"],
            {
                "source": "ss -ltnup",
                "comparison": "present in current snapshot, absent in previous baseline",
            },
        )
        self.assertEqual(event["dedupe_key"], "new_listener:tcp:127.0.0.1:8080:python3")

    def test_build_file_event_matches_contract(self) -> None:
        before = FileRecord(path="/etc/sudoers", exists=True, sha256="before", size=10, mode=33184, mtime_ns=1)
        after = FileRecord(path="/etc/sudoers", exists=True, sha256="after", size=11, mode=33184, mtime_ns=2)
        event = build_file_event(
            "sensitive_file_hash_changed",
            host_id="jc-server",
            observed_at="2026-03-23T22:00:00Z",
            previous=before,
            current=after,
        )
        self.assertEqual(event["kind"], "sensitive_file_hash_changed")
        self.assertEqual(event["severity"], "critical")
        self.assertEqual(event["host_id"], "jc-server")
        self.assertEqual(event["details"]["path"], "/etc/sudoers")
        self.assertEqual(event["details"]["previous"]["sha256"], "before")
        self.assertEqual(event["details"]["current"]["sha256"], "after")
        self.assertEqual(event["explain"]["source"], "files.snapshot")
        self.assertEqual(event["dedupe_key"], "sensitive_file_hash_changed:/etc/sudoers")

    def test_build_auth_event_matches_contract(self) -> None:
        event = build_auth_event(
            "ssh_login_success",
            details={"username": "jc", "source_ip": "1.2.3.4"},
            host_id="jc-server",
            observed_at="2026-03-23T22:00:00Z",
            explain={"source": "journal"},
            summary="SSH login succeeded for jc from 1.2.3.4",
            dedupe_key="ssh_login_success:jc:1.2.3.4:publickey",
            severity="info",
        )
        self.assertEqual(event["kind"], "ssh_login_success")
        self.assertEqual(event["severity"], "info")
        self.assertEqual(event["details"]["username"], "jc")
        self.assertEqual(event["dedupe_key"], "ssh_login_success:jc:1.2.3.4:publickey")

    def test_run_once_persists_listener_file_and_auth_state_and_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            watched_file = base_dir / "sudoers"
            watched_file.write_text("v2")

            listener_baseline = base_dir / "baselines" / "listeners.json"
            listener_baseline.parent.mkdir(parents=True, exist_ok=True)
            listener_baseline.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "captured_at": "2026-03-23T21:00:00Z",
                        "listeners": [
                            {
                                "proto": "tcp",
                                "local_address": "0.0.0.0",
                                "local_port": 22,
                                "process_name": "sshd",
                                "pid": 100,
                            }
                        ],
                    }
                )
            )
            (base_dir / "baselines" / "files.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "captured_at": "2026-03-23T21:00:00Z",
                        "files": [
                            {
                                "path": str(watched_file),
                                "exists": True,
                                "sha256": "old-hash",
                                "size": 2,
                                "mode": 33188,
                                "mtime_ns": 1,
                            },
                            {
                                "path": str(base_dir / 'deleted.txt'),
                                "exists": True,
                                "sha256": "gone",
                                "size": 1,
                                "mode": 33188,
                                "mtime_ns": 1,
                            },
                        ],
                    }
                )
            )

            config = WatchClawConfig(
                host_id="jc-server",
                base_dir=str(base_dir),
                listeners_enabled=True,
                listeners_command=("ss", "-ltnup"),
                watched_files=(str(watched_file), str(base_dir / "deleted.txt"), str(base_dir / "created.txt")),
                auth_enabled=True,
            )

            created_file = FileRecord(path=str(base_dir / "created.txt"), exists=True, sha256="new", size=3, mode=33188, mtime_ns=3)
            current_file = FileRecord(path=str(watched_file), exists=True, sha256="new-hash", size=2, mode=33188, mtime_ns=2)
            missing_file = FileRecord(path=str(base_dir / "deleted.txt"), exists=False)
            with patch(
                "watchclaw.engine.collect_listener_snapshot",
                return_value=[ListenerRecord(proto="tcp", local_address="127.0.0.1", local_port=8080, process_name="python3", pid=200)],
            ), patch(
                "watchclaw.engine.collect_file_snapshot",
                return_value=[created_file, missing_file, current_file],
            ), patch(
                "watchclaw.engine.collect_auth_signals",
                return_value=(
                    [
                        AuthSignal(
                            kind="ssh_login_success",
                            details={"username": "jc", "source_ip": "1.2.3.4"},
                            explain={"source": "journal"},
                            summary="SSH login succeeded for jc from 1.2.3.4",
                            dedupe_key="ssh_login_success:jc:1.2.3.4:publickey",
                            severity="info",
                        )
                    ],
                    AuthLogCursor(source="journal", journal_cursor="cursor-5"),
                ),
            ):
                result = run_once(config)

            self.assertEqual(result["listeners"], 1)
            self.assertEqual(result["files"], 3)
            self.assertEqual(result["auth"], 1)
            self.assertEqual(result["events"], 6)
            self.assertIn("delivery", result)
            self.assertEqual(result["delivery"]["prepared_count"], 6)
            self.assertEqual(result["delivery"]["skipped_count"], 0)

            events = [json.loads(line) for line in (base_dir / "events.jsonl").read_text().splitlines()]
            self.assertEqual(
                sorted(event["kind"] for event in events),
                [
                    "listener_removed",
                    "new_listener",
                    "sensitive_file_hash_changed",
                    "ssh_login_success",
                    "watched_file_created",
                    "watched_file_deleted",
                ],
            )
            files_baseline = json.loads((base_dir / "baselines" / "files.json").read_text())
            self.assertEqual(len(files_baseline["files"]), 3)
            state = json.loads((base_dir / "state.json").read_text())
            self.assertEqual(state["host_id"], "jc-server")
            self.assertEqual(state["auth_cursor"]["journal_cursor"], "cursor-5")
            actions = [json.loads(line) for line in (base_dir / "actions.jsonl").read_text().splitlines()]
            self.assertEqual([action["action"] for action in actions], [
                "write_listener_baseline",
                "write_file_baseline",
                "append_events",
                "write_state",
            ])
            self.assertIsNone(actions[0]["previous_record_hash"])
            self.assertEqual(actions[1]["previous_record_hash"], actions[0]["record_hash"])

            delivery_state = json.loads((base_dir / "delivery-state.json").read_text())
            delivery_statuses = {entry["kind"]: entry["status"] for entry in delivery_state["channels"]["telegram"]["events"].values()}
            self.assertEqual(delivery_statuses["ssh_login_success"], "prepared")
            self.assertEqual(delivery_statuses["watched_file_deleted"], "prepared")


if __name__ == "__main__":
    unittest.main()
