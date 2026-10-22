# Spec Sentry v0.1 implementation plan

## User job and CLI

Review a single annotated Markdown specification for precise structural inconsistencies and retain human triage decisions separately.

```sh
python -m spec_sentry check fixtures/sharing-spec.md --out findings.json
python -m spec_sentry decide findings.json --finding <finding-id> --status accepted --reviewer "Demo reviewer" --note "Resolve the limit before implementation" --ledger decisions.json
python -m spec_sentry report fixtures/sharing-spec.md --ledger decisions.json --format markdown --out review.md
```

`check` returns 1 for findings and 0 clean. `decide` records one finding from the supplied report (it does not reread/approve a changed source), creates the ledger if needed, and returns 0. `report` recomputes findings, joins ledger decisions, and returns 1 when there are open/accepted/deferred or stale findings; only fresh dismissed findings are excluded from the outstanding count. Invalid inputs and failures exit 2. `--ledger` is optional for report. JSON is the other report format.

## Explicit Markdown grammar

Outside fenced code blocks recognize:

- `@quantity preview.max_size = 10 MB` — quantity key, a nonnegative decimal, and a unit token. Keys use letters/digits/dots/underscores/hyphens. Unit is a nonempty letters/percent token, compared case-sensitively. Parse Decimal from the stdlib; `10` and `10.0` are equal.
- `@define external collaborator: A person invited from outside the workspace.` — a term definition, casefolded/collapsed whitespace identity.
- `[[term:external collaborator]]` — an explicitly used term reference anywhere in prose.
- `@decision sharing-policy | pending | Who may invite guests?` — ID, state `pending|approved|rejected`, question/decision text. Approved and rejected annotations additionally require `| reviewer: Name`; pending may omit the reviewer.

Directives must occupy a full line (leading whitespace allowed). Lines beginning with known `@quantity`, `@define`, or `@decision` prefixes but failing grammar produce `malformed_annotation` findings with their line rather than being silently ignored. This is a structural checker over declared facts; ordinary prose outside this grammar is not exhaustively checked.

## Finding semantics

- `conflicting_quantity`: the same normalized quantity key has multiple distinct `(Decimal value, unit)` pairs. Group one finding per key and include all relevant source locations and literal values. Do not convert units or infer scope from prose headings.
- `undefined_term`: each normalized used term lacking a definition yields one finding containing all usage locations. A term definition alone is not a use.
- `conflicting_definition`: same normalized term has different normalized definition text; cite both/all definitions. Do not adjudicate meanings.
- `pending_decision`: each pending decision annotation yields a finding with its question and location.
- `unattributed_decision`: approved/rejected decision lacks a nonempty reviewer.
- `conflicting_decision`: duplicate decision ID with differing state or text; cite every occurrence. Exact repeated decision annotations may be combined without a conflict.
- `malformed_annotation`: invalid recognizable directive, with expected grammar.

Finding `{id,kind,message,subject,locations:[{path,line_start,line_end,text}],evidence:{...}}`. Stable IDs are hash prefixes (at least 16 hex chars) of kind plus normalized subject; malformed directive identity includes line and text. Report `{schema_version:1,source:{path,sha256},coverage:{grammar_version:1,limitations:[...]},findings:[...]}` ordered by first line then kind. Show literal evidence and never call these semantic contradictions without qualification.

## Ledger and API

Ledger: `{schema_version:1,decisions:[{finding_id,source_sha256,status:"accepted"|"dismissed"|"deferred",reviewer,note,decided_at}]}`. Note and reviewer must be nonempty. Append records; the latest record for a finding is its active triage, preserving earlier history. `accepted` means the reviewer accepts that this requires action, not that the specification is approved. Source hash must equal the current document hash for active triage to be fresh. Even an unrelated source edit conservatively makes decisions stale. Do not silently carry dismissals forward. Ledger entries with no current finding appear in a historical/resolved section and are not silently deleted.

- `parse_spec(text: str, path: str) -> dict`
- `check_spec(text: str, path: str) -> dict`
- `record_decision(report: dict, ledger: dict, finding_id: str, status: str, reviewer: str, note: str, decided_at: str) -> dict`
- `apply_ledger(report: dict, ledger: dict) -> dict`
- `render_markdown(report: dict) -> str`

Pure APIs operate on text/data; CLI handles byte hash, I/O, and atomic ledger writes. Validate report and ledger schemas before mutation. The Markdown report shows source/fingerprint, coverage limits, each finding with all locations, triage freshness, reviewer note, and historical entries.

## Fixtures and acceptance tests

1. A realistic sharing spec includes two max-size values, undefined marked term, pending decision, a correct definition/use, and a reviewed approval. The checker finds the first three with exact lines and leaves the valid statements alone.
2. Equal quantities `10` and `10.0 MB` do not conflict; 10 MB and 10 GB do, with no false unit equivalence. A third conflicting occurrence is retained in the grouped finding.
3. Definitions/terms are case-insensitive after whitespace normalization; ordinary unmarked nouns are not flagged. Code-fenced examples produce no findings.
4. Missing approval reviewer, conflicting duplicate decision, and malformed known directive yield specific findings instead of crashes or silence.
5. Dismissing a finding with a note is fresh for the same hash and removes it from outstanding count. Edit the file: the dismissal is stale and cannot hide the current finding. A fixed finding remains in ledger history.
6. Reject unknown finding IDs, empty reviewer/note, invalid status, corrupted ledger JSON, and duplicate invalid records without rewriting the ledger.
7. CLI check→decide→report works with temporary fixtures, uses documented exit codes, and produces deterministic findings before human timestamps enter the ledger.

## Non-goals and milestone

Required: explicit grammar, located checks, fingerprinted ledger, JSON/Markdown reports, substantive tests. Deferred: free-form contradiction detection, AI reviewers, document rewriting, team signoff systems, arbitrary unit conversion, issue-tracker integration. No output may claim a clean document has no contradictions; say no configured structural findings.

Build parser/checker, then ledger freshness, then CLI/report. Done means a reviewer can reproduce a conflicting quantity, record a dismissal, and see that dismissal become stale after revision.
