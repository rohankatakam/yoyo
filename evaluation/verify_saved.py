"""Evaluate unchanged saved claims against their original transcript, without writes."""

import json
from pathlib import Path
from yoyo.claim_models import Candidate
from yoyo.verify_claims import verify
from yoyo.resolution.providers import Research
from yoyo.telemetry import Trace
from yoyo.artifacts import stable


def main():
    source = json.loads(Path("artifacts/packet-eval-source.json").read_text())
    claims = json.loads(Path("artifacts/packet-eval-claims.json").read_text())
    trace = Trace(
        stable("packet-claim-verification-v2"), {"evaluation": "saved-claims"}
    )
    research = Research(trace)
    output = Path("artifacts/packet-claim-verification-v2.json")
    rows = json.loads(output.read_text()) if output.exists() else []
    try:
        for raw in claims[len(rows) :]:
            claim = Candidate.model_validate(raw)
            verdict, packet = verify(claim, source, research)
            rows.append(
                {"claim": raw, "packet": packet, "verdict": verdict.model_dump()}
            )
            output.write_text(json.dumps(rows, indent=2))
            print(verdict.outcome, claim.text, flush=True)
        trace.finish({"claims": len(rows)})
        print("TRACE", trace.url, flush=True)
    except Exception as exc:
        trace.finish(error=str(exc))
        raise


if __name__ == "__main__":
    main()
