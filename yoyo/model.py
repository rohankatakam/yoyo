"""One durable operation per API submission; uncertain submissions require review."""

import json

from openai import OpenAI
from openai.lib._pydantic import to_strict_json_schema

from .artifacts import digest, read_json, store_json
from .config import settings
from .budget import reserve, finish, timeout, BudgetExhausted


def call_model(state, key, prompt, payload, output_type, trace):
    signature = digest(
        [settings.model, prompt, payload, output_type.model_json_schema()]
    )
    operation = state.progress["operations"].get(key)
    if operation:
        if operation["signature"] != signature:
            raise ValueError("Resume configuration differs from saved operation")
        if operation["status"] != "completed":
            raise RuntimeError(
                f"Operation {key} is {operation['status']}; inspect before resubmitting"
            )
        return output_type.model_validate(read_json(operation["parsed"]))
    if len(state.progress["operations"]) >= state.inputs["max_calls"]:
        raise BudgetExhausted("Model call budget exhausted")
    budget_key = state.id + ":" + key
    reserve(budget_key, "llm-" + key)
    operation = {
        "status": "submitted",
        "signature": signature,
        "input": store_json({"prompt": prompt, "payload": payload}),
    }
    state.progress["operations"][key] = operation
    state.save()
    client = OpenAI(
        api_key=settings.openai_api_key, max_retries=0, timeout=timeout(180)
    )
    try:
        with trace.span(
            key, {"model": settings.model, "input": operation["input"]}, "llm"
        ) as output:
            response = client.responses.create(
                model=settings.model,
                store=True,
                input=[
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ],
                max_output_tokens=12000,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": output_type.__name__,
                        "strict": True,
                        "schema": to_strict_json_schema(output_type),
                    }
                },
            )
            operation["raw"] = store_json(response.model_dump(mode="json"))
            finish(budget_key, response.model_dump(mode="json"))
            operation["response_id"] = response.id
            operation["usage"] = response.usage.model_dump() if response.usage else {}
            state.save()
            if response.status != "completed":
                raise ValueError(f"Model response status: {response.status}")
            parsed = output_type.model_validate_json(response.output_text)
            operation.update(status="completed", parsed=store_json(parsed.model_dump()))
            output.update(
                response_id=response.id,
                usage=operation["usage"],
                usage_metadata={
                    k: operation["usage"].get(k, 0)
                    for k in ("input_tokens", "output_tokens", "total_tokens")
                },
                artifact=operation["raw"],
            )
            state.save()
            return parsed
    except Exception as exc:
        operation["status"] = (
            "failed_with_response" if "raw" in operation else "unknown_outcome"
        )
        operation["error"] = str(exc)
        state.save()
        raise
