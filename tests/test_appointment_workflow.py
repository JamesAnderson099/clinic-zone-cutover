from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from clinic_cutover.appointment_workflow import AppointmentWindow, CutoverRequest, run_cutover


class RecordingDns:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def add_domain(self, domain: str) -> str:
        self.calls.append(("add", domain))
        return "zone_clinic_7"

    def upsert_cname(self, zone_id: str, name: str, content: str, operation_id: str) -> None:
        self.calls.append(("upsert", zone_id, name, content, operation_id))

    def verify_domain(self, domain: str) -> None:
        self.calls.append(("verify", domain))


def request_with(starts_at: datetime) -> CutoverRequest:
    return CutoverRequest(
        operation_id=UUID("4ca46069-4f17-4b55-a899-4c23db24440f"),
        domain="example.com",
        record_name="appointments",
        gateway_target="gateway.example.net",
        appointments=[AppointmentWindow(starts_at=starts_at, status="confirmed")],
    )


def test_defers_cutover_during_appointment_safety_window() -> None:
    now = datetime(2026, 9, 19, 9, 0, tzinfo=timezone.utc)
    dns = RecordingDns()

    result = run_cutover(request_with(now + timedelta(minutes=30)), dns, now=now)

    assert result.decision == "deferred"
    assert result.notice.severity == "action_required"
    assert dns.calls == []


def test_applies_cutover_after_safety_window() -> None:
    now = datetime(2026, 9, 19, 9, 0, tzinfo=timezone.utc)
    dns = RecordingDns()

    result = run_cutover(request_with(now + timedelta(hours=3)), dns, now=now)

    assert result.decision == "applied"
    assert result.zone_id == "zone_clinic_7"
    assert [call[0] for call in dns.calls] == ["add", "upsert", "verify"]
    assert dns.calls[1][1] == "zone_clinic_7"


def test_rejects_subdomain_as_domain_zone() -> None:
    request = request_with(datetime.now(timezone.utc))
    with pytest.raises(ValidationError, match="registrable root domain"):
        CutoverRequest.model_validate({**request.model_dump(), "domain": "care.example.com"})
