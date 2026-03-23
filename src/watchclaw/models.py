from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


SCHEMA_VERSION = 1


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


DEFAULT_CONFIG = {
    "host_id": "localhost",
    "storage": {"base_dir": "/var/lib/watchclaw"},
    "collection": {"listeners": {"enabled": True, "command": ["ss", "-ltnup"]}},
    "runtime": {"mode": "timer"},
}
