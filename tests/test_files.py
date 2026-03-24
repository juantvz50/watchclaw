from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
