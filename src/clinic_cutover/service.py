from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from .appointment_workflow import CutoverRequest, CutoverResult, run_cutover
from .infrai_dns import InfraiDns, InfraiError


service = FastAPI(title="Clinic zone cutover")


def dns_gateway() -> InfraiDns:
    return InfraiDns()


@service.post("/appointment-cutovers", response_model=CutoverResult)
def create_cutover(request: CutoverRequest, dns: InfraiDns = Depends(dns_gateway)) -> CutoverResult:
    try:
        return run_cutover(request, dns)
    except InfraiError as error:
        client_status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail={"code": error.code, "error": error.detail}) from error
    finally:
        dns.close()
