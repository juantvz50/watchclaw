from __future__ import annotations

import glob
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, order=True)
class FileRecord:
    path: str
    exists: bool
    sha256: str | None = None
    size: int | None = None
    mode: int | None = None
    mtime_ns: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "exists": self.exists,
            "sha256": self.sha256,
            "size": self.size,
            "mode": self.mode,
            "mtime_ns": self.mtime_ns,
        }


def _expand_snapshot_paths(paths: list[str] | tuple[str, ...]) -> list[str]:
    expanded: set[str] = set()
    for raw_path in paths:
        candidate = str(raw_path)
        matches = glob.glob(candidate)
        if matches:
            expanded.update(str(Path(match)) for match in matches)
            continue
        if glob.has_magic(candidate):
            continue
        expanded.add(str(Path(candidate)))
    return sorted(expanded)


def collect_file_snapshot(paths: list[str] | tuple[str, ...]) -> list[FileRecord]:
    records: list[FileRecord] = []
    for raw_path in _expand_snapshot_paths(paths):
        path = Path(raw_path)
        if not path.exists():
            records.append(FileRecord(path=str(path), exists=False))
            continue
        stat = path.stat()
        records.append(
            FileRecord(
                path=str(path),
                exists=True,
                sha256=sha256_file(path),
                size=stat.st_size,
                mode=stat.st_mode,
                mtime_ns=stat.st_mtime_ns,
            )
        )
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
