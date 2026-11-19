import os
from typing import Protocol

import httpx
from opentelemetry import trace
from pydantic import ValidationError

from .activities import activity
from .providers import EnglishTranslation, ProviderUnavailable


class Translator(Protocol):
    async def translate_to_english(self, text: str) -> str: ...


class AzureTranslator:
    def __init__(self, client: httpx.AsyncClient, key: str, region: str | None):
        self.client = client
        self.headers = {"Ocp-Apim-Subscription-Key": key}
        if region:
            self.headers["Ocp-Apim-Subscription-Region"] = region

    async def translate_to_english(self, text: str) -> str:
        with activity("translation", "translation.azure", provider="azure"):
            span = trace.get_current_span()
            try:
                response = await self.client.post(
                    "https://api.cognitive.microsofttranslator.com/translate",
                    params={"api-version": "3.0", "from": "he", "to": "en"},
                    headers=self.headers,
                    json=[{"Text": text}],
                )
                response.raise_for_status()
                translated = response.json()[0]["translations"][0]["text"]
                return EnglishTranslation(text=translated).text
            except (httpx.HTTPError, ValidationError, KeyError, IndexError, TypeError, ValueError) as error:
                span.set_status(trace.StatusCode.ERROR, type(error).__name__)
                raise ProviderUnavailable from None


def select_translator(client: httpx.AsyncClient, llm: Translator) -> tuple[str, Translator]:
    name = os.getenv("TRANSLATION_PROVIDER", "llm")
    if name == "llm":
        return name, llm
    if name == "azure":
        key = os.getenv("AZURE_TRANSLATOR_KEY")
        if not key:
            raise ValueError("AZURE_TRANSLATOR_KEY is required when TRANSLATION_PROVIDER=azure")
        return name, AzureTranslator(client, key, os.getenv("AZURE_TRANSLATOR_REGION"))
    raise ValueError("Unsupported TRANSLATION_PROVIDER")
