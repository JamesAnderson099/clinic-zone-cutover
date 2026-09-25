from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, field_validator
import tldextract


_domain_parser = tldextract.TLDExtract(suffix_list_urls=())


class DnsGateway(Protocol):
    def add_domain(self, domain: str) -> str:
        raise AssertionError

    def upsert_cname(self, zone_id: str, name: str, content: str, operation_id: str) -> None:
        raise AssertionError

    def verify_domain(self, domain: str) -> None:
        raise AssertionError


class AppointmentWindow(BaseModel):
    starts_at: datetime
    status: Literal["confirmed", "checked_in", "completed", "cancelled"]

    @field_validator("starts_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("starts_at must include a timezone")
        return value


class CutoverRequest(BaseModel):
    operation_id: UUID
    domain: str = Field(min_length=3)
    record_name: str = Field(min_length=1)
    gateway_target: str = Field(min_length=3)
    appointments: list[AppointmentWindow] = Field(default_factory=list)

    @field_validator("domain")
    @classmethod
    def require_root_domain(cls, value: str) -> str:
        domain = value.rstrip(".").lower()
        parsed = _domain_parser(domain)
        if not parsed.domain or not parsed.suffix or parsed.subdomain:
            raise ValueError("domain must be a registrable root domain")
        return domain


class OperationalNotice(BaseModel):
    audience: Literal["clinic_operations"] = "clinic_operations"
    severity: Literal["info", "action_required"]
    message: str


class CutoverResult(BaseModel):
    decision: Literal["applied", "deferred"]
    zone_id: str | None = None
    notice: OperationalNotice


def run_cutover(request: CutoverRequest, dns: DnsGateway, now: datetime | None = None) -> CutoverResult:
    current = now or datetime.now(timezone.utc)
    safety_limit = current + timedelta(hours=2)
    active = [
        item
        for item in request.appointments
        if item.status in {"confirmed", "checked_in"} and current <= item.starts_at <= safety_limit
    ]
    if active:
        return CutoverResult(
            decision="deferred",
            notice=OperationalNotice(
                severity="action_required",
                message="DNS cutover deferred until the active appointment safety window clears.",
            ),
        )

    zone_id = dns.add_domain(request.domain)
    dns.upsert_cname(zone_id, request.record_name, request.gateway_target, str(request.operation_id))
    dns.verify_domain(request.domain)
    return CutoverResult(
        decision="applied",
        zone_id=zone_id,
        notice=OperationalNotice(
            severity="info",
            message="Gateway DNS is verified; clinic operations can continue the cutover checklist.",
        ),
    )
