# Runtime Contract Audit Report

Generated: 2026-05-31T14:17:51.360013+00:00
Gateway: `http://localhost:9000`

## Summary
- Modes requested: dev, prod
- Scenarios: 8
- Failed checks: 4
- Canceled request events: 3
- Console severe entries: 2

## Mode Results
- `dev` at `http://localhost:3000`: login success=True, has token=True
  - jobs: passed, checks=4, failed=0, canceled=0, auth/me=0
    - note: captured 2 post-load network events
  - recommendations: failed, checks=4, failed=1, canceled=1, auth/me=1
  - jobs_cancellation: failed, checks=2, failed=1, canceled=2, auth/me=0
    - note: network throttle enabled=True
  - recommendations_cancellation: failed, checks=2, failed=1, canceled=0, auth/me=0
    - note: network throttle enabled=True
  - auth_session: failed, checks=2, failed=1, canceled=0, auth/me=6
  - theme_toggle: passed, checks=3, failed=0, canceled=0, auth/me=0
  - gateway_restart: passed, checks=2, failed=0, canceled=0, auth/me=0
- `prod` at `http://localhost:3001`: login success=False, has token=False
  - login: blocked, checks=0, failed=0, canceled=0, auth/me=0
    - note: authenticated runtime scenarios require successful login

## Artifact Locations
- `reports/debug/runtime_contract/summary.json`
- `reports/debug/runtime_contract/network.ndjson`
- `reports/debug/runtime_contract/console.ndjson`
- `reports/debug/runtime_contract/gateway_logs.ndjson`
- `reports/debug/runtime_contract/screenshots/`
- `reports/debug/runtime_contract/dom_snapshots/`
