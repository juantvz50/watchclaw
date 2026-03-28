from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SCHEMA_VERSION = 1

DEFAULT_WATCHED_FILE_PATHS = (
    "/etc/ssh/sshd_config",
    "/etc/ssh/sshd_config.d/*.conf",
    "/etc/passwd",
    "/etc/group",
    "/etc/shadow",
    "/etc/gshadow",
    "/etc/sudoers",
    "/etc/sudoers.d/*",
    "/etc/crontab",
    "/etc/cron.d/*",
    "/root/.ssh/authorized_keys",
    "/home/*/.ssh/authorized_keys",
)


@dataclass(frozen=True, order=True)
class ListenerRecord:
    proto: str
    local_address: str
    local_port: int
    process_name: str | None = None
    pid: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WatchClawConfig:
    host_id: str
    base_dir: str
    listeners_enabled: bool = True
    listeners_command: tuple[str, ...] = ("ss", "-ltnup")
    listener_ignore_process_names: tuple[str, ...] = ()
    listener_ignore_local_ports: tuple[int, ...] = ()
    watched_files: tuple[str, ...] = ()
    auth_enabled: bool = True
    auth_journal_command: tuple[str, ...] = (
        "journalctl",
        "-q",
        "-o",
        "json",
        "--no-pager",
    )
    auth_log_paths: tuple[str, ...] = ("/var/log/auth.log", "/var/log/secure")
    telegram_delivery_inline: bool = True


DEFAULT_CONFIG = {
    "host_id": "localhost",
    "storage": {"base_dir": "/var/lib/watchclaw"},
    "collection": {
        "listeners": {
            "enabled": True,
            "command": ["ss", "-ltnup"],
            "ignore_process_names": [],
            "ignore_local_ports": [],
        },
        "files": {"paths": list(DEFAULT_WATCHED_FILE_PATHS)},
        "auth": {
            "enabled": True,
            "journal_command": ["journalctl", "-q", "-o", "json", "--no-pager"],
            "log_paths": ["/var/log/auth.log", "/var/log/secure"],
        },
    },
    "runtime": {
        "mode": "timer",
        "delivery": {
            "telegram_inline": True,
        },
    },
}
