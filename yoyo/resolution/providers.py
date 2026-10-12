import json
import httpx
from openai import OpenAI
from openai.lib._pydantic import to_strict_json_schema
from ..config import settings
from .cache import Cache


class Research:
    def __init__(self, trace=None):
        self.cache = Cache()
        self.client = OpenAI(
            api_key=settings.openai_api_key, max_retries=0, timeout=180
        )
        self.trace = trace

    def ask(self, prompt, payload, contract, schema=None):
        request = {
            "model": settings.model,
            "temperature": 0,
            "prompt": prompt,
            "payload": payload,
            "schema": schema or to_strict_json_schema(contract),
        }

        def execute():
            response = self.client.responses.create(
                model=settings.model,
                temperature=0,
                input=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(payload)},
                ],
                max_output_tokens=6000,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": contract.__name__,
                        "strict": True,
                        "schema": request["schema"],
                    }
                },
            )
            return response.model_dump(mode="json")

        result = self.cached("llm-" + contract.__name__, request, execute)
        if result["status"] != "completed":
            raise ValueError("Incomplete model response retained in cache")
        text = "".join(
            c.get("text", "") for o in result["output"] for c in o.get("content", [])
        )
        return contract.model_validate_json(text)

    def search(self, query):
        request = {
            "query": query,
            "type": "auto",
            "numResults": 6,
            "contents": {"text": {"maxCharacters": 7000}},
        }

        def execute():
            response = httpx.post(
                "https://api.exa.ai/search",
                json=request,
                headers={"x-api-key": settings.exa_api_key},
                timeout=90,
            )
            response.raise_for_status()
            return response.json()

        return self.cached("exa-search", request, execute)

    def embed(self, text):
        request = {
            "model": settings.embedding_model,
            "input": text[:20000],
            "dimensions": 512,
        }
        result = self.cached(
            "embedding",
            request,
            lambda: self.client.embeddings.create(**request).model_dump(mode="json"),
        )
        return result["data"][0]["embedding"]

    def cached(self, kind, request, execute):
        if not self.trace:
            return self.cache.call(kind, request, execute)
        from ..artifacts import digest

        with self.trace.span(
            kind,
            {"request_hash": digest(request)},
            "llm" if kind.startswith("llm") else "tool",
        ) as output:
            result = self.cache.call(kind, request, execute)
            output.update(self.cache.events[-1])
            return result
