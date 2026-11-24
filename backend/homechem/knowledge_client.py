import asyncio
from collections import OrderedDict
import json
import os
from time import monotonic

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from opentelemetry.propagate import inject
from pydantic import BaseModel

from .activities import activity
from .debug_bundle import mcp_http_client, json_body


class KnowledgeUnavailable(Exception):
    pass


class KnowledgeClient:
    def __init__(self, url: str | None = None, provider: str = "homechem"):
        self.url = url or os.getenv("MCP_DATA_URL", "http://127.0.0.1:8002/mcp")
        self.provider = provider
        self.cache: OrderedDict[str, tuple[float, dict]] = OrderedDict()

    async def call[T: BaseModel](self, tool: str, arguments: dict, output: type[T]) -> T:
        key = json.dumps([tool, arguments], sort_keys=True)
        cached = self.cache.get(key)
        if cached and monotonic() - cached[0] < 3600:
            with activity("cache", "knowledge.cache", tool=tool, provider=self.provider, hit=True):
                self.cache.move_to_end(key)
                return output.model_validate(cached[1])
        with activity("mcp", "mcp.data", tool=tool, provider=self.provider, transport="streamable-http") as step:
            step.debug["arguments"] = json.dumps(json_body(json.dumps(arguments).encode()), ensure_ascii=False)
            headers = {}
            inject(headers)
            try:
                async with asyncio.timeout(25):
                    async with streamablehttp_client(self.url, headers=headers, timeout=20, sse_read_timeout=20, httpx_client_factory=mcp_http_client) as (read, write, _):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            result = await session.call_tool(tool, arguments)
                            if result.isError:
                                raise KnowledgeUnavailable("Data source could not resolve this request")
                            payload = result.structuredContent
                            if payload is None:
                                blocks = [block.text for block in result.content if block.type == "text"]
                                if len(blocks) != 1:
                                    raise KnowledgeUnavailable("Expected one JSON result")
                                payload = json.loads(blocks[0])
                            validated = output.model_validate(payload)
                self.cache[key] = (monotonic(), validated.model_dump())
                self.cache.move_to_end(key)
                while len(self.cache) > 256:
                    self.cache.popitem(last=False)
                step.details["validated"] = True
                source = getattr(validated, "provenance", None)
                if source:
                    step.details.update(source=source.publisher, source_url=source.url, data_mode=source.mode)
                if hasattr(validated, "cid"):
                    step.details["cid"] = validated.cid
                if hasattr(validated, "items"):
                    step.details["matches"] = len(validated.items)
                return validated
            except Exception as error:
                step.details["cause_type"] = type(error).__name__
                raise KnowledgeUnavailable("MCP data source unavailable or invalid result") from None
