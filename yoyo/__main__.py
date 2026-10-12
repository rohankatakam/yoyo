import argparse
import json

from .pipeline import process

parser = argparse.ArgumentParser(
    description="Process a complete real podcast transcript"
)
parser.add_argument("transcript")
parser.add_argument("--metadata", required=True)
parser.add_argument("--episode-id", required=True)
parser.add_argument("--resume")
parser.add_argument("--max-calls", type=int, default=30)
parser.add_argument("--matching", choices=["lexical", "hybrid"], default="lexical")
parser.add_argument("--no-trace", action="store_true")
args = parser.parse_args()
print(
    json.dumps(
        process(
            args.transcript,
            args.metadata,
            args.episode_id,
            resume=args.resume,
            max_calls=args.max_calls,
            tracing=not args.no_trace,
            matching=args.matching,
        ),
        indent=2,
    )
)
