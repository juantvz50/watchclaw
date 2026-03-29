from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, build_default_config, dump_config, load_config, write_default_config
from .delivery import acknowledge_telegram_delivery_batch, prepare_pending_telegram_deliveries
from .engine import run_once
from .inspect import inspect_jsonl_chain
from .runtime import build_runtime_report
from .telegram import render_event_file, render_event_notification


STATUS_COMMAND = "status"
RUN_ONCE_COMMAND = "run-once"
PRINT_DEFAULT_CONFIG_COMMAND = "print-default-config"
INIT_CONFIG_COMMAND = "init-config"
INSPECT_COMMAND = "inspect"
RENDER_TELEGRAM_COMMAND = "render-telegram"
PREPARE_TELEGRAM_DELIVERY_COMMAND = "prepare-telegram-delivery"
ACK_TELEGRAM_DELIVERY_COMMAND = "ack-telegram-delivery"


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

    inspect_parser = subparsers.add_parser(INSPECT_COMMAND, help="verify local hash chains and summarize recent records")
    inspect_parser.add_argument("--config", dest="config_path")
    inspect_parser.add_argument("--tail", type=int, default=5, help="number of recent records to summarize per log")

    render_parser = subparsers.add_parser(
        RENDER_TELEGRAM_COMMAND,
        help="render WatchClaw events into Telegram-ready message payloads without sending them",
    )
    render_parser.add_argument("--event-file", help="JSONL file containing WatchClaw event objects")
    render_parser.add_argument("--event-json", help="single WatchClaw event object as JSON")

    prepare_parser = subparsers.add_parser(
        PREPARE_TELEGRAM_DELIVERY_COMMAND,
        help="select unsent notification-worthy events, render Telegram payloads, and mark them prepared locally",
    )
    prepare_parser.add_argument("--config", dest="config_path")
    prepare_parser.add_argument("--limit", type=int, default=None, help="maximum number of events to prepare")
    prepare_parser.add_argument(
        "--include-prepared",
        action="store_true",
        help="re-include events already marked prepared but not yet acknowledged",
    )

    ack_parser = subparsers.add_parser(
        ACK_TELEGRAM_DELIVERY_COMMAND,
        help="mark a prepared Telegram delivery batch as sent or failed after an external transport step",
    )
    ack_parser.add_argument("--config", dest="config_path")
    ack_parser.add_argument("--batch-id", required=True, help="delivery batch identifier returned by prepare-telegram-delivery")
    ack_parser.add_argument("--status", required=True, choices=["sent", "failed"], help="terminal delivery state to record")
    ack_parser.add_argument("--event-id", dest="event_ids", action="append", default=[], help="limit the acknowledgement to one or more event ids")
    ack_parser.add_argument("--reason", help="optional operator/integration note recorded in delivery state")

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
        report = build_runtime_report(
            config_path=str(Path(getattr(args, "config_path", None) or DEFAULT_CONFIG_PATH)),
            base_dir=config.base_dir,
            host_id=config.host_id,
        )
        report.update(
            {
                "listeners_enabled": config.listeners_enabled,
                "watched_files": list(config.watched_files),
                "auth_enabled": config.auth_enabled,
                "telegram_delivery_inline": config.telegram_delivery_inline,
            }
        )
        print(json.dumps(report))
        return

    if command == INSPECT_COMMAND:
        base_dir = Path(config.base_dir)
        payload = {
            "status": "ok",
            "host_id": config.host_id,
            "base_dir": str(base_dir),
            "logs": {
                "events": inspect_jsonl_chain(base_dir / "events.jsonl", tail=max(args.tail, 0)),
                "actions": inspect_jsonl_chain(base_dir / "actions.jsonl", tail=max(args.tail, 0)),
            },
        }
        print(json.dumps(payload))
        return

    if command == RENDER_TELEGRAM_COMMAND:
        if bool(args.event_file) == bool(args.event_json):
            print("watchclaw: pass exactly one of --event-file or --event-json", file=sys.stderr)
            raise SystemExit(1)
        if args.event_file:
            print(json.dumps(render_event_file(args.event_file)))
            return
        print(json.dumps(render_event_notification(json.loads(args.event_json))))
        return

    if command == PREPARE_TELEGRAM_DELIVERY_COMMAND:
        print(
            json.dumps(
                prepare_pending_telegram_deliveries(
                    base_dir=Path(config.base_dir),
                    host_id=config.host_id,
                    limit=args.limit,
                    include_prepared=args.include_prepared,
                )
            )
        )
        return

    if command == ACK_TELEGRAM_DELIVERY_COMMAND:
        print(
            json.dumps(
                acknowledge_telegram_delivery_batch(
                    base_dir=Path(config.base_dir),
                    host_id=config.host_id,
                    batch_id=args.batch_id,
                    status=args.status,
                    event_ids=args.event_ids or None,
                    reason=args.reason,
                )
            )
        )
        return

    result = run_once(config)
    print(json.dumps({"status": "ok", **result}))


if __name__ == "__main__":
    main()
