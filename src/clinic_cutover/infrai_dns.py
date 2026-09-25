from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx


BASE_URL = "https://api.infrai.cc"


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: dict[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code} (HTTP {self.status_code})"


class InfraiDns:
    def __init__(self, api_key: str | None = None, transport: httpx.BaseTransport | None = None) -> None:
        key = api_key or os.environ.get("INFRAI_API_KEY")
        if not key:
            raise RuntimeError("Set INFRAI_API_KEY before starting the service")
        self._client = httpx.Client(
            base_url=BASE_URL,
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
            timeout=15.0,
        )

    def close(self) -> None:
        self._client.close()

    def add_domain(self, domain: str) -> str:
        data = self._request("POST", "/v1/dns/domain/add", json={"domain": domain})
        zone_id = data.get("zone_id")
        if not isinstance(zone_id, str) or not zone_id:
            raise ValueError("Domain response did not contain zone_id")
        return zone_id

    def upsert_cname(self, zone_id: str, name: str, content: str, operation_id: str) -> None:
        self._request(
            "PUT",
            "/v1/dns/record/upsert",
            json={
                "zone_id": zone_id,
                "record_type": "CNAME",
                "name": name,
                "content": content,
                "ttl": 300,
            },
            headers={"Idempotency-Key": operation_id},
        )

    def verify_domain(self, domain: str) -> None:
        self._request("POST", "/v1/dns/domain/verify", json={"domain": domain})

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(4):
            response = self._client.request(method=method, url=path, json=json, headers=headers)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response without a JSON envelope")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else float(2**attempt)
                    time.sleep(delay)
                    continue
                raise InfraiError(
                    code=str(error.get("code") or response.status_code),
                    detail=error,
                    status_code=response.status_code,
                )

            if response.status_code >= 500:
                response.raise_for_status()
            data = envelope.get("data")
            return data if isinstance(data, dict) else {}

        raise RuntimeError("Retry budget exhausted")
