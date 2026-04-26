from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def ensure_run_dirs(output_dir: Path, client_id: str, month: str) -> dict[str, Path]:
    root = output_dir / client_id / month
    dirs = {
        "root": root,
        "raw": root / "raw",
        "processed": root / "processed",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

