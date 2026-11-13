# ADR-001: The register is a read-only SQLite build artifact

Status: proposed (2026-11-13)

## Context
- The source changes a few times a year (the editions are dated "as on 30.09.2026").
- Serving needs only reads. Correctness matters more than freshness.
- Porter's used PostgreSQL because it had concurrent writers (a job queue). This project has none.

## Decision
- The build plane writes `register.sqlite` once, in a deterministic order, plus a canonical JSON dump whose SHA-256 identifies the build.
- The serving plane opens the file read-only (`mode=ro`, `immutable=1`).

## Alternatives considered
| Option | Why not |
|---|---|
| PostgreSQL | A server to run and migrate, for a read-only table of about 2,500 rows. No concurrency problem to solve. |
| JSON loaded into memory | No indexes or SQL. Ad-hoc queries in the evaluation and debugging would be painful. |
| A search engine (OpenSearch) | Overkill. Name resolution is a small alias table, not full-text search over documents. |

## Consequences
- **Plus:** reproducible answers. A deploy is atomic (code and data move together). Trivial to test with a fixture database.
- **Minus:** a new edition needs a rebuild and redeploy. Pilot logs (M6) need a separate writable store, decided in the M6 LLD.
