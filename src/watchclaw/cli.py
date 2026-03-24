from __future__ import annotations

import argparse
import json

from .config import load_config
from .engine import run_once


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="watchclaw")
    parser.add_argument("command", nargs="?", default="status", choices=["status", "run-once"])
    parser.add_argument("--config", dest="config_path")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config_path)

    if args.command == "status":
        print(f"watchclaw: ready host_id={config.host_id} base_dir={config.base_dir} auth_enabled={config.auth_enabled}")
        return

    result = run_once(config)
    print(json.dumps({"status": "ok", **result}))


if __name__ == "__main__":
    main()
