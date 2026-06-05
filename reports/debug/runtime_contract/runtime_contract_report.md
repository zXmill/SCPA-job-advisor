# Runtime Contract Audit Report

Generated: 2026-05-31T14:37:33.176810+00:00
Gateway: `http://localhost:9000`

## Summary
- Modes requested: dev, prod
- Scenarios: 14
- Failed checks: 0
- Canceled request events: 75
- Console severe entries: 0

## Mode Results
- `dev` at `http://localhost:3000`: login success=True, has token=True
  - jobs: passed, checks=4, failed=0, canceled=0, auth/me=0
    - note: captured 5 post-load network events
  - recommendations: passed, checks=5, failed=0, canceled=0, auth/me=1
  - jobs_cancellation: passed, checks=2, failed=0, canceled=2, auth/me=0
    - note: network throttle enabled=True
  - recommendations_cancellation: passed, checks=2, failed=0, canceled=0, auth/me=0
    - note: network throttle enabled=True
  - auth_session: passed, checks=2, failed=0, canceled=0, auth/me=5
  - theme_toggle: passed, checks=3, failed=0, canceled=0, auth/me=0
  - gateway_restart: passed, checks=2, failed=0, canceled=0, auth/me=0
- `prod` at `http://localhost:3001`: login success=True, has token=True
  - jobs: passed, checks=4, failed=0, canceled=12, auth/me=0
    - note: captured 78 post-load network events
  - recommendations: passed, checks=5, failed=0, canceled=1, auth/me=1
  - jobs_cancellation: passed, checks=2, failed=0, canceled=13, auth/me=0
    - note: network throttle enabled=True
  - recommendations_cancellation: passed, checks=2, failed=0, canceled=4, auth/me=0
    - note: network throttle enabled=True
  - auth_session: passed, checks=2, failed=0, canceled=13, auth/me=5
  - theme_toggle: passed, checks=3, failed=0, canceled=0, auth/me=0
  - gateway_restart: passed, checks=2, failed=0, canceled=21, auth/me=0

## Artifact Locations
- `reports/debug/runtime_contract/summary.json`
- `reports/debug/runtime_contract/network.ndjson`
- `reports/debug/runtime_contract/console.ndjson`
- `reports/debug/runtime_contract/gateway_logs.ndjson`
- `reports/debug/runtime_contract/screenshots/`
- `reports/debug/runtime_contract/dom_snapshots/`
