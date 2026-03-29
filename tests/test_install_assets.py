from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


class InstallAssetsTest(unittest.TestCase):
    def test_install_script_has_valid_bash_syntax(self) -> None:
        script_path = ROOT / "scripts" / "install.sh"
        completed = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_upgrade_script_has_valid_bash_syntax(self) -> None:
        script_path = ROOT / "scripts" / "upgrade.sh"
        completed = subprocess.run(["bash", "-n", str(script_path)], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_service_unit_is_a_render_template(self) -> None:
        service_path = ROOT / "systemd" / "watchclaw.service"
        content = service_path.read_text(encoding="utf-8")
        self.assertIn("@WATCHCLAW_BIN@", content)
        self.assertIn("@WATCHCLAW_CONFIG@", content)


if __name__ == "__main__":
    unittest.main()
