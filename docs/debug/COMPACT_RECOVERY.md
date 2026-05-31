# Compact Recovery

Updated: 2026-05-31 09:52 +07

## Current Task
DEBUG-ULT-001: ultimate evidence-based debugging session bootstrap.

## Current Branch
agent-run

## Latest Commit Hash
0b55041

## Dirty Files
- Pre-existing before this session: `README.md`, `SCPAv2`, `notebooks/01_indonesian_hybrid_dataset_eda.ipynb`, `notebooks/02_hybrid_dataset_validation.ipynb`.
- Pre-existing before this session: many untracked project files/directories including source, docs, reports, models, and `docs/debug/`.
- Nested `frontend/` repository is dirty and must be handled separately if frontend code changes are made.
- This session owns only the new/updated debugging docs and durable agent-state checkpoint until product evidence confirms a fix.

## Active Hypothesis
H1-DOCKER-GATEWAY-REQ is confirmed by baseline rebuild evidence: `docker compose up -d --build` fails in the gateway image because pip cannot open `requirements-db.txt`. H2-DOCKER-CONTEXT is also supported by evidence: gateway build context transferred about 5.06GB and root `.dockerignore` is missing.

## Latest Validation Status
Backend pytest passed (`389 passed, 3 warnings`), frontend lint/build passed, Docker config passed, Docker rebuild failed at gateway. Existing containers are healthy but predate the failed rebuild.

## Next Exact Action
Commit static inventory, baseline validation, and hypotheses, then add and run the Selenium/Chrome audit harness against the current frontend on port 3000 and gateway on port 9000.
