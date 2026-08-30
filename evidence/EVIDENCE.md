# ZeroTrace Evidence Index

**SSOT-01 §5:** every `EV-*` ID maps to one file in `/evidence/`, and each entry names
the rubric line it satisfies. The pack is built as the work happens, never at the end.
See `docs/00_SSOT_RULES_AND_SCORING.md` §5 for the binding rules and the full evidence
ledger.

| ID | File | Satisfies |
|---|---|---|
| `EV-PA-01` | `evidence/04_jtbd/EV-PA-01-part-a-e2e.json` | Part A production-mode E2E gate (`make part-a-e2e`): real HTTP through PostgreSQL 16 + Redis 7, restart persistence, concurrency, policy conflict safety, and the full privacy sweep. Approved scope is production-mode Part A E2E only; OIDC, real detection, and the real provider upstream are later milestones. This Part A report is **not** one of the later 60-case full-product evidence IDs (`EV-JTB-01/02/03`); it stands alone as the Part A completion gate. |

## Rules

1. One row per `EV-*` ID, in ID order. The file path is relative to the repository root.
2. A row is added in the same change that creates or approves its `EV-*` ID (SSOT-01 §10).
3. The report file `EV-PA-01-part-a-e2e.json` is written by `make part-a-e2e`; it is
   published with an atomic rename only after every assertion and the privacy sweep pass,
   and it is never hand-edited.
4. The remaining IDs listed in SSOT-01 §5.1 are filed as their gates complete.
