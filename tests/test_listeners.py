import unittest

from watchclaw.listeners import extract_process, normalize_address, parse_ss_output, split_address_port
from watchclaw.models import ListenerRecord


class ListenerHelpersTest(unittest.TestCase):
    def test_split_address_port_handles_ipv4_and_ipv6(self) -> None:
        self.assertEqual(split_address_port("0.0.0.0:22"), ("0.0.0.0", 22))
        self.assertEqual(split_address_port("[::]:443"), ("::", 443))

    def test_normalize_address_strips_interface_suffix(self) -> None:
        self.assertEqual(normalize_address("127.0.0.53%lo"), "127.0.0.53")

    def test_extract_process_reads_name_and_pid(self) -> None:
        self.assertEqual(extract_process('users:(("openclaw-gatewa",pid=955,fd=25))'), ("openclaw-gatewa", 955))
        self.assertEqual(extract_process(""), (None, None))

    def test_parse_ss_output_returns_stable_deduplicated_records(self) -> None:
        output = """Netid State Recv-Q Send-Q Local Address:Port Peer Address:Port Process
udp   UNCONN 0      0      0.0.0.0:5353      0.0.0.0:* users:((\"svc\",pid=10,fd=25))
udp   UNCONN 0      0      0.0.0.0:5353      0.0.0.0:* users:((\"svc\",pid=10,fd=26))
tcp   LISTEN 0      511    [::]:22           [::]:*
"""
        self.assertEqual(
            parse_ss_output(output),
            [
                ListenerRecord(proto="tcp", local_address="::", local_port=22, process_name=None, pid=None),
                ListenerRecord(proto="udp", local_address="0.0.0.0", local_port=5353, process_name="svc", pid=10),
            ],
        )


if __name__ == "__main__":
    unittest.main()
