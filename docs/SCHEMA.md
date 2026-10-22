# Spec Sentry report and ledger

All JSON artifacts use UTF-8 and `schema_version: 1`. `source.sha256` is SHA-256 over the UTF-8 source bytes. A whole-file change marks every decision from the earlier review stale.

## Findings report

`check` emits `{ "schema_version": 1, "source": {"path": ..., "sha256": ...}, "coverage": ..., "findings": [...] }`. A finding has a deterministic `id`, `kind`, `message`, normalized `subject`, one or more `locations`, and optional `evidence`. Each location records a relative path, 1-based inclusive line bounds, and the literal annotation or marker. Finding kinds are `conflicting_quantity`, `undefined_term`, `conflicting_definition`, `pending_decision`, `unattributed_decision`, `conflicting_decision`, and `malformed_annotation`.

## Decision ledger

`{ "schema_version": 1, "decisions": [...] }` is append-only from the CLI. Each record has `finding_id`, `source_sha256`, `status` (`accepted`, `dismissed`, or `deferred`), nonempty `reviewer` and `note`, and `decided_at` in UTC ISO 8601 form. The latest record per finding is active. A record is fresh only when its source hash matches the current document. `accepted` records that a reviewer believes the finding needs action; it does not approve the specification.

Reports retain decisions for findings no longer present in `historical_decisions`. They are not deleted or treated as current findings. Only fresh dismissed decisions reduce the current outstanding count.
