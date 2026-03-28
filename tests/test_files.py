from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from watchclaw.files import collect_file_snapshot


class FileCollectorTest(unittest.TestCase):
    def test_collect_file_snapshot_captures_existing_and_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            existing = base / "existing.txt"
            existing.write_text("hello")
            missing = base / "missing.txt"

            records = collect_file_snapshot([str(missing), str(existing)])

            self.assertEqual(records[0].path, str(existing))
            self.assertTrue(records[0].exists)
            self.assertEqual(records[0].size, 5)
            self.assertIsNotNone(records[0].sha256)

            self.assertEqual(records[1].path, str(missing))
            self.assertFalse(records[1].exists)
            self.assertIsNone(records[1].sha256)
            self.assertIsNone(records[1].size)

    def test_collect_file_snapshot_expands_globs_without_emitting_missing_glob_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            ssh_dir = base / "home" / "alice" / ".ssh"
            ssh_dir.mkdir(parents=True)
            authorized_keys = ssh_dir / "authorized_keys"
            authorized_keys.write_text("ssh-ed25519 AAAA test")

            records = collect_file_snapshot([
                str(base / "home" / "*" / ".ssh" / "authorized_keys"),
                str(base / "root" / ".ssh" / "authorized_keys"),
                str(base / "etc" / "sudoers.d" / "*"),
            ])

            self.assertEqual([record.path for record in records], [
                str(authorized_keys),
                str(base / "root" / ".ssh" / "authorized_keys"),
            ])
            self.assertTrue(records[0].exists)
            self.assertFalse(records[1].exists)


if __name__ == "__main__":
    unittest.main()
