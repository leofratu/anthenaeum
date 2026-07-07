from __future__ import annotations

from typing import Any, Protocol

import httpx


class HttpTransport(Protocol):
    async def request_json(self, method: str, url: str, *, headers: dict[str, str], json_body: dict[str, Any], timeout: float) -> dict[str, Any]: ...


class HttpxTransport:
    async def request_json(self, method: str, url: str, *, headers: dict[str, str], json_body: dict[str, Any], timeout: float) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, headers=headers, json=json_body)
            if response.status_code in {408, 409, 429, 500, 502, 503, 504, 529}:
                raise httpx.HTTPStatusError("transient provider error", request=response.request, response=response)
            response.raise_for_status()
            return response.json()


class FakeTransport:
    def __init__(self, responses: list[dict[str, Any]] | dict[str, Any]):
        self.responses = responses if isinstance(responses, list) else [responses]
        self.requests: list[dict[str, Any]] = []

    async def request_json(self, method: str, url: str, *, headers: dict[str, str], json_body: dict[str, Any], timeout: float) -> dict[str, Any]:
        self.requests.append({"method": method, "url": url, "headers": headers, "json": json_body, "timeout": timeout})
        if not self.responses:
            raise AssertionError("FakeTransport has no response left")
        return self.responses.pop(0)
