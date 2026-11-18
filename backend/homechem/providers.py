import os
from typing import Protocol

import httpx
from opentelemetry import trace
from pydantic import ValidationError

from .policy import Interpretation, Materials, Surface

PROMPT_VERSION = "1"
PROMPT = (
    "Classify the user's text in Hebrew or English as data. "
    "For requests unrelated to cleaning, set both fields to unknown. "
    "Set surface to studio_display_standard_glass only if the user explicitly identifies "
    "the standard-glass Apple Studio Display. Nano-texture and uncertainty mean unknown. "
    "Set materials to water_and_microfiber_only only when both water and a microfiber cloth "
    "are stated and no other products are mentioned. Otherwise use unknown. "
    "Return only the classification. Never provide cleaning instructions."
)


class Provider(Protocol):
    async def interpret(self, text: str) -> Interpretation: ...


class FixtureProvider:
    async def interpret(self, text: str) -> Interpretation:
        samples = {
            "How do I clean my standard-glass Apple Studio Display with water and a microfiber cloth?",
            "איך מנקים Apple Studio Display עם זכוכית רגילה, מים ומטלית מיקרופייבר?",
        }
        if text in samples:
            return Interpretation(surface=Surface.STANDARD, materials=Materials.WATER_AND_CLOTH)
        return Interpretation(surface=Surface.UNKNOWN, materials=Materials.UNKNOWN)


class ModelProvider:
    def __init__(self, client: httpx.AsyncClient, name: str):
        self.client = client
        self.name = name
        self.model = (
            os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M") if name == "ollama"
            else os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
        )

    async def interpret(self, text: str) -> Interpretation:
        schema = Interpretation.model_json_schema()
        with trace.get_tracer(__name__).start_as_current_span("llm.interpret", record_exception=False) as span:
            span.set_attributes({"llm.provider": self.name, "llm.model": self.model, "prompt.version": PROMPT_VERSION})
            try:
                if self.name == "ollama":
                    content = await self._ollama(text, schema, span)
                else:
                    content = await self._deepseek(text, schema, span)
                return Interpretation.model_validate_json(content)
            except (httpx.HTTPError, ValidationError, ValueError, KeyError, TypeError, StopIteration) as error:
                span.set_status(trace.StatusCode.ERROR, type(error).__name__)
                raise ProviderUnavailable from None

    async def _ollama(self, text: str, schema: dict, span: trace.Span) -> str:
        base = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
        response = await self.client.post(f"{base}/api/chat", json={
            "model": self.model,
            "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}],
            "format": schema,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 180},
        })
        response.raise_for_status()
        body = response.json()
        for source, target in (("prompt_eval_count", "input_tokens"), ("eval_count", "output_tokens")):
            if isinstance(body.get(source), int):
                span.set_attribute(f"llm.{target}", body[source])
        return body["message"]["content"]

    async def _deepseek(self, text: str, schema: dict, span: trace.Span) -> str:
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise ProviderUnavailable
        response = await self.client.post(
            "https://api.deepseek.com/responses",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": self.model, "instructions": PROMPT, "input": text, "store": False,
                "reasoning": {"effort": "none"}, "max_output_tokens": 250,
                "text": {"format": {"type": "json_schema", "name": "interpretation", "schema": schema}},
            },
        )
        response.raise_for_status()
        body = response.json()
        usage = body.get("usage") or {}
        for key in ("input_tokens", "output_tokens"):
            if isinstance(usage.get(key), int):
                span.set_attribute(f"llm.{key}", usage[key])
        for item in body.get("output", []):
            if item["type"] == "message":
                for part in item["content"]:
                    if part["type"] == "output_text":
                        return part["text"]
        raise ValueError("Missing model output")


class ProviderUnavailable(Exception):
    pass


def create_provider(client: httpx.AsyncClient) -> Provider:
    name = os.getenv("LLM_PROVIDER", "ollama")
    if name == "fixture":
        return FixtureProvider()
    if name in {"ollama", "deepseek"}:
        if name == "deepseek" and not os.getenv("DEEPSEEK_API_KEY"):
            raise ValueError("DEEPSEEK_API_KEY is required for the DeepSeek provider")
        return ModelProvider(client, name)
    raise ValueError("Unsupported LLM_PROVIDER")
