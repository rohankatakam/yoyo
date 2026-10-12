"""Durable, shared cache of real provider responses. Unknown submissions never retry."""

import json
import os
import time
from pathlib import Path
from ..artifacts import digest, store_json, read_json
from ..config import settings


class Cache:
    def __init__(self):
        self.root = settings.artifact_dir / "provider-cache"
        self.root.mkdir(parents=True, exist_ok=True)
        self.events = []

    def call(self, kind, payload, execute):
        key = digest([kind, payload])
        path = self.root / f"{key}.json"
        started = time.monotonic()
        if path.exists():
            record = json.loads(path.read_text())
            if record["status"] != "completed":
                raise RuntimeError(
                    f"Provider operation {key} is {record['status']}; inspect before retry"
                )
            hit = True
        else:
            record = {
                "kind": kind,
                "request": store_json(payload),
                "status": "submitted",
            }
            # Exclusive creation prevents two processes submitting the same operation.
            with path.open("x") as stream:
                json.dump(record, stream)
            try:
                result = execute()
                record.update(
                    status="completed",
                    response=store_json(result),
                    seconds=time.monotonic() - started,
                )
            except Exception as exc:
                record.update(status="unknown_outcome", error=str(exc))
                self.write(path, record)
                raise
            self.write(path, record)
            hit = False
        result = read_json(record["response"])
        self.events.append(
            {
                "key": key,
                "kind": kind,
                "cache_hit": hit,
                "seconds": time.monotonic() - started,
                "cold_seconds": record["seconds"],
                "usage": result.get("usage", {}),
                "costDollars": result.get("costDollars"),
            }
        )
        return result

    @staticmethod
    def write(path: Path, value):
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value))
        os.replace(temporary, path)
