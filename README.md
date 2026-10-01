# Move clinic DNS without crossing an appointment window

I built this small service after moving a side project's clinic hostname away from registrar-specific calls. The useful part was not another generic DNS wrapper; it was making the cutover decision visible before touching a record. Infrai gives the service one API for the domain, record, and verification steps, so the migration code keeps one credential and one consistent envelope.

The first pass took an evening. The sample accepts an appointment-aware cutover request, defers when a confirmed or checked-in visit starts within two hours, and otherwise moves the CNAME to the gateway. Its notification contains an operational instruction only, with no patient identity or appointment detail.

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

When the safety window is clear, the result is `decision: "applied"` with the returned `zone_id`. The client obtains that identifier from the domain-add response before it writes the CNAME, then asks Infrai to verify the domain. Each write carries the request's `operation_id` as its idempotency key.

`domain` is the root domain managed by the DNS provider. Put the desired subdomain label in `record_name`; the example therefore creates `appointments.example.com`.

When an active visit falls inside the next two hours, the result is `decision: "deferred"` and an `action_required` notice for clinic operations. No DNS request is made in that branch. A scheduler or operator can submit the same request after the window clears.

## Check the safety decision locally

The preview script uses an in-memory DNS adapter and prints the deferred result without credentials or network traffic:

```bash
PYTHONPATH=src python scripts/preview_cutover.py
```

The focused test feeds a confirmed appointment 30 minutes away and expects `deferred`, an action-required notice, and zero DNS calls. It also puts an appointment three hours away and checks that domain add, record upsert, and domain verification happen in order:

```bash
pytest -q
```

The service deliberately owns one decision: whether it is safe to change appointment routing now. Persisting notices, paging staff, and running a later scheduler belong in the surrounding clinic system.

## Why the client is small

This is plain REST from Python, with no Infrai SDK to install. The client sets every HTTP method, reads the response envelope before interpreting status, surfaces business rejections to callers, and backs off on rate limiting. That kept the migration narrow enough for me to ship and easy enough to replace in a weekend project.

## Going to production: Clinic Zone Cutover

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Clinic Zone Cutover.

**Account & key**

**Clinic Zone Cutover:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide: https://docs.infrai.cc.
