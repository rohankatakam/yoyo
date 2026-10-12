"""Hash-addressed files, published atomically. Raw provider data never enters Git."""

import hashlib
import json
import os
import tempfile
from uuid import NAMESPACE_URL, uuid5

from .config import settings


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def stable(*parts):
    return str(uuid5(NAMESPACE_URL, json.dumps(parts)))


def store_bytes(data, suffix="json"):
    sha = hashlib.sha256(data).hexdigest()
    root = settings.artifact_dir
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{sha}.{suffix}"
    with tempfile.NamedTemporaryFile(dir=root, delete=False) as temp:
        temp.write(data)
        temp.flush()
        os.fsync(temp.fileno())
    try:
        try:
            os.link(temp.name, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise ValueError("Stored artifact hash mismatch")
    finally:
        os.unlink(temp.name)
    return {"name": path.name, "sha256": sha}


def store_json(value):
    return store_bytes(canonical(value))


def read_bytes(ref):
    name = ref["name"]
    if name != os.path.basename(name):
        raise ValueError("Invalid artifact name")
    data = (settings.artifact_dir / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != ref["sha256"]:
        raise ValueError("Stored artifact hash mismatch")
    return data


def read_json(ref):
    return json.loads(read_bytes(ref))
