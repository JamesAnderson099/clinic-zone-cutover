from datetime import datetime, timedelta, timezone
from uuid import UUID

from clinic_cutover.appointment_workflow import CutoverRequest, AppointmentWindow, run_cutover


class PreviewDns:
    def add_domain(self, domain: str) -> str:
        return "zone_preview_01"

    def upsert_cname(self, zone_id: str, name: str, content: str, operation_id: str) -> None:
        return None

    def verify_domain(self, domain: str) -> None:
        return None


now = datetime.now(timezone.utc)
request = CutoverRequest(
    operation_id=UUID("4ca46069-4f17-4b55-a899-4c23db24440f"),
    domain="example.com",
    record_name="appointments",
    gateway_target="gateway.example.net",
    appointments=[AppointmentWindow(starts_at=now + timedelta(minutes=45), status="confirmed")],
)
print(run_cutover(request, PreviewDns(), now=now).model_dump_json(indent=2))
