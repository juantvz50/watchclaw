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


from watchclaw.config import build_default_config, load_config, write_default_config
from watchclaw.models import DEFAULT_WATCHED_FILE_PATHS


class ConfigTest(unittest.TestCase):
    def test_build_default_config_includes_operator_first_watched_files(self) -> None:
        config = build_default_config(host_id="jc-server")
        self.assertEqual(tuple(config["collection"]["files"]["paths"]), DEFAULT_WATCHED_FILE_PATHS)

    def test_build_default_config_accepts_overrides(self) -> None:
        config = build_default_config(
            host_id="jc-server",
            base_dir="/tmp/watchclaw",
            watched_files=["/etc/ssh/sshd_config", "/etc/sudoers", "/etc/sudoers"],
        )
        self.assertEqual(config["host_id"], "jc-server")
        self.assertEqual(config["storage"]["base_dir"], "/tmp/watchclaw")
        self.assertEqual(config["collection"]["files"]["paths"], ["/etc/ssh/sshd_config", "/etc/sudoers"])

    def test_write_default_config_refuses_to_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = Path(tmp_dir) / "config.json"
            write_default_config(output, host_id="first")
            with self.assertRaises(FileExistsError):
                write_default_config(output, host_id="second")
            write_default_config(output, host_id="second", force=True)
            payload = json.loads(output.read_text())
            self.assertEqual(payload["host_id"], "second")

    def test_load_config_merges_partial_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_path = Path(tmp_dir) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "host_id": "jc-server",
                        "storage": {"base_dir": "/tmp/watchclaw"},
                        "collection": {
                            "files": {"paths": ["/etc/sudoers"]},
                            "auth": {"enabled": False},
                        },
                        "runtime": {"delivery": {"telegram_inline": False}},
                    }
                )
            )
            config = load_config(config_path)
            self.assertEqual(config.host_id, "jc-server")
            self.assertEqual(config.base_dir, "/tmp/watchclaw")
            self.assertEqual(config.watched_files, ("/etc/sudoers",))
            self.assertFalse(config.auth_enabled)
            self.assertTrue(config.listeners_enabled)
            self.assertFalse(config.telegram_delivery_inline)


if __name__ == "__main__":
    unittest.main()
