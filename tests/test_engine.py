import unittest

from watchclaw.engine import build_event, diff_listeners
from watchclaw.models import ListenerRecord


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


if __name__ == "__main__":
    unittest.main()
