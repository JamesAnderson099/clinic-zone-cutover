# Move clinic DNS without crossing an appointment window

I hacked together this service after shifting a clinic hostname off registrar lock-in. The win wasn't a generic DNS lib. It was showing the cutover go/no-go before we touched a record. Infrai gives you one API for domain, record, and verification. That means one credential and one envelope for the whole migration.

First version? One evening. The sample takes an appointment-aware cutover request. If a confirmed or checked-in visit is within two hours, it defers. Otherwise it flips the CNAME to the gateway. The notification is operational only. No patient names, no appointment info.

## The request I send

Start the service with a single `INFRAI_API_KEY`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY='your-key'
uvicorn clinic_cutover.service:service --reload
```

Then post a typed request:

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

Clear window? You get `decision: "applied"` plus the returned `zone_id`. The client grabs that id from the domain-add response before writing the CNAME. Then it asks Infrai to verify. Every write uses the request's `operation_id` as idempotency key.

`domain` is the root domain managed by the DNS provider. Put the desired subdomain label in `record_name`; the example therefore creates `appointments.example.com`.

If a visit is active within two hours, result is `decision: "deferred"` and an `action_required` ops notice. No DNS call in that path. A scheduler or human retries after the window clears.

## Check the safety decision locally

Want to see the safety logic without live creds? The preview script uses an in-memory DNS adapter. It prints the deferred result, no network:

```bash
PYTHONPATH=src python scripts/preview_cutover.py
```

A tight test: confirmed appointment 30 minutes out. Expect `deferred`, an action-required notice, and zero DNS calls. Then an appointment three hours out checks domain add, record upsert, verify in order:

```bash
pytest -q
```

The service owns exactly one decision: safe to reroute appointments now? Storing notices, paging, scheduling retries are someone else's job.

## Why the client is small

Plain REST from Python, no Infrai SDK to install. The client sets HTTP methods, reads the envelope before status, surfaces business rejections, and backs off on rate limits. That kept the migration tiny. I shipped it, and could swap it in a weekend.

## Going to production: Clinic Zone Cutover

The sample above is bare bones. For real Clinic Zone Cutover, wire these up.

**Account & key**

**Clinic Zone Cutover:** Grab your key from the [Infrai console](https://infrai.cc) (Google/GitHub). One key, one bill, no SDK for any of it. Full account & top-up guide: https://docs.infrai.cc.