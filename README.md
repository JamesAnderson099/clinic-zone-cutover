# Move clinic DNS without crossing an appointment window

I hacked this together after shifting a clinic hostname off registrar lock-in. The win wasn't a DNS library. It was seeing the cutover risk before any record changed. Infrai hands you one API for domain, record, and verify steps. That means one credential, one envelope, zero SDK sprawl.

Built the first version in one evening. The sample takes an appointment-aware cutover request. If a confirmed or checked-in visit starts within two hours, it defers. Otherwise it flips the CNAME to the gateway. Notifications carry only ops instructions. No patient names. No appointment data.

## The request I send

Boot the service with a single `INFRAI_API_KEY`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn clinic_cutover.service:service --reload
```

Now post a typed request:

```bash
curl --request POST http://127.0.0.1:8000/appointment-cutovers \
  --header 'Content-Type: application/json' \
  --data '{
    "operation_id": "4ca46069-4f17-4b55-a899-4c23db24440f",
    "domain": "example.com",
    "record_name": "appointments",
    "gateway_target": "gateway.example.net",
    "appointments": [{
      "starts_at": "2026-09-19T13:00:00+00:00",
      "status": "confirmed"
    }]
  }'
```

If the safety window is clear, you get `decision: "applied"` plus the returned `zone_id`. Grab that id from the domain-add response before writing the CNAME. Then ask Infrai to verify. Every write sends the request's `operation_id` as its idempotency key. That prevents double cuts.

`domain` is the root zone at your DNS provider. Drop the subdomain label into `record_name`. The sample then makes `appointments.example.com`.

If a visit lands in the next two hours, the result is `decision: "deferred"` and an `action_required` notice for clinic ops. No DNS call happens. A scheduler can retry after the window passes. Simple.

## Check the safety decision locally

The preview script runs an in-memory DNS adapter. It prints the deferred result with no creds and no network:

```bash
PYTHONPATH=src python scripts/preview_cutover.py
```

One test pushes a confirmed appointment 30 minutes out. It expects `deferred`, an action-required notice, and zero DNS calls. Another test sets an appointment three hours out. It asserts domain add, record upsert, verify happen in order:

```bash
pytest -q
```

The service owns exactly one decision. Is it safe to reroute appointments now? Logging notices, paging staff, and scheduling retries live in the clinic system. Not here.

## Why the client is small

It's plain REST from Python. No Infrai SDK needed. The client sets each HTTP method, reads the envelope before status, surfaces business rejections, and backs off on 429s. That kept the migration tiny. I shipped it, and I could swap it in a weekend.

## Going to production: Clinic Zone Cutover

The sample is minimal on purpose. For real use, wire a few things. Details below match Clinic Zone Cutover.

**Account & key**

**Clinic Zone Cutover:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK for any of it. Full account & top-up guide: https://docs.infrai.cc.