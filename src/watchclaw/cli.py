from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, build_default_config, dump_config, load_config, write_default_config
from .engine import run_once


STATUS_COMMAND = "status"
RUN_ONCE_COMMAND = "run-once"
PRINT_DEFAULT_CONFIG_COMMAND = "print-default-config"
INIT_CONFIG_COMMAND = "init-config"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="watchclaw")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = False

    status_parser = subparsers.add_parser(STATUS_COMMAND, help="show resolved runtime configuration")
    status_parser.add_argument("--config", dest="config_path")

    run_once_parser = subparsers.add_parser(RUN_ONCE_COMMAND, help="collect one snapshot cycle and append events")
    run_once_parser.add_argument("--config", dest="config_path")

    print_parser = subparsers.add_parser(PRINT_DEFAULT_CONFIG_COMMAND, help="print a default config JSON document")
    add_config_generation_args(print_parser, include_output=False)

    init_parser = subparsers.add_parser(INIT_CONFIG_COMMAND, help="write a default config file for installation")
    add_config_generation_args(init_parser, include_output=True)

    return parser


def add_config_generation_args(parser: argparse.ArgumentParser, *, include_output: bool) -> None:
    if include_output:
        parser.add_argument("--output", default=str(DEFAULT_CONFIG_PATH), help="destination path for generated config")
        parser.add_argument("--force", action="store_true", help="overwrite an existing config file")
    parser.add_argument("--host-id", help="stable host identifier to place into the generated config")
    parser.add_argument("--base-dir", help="storage.base_dir value for the generated config")
    parser.add_argument(
        "--watch-file",
        dest="watched_files",
        action="append",
        default=[],
        help="append a watched file path; may be passed multiple times",
    )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    command = args.command or STATUS_COMMAND

    if command == PRINT_DEFAULT_CONFIG_COMMAND:
        print(
            dump_config(
                build_default_config(
                    host_id=args.host_id,
                    base_dir=args.base_dir,
                    watched_files=args.watched_files or None,
                )
            ),
            end="",
        )
        return

    if command == INIT_CONFIG_COMMAND:
        try:
            written_path = write_default_config(
                args.output,
                force=args.force,
                host_id=args.host_id,
                base_dir=args.base_dir,
                watched_files=args.watched_files or None,
            )
        except FileExistsError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from exc
        print(f"watchclaw: wrote config {written_path}")
        return

    config = load_config(getattr(args, "config_path", None))

    if command == STATUS_COMMAND:
        print(
            json.dumps(
                {
                    "status": "ready",
                    "host_id": config.host_id,
                    "base_dir": config.base_dir,
                    "listeners_enabled": config.listeners_enabled,
                    "watched_files": list(config.watched_files),
                    "auth_enabled": config.auth_enabled,
                    "config_path": str(Path(getattr(args, "config_path", None) or DEFAULT_CONFIG_PATH)),
                }
            )
        )
        return

    result = run_once(config)
    print(json.dumps({"status": "ok", **result}))


if __name__ == "__main__":
    main()
