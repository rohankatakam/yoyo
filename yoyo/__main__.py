import argparse
import json
from pathlib import Path
from .contracts import Bundle
from .service import import_bundle

parser = argparse.ArgumentParser()
parser.add_argument("command", choices=["import-reference"])
parser.add_argument("--file", type=Path, default=Path("fixtures/felins-reference.json"))
parser.add_argument("--no-trace", action="store_true")
args = parser.parse_args()
print(
    json.dumps(
        import_bundle(
            Bundle.model_validate_json(args.file.read_text()), tracing=not args.no_trace
        ),
        indent=2,
    )
)
