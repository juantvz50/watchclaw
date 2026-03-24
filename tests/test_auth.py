from __future__ import annotations

import unittest

from watchclaw.auth import AuthLogCursor, parse_auth_log_lines, parse_journal_output


class AuthParsingTest(unittest.TestCase):
    def test_parse_journal_output_extracts_ssh_signals_and_cursor(self) -> None:
        output = "\n".join(
            [
                '{"__CURSOR":"cursor-1","SYSLOG_IDENTIFIER":"sshd","MESSAGE":"Accepted publickey for jc from 1.2.3.4 port 5555 ssh2"}',
                '{"__CURSOR":"cursor-2","SYSLOG_IDENTIFIER":"sshd","MESSAGE":"Invalid user admin from 5.6.7.8 port 2222"}',
                '{"__CURSOR":"cursor-3","SYSLOG_IDENTIFIER":"sshd","MESSAGE":"Failed password for root from 9.9.9.9 port 22 ssh2"}',
                '{"__CURSOR":"cursor-4","SYSLOG_IDENTIFIER":"sshd","MESSAGE":"Failed password for root from 9.9.9.9 port 23 ssh2"}',
                '{"__CURSOR":"cursor-5","SYSLOG_IDENTIFIER":"sshd","MESSAGE":"Failed password for root from 9.9.9.9 port 24 ssh2"}',
            ]
        )
        signals, cursor = parse_journal_output(output)
        self.assertEqual(cursor, "cursor-5")
        self.assertEqual(sorted(signal.kind for signal in signals), ["ssh_failed_login_burst", "ssh_invalid_user", "ssh_login_success"])

        success = next(signal for signal in signals if signal.kind == "ssh_login_success")
        self.assertEqual(success.details["username"], "jc")
        self.assertEqual(success.details["auth_method"], "publickey")

        burst = next(signal for signal in signals if signal.kind == "ssh_failed_login_burst")
        self.assertEqual(burst.details["attempt_count"], 3)
        self.assertEqual(burst.details["source_ip"], "9.9.9.9")

    def test_parse_auth_log_lines_filters_non_ssh_and_builds_invalid_user(self) -> None:
        lines = [
            "Mar 23 18:00:00 host sshd[1]: Invalid user oracle from 10.0.0.2 port 2200",
            "Mar 23 18:00:01 host CRON[2]: pam_unix(cron:session): session opened",
        ]
        signals = parse_auth_log_lines(lines, source="logfile:/var/log/auth.log")
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].kind, "ssh_invalid_user")
        self.assertEqual(signals[0].details["username"], "oracle")

    def test_auth_cursor_defaults_are_stable(self) -> None:
        cursor = AuthLogCursor()
        self.assertEqual(cursor.to_dict()["file_offset"], 0)
        self.assertIsNone(cursor.journal_cursor)


if __name__ == "__main__":
    unittest.main()
