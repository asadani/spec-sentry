<p align="center">
  <img src="assets/logo.svg" alt="Spec Sentry — Find ambiguity before it ships" width="400" height="160">
</p>

# Spec Sentry

Spec Sentry reviews a small, explicit annotation grammar in a Markdown specification. It locates declared quantity conflicts, unresolved marked terms, conflicting definitions, pending decisions, and malformed known directives. Review decisions live in a separate fingerprinted ledger.

## Quickstart

Use Python 3.11 or newer from this repository directory. These commands copy the fixture to a temporary directory and exercise check, decision, and report:

```sh
set -eu
DEMO_DIR="$(mktemp -d)"
trap 'rm -rf "$DEMO_DIR"' EXIT
cp fixtures/sharing-spec.md "$DEMO_DIR/sharing-spec.md"
if python -m spec_sentry check sharing-spec.md --root "$DEMO_DIR" --out "$DEMO_DIR/findings.json"; then
  echo "Expected the sharing spec to produce findings" >&2; exit 1
else
  code=$?
  test "$code" -eq 1
fi
FINDING_ID="$(python -c 'import json,sys; print(next(f["id"] for f in json.load(open(sys.argv[1]))["findings"] if f["kind"] == "pending_decision"))' "$DEMO_DIR/findings.json")"
python -m spec_sentry decide "$DEMO_DIR/findings.json" --finding "$FINDING_ID" --status dismissed --reviewer "Demo reviewer" --note "Keep this item for discussion." --decided-at 2026-10-22T01:00:00Z --ledger "$DEMO_DIR/decisions.json"
if python -m spec_sentry report sharing-spec.md --root "$DEMO_DIR" --ledger "$DEMO_DIR/decisions.json" --format markdown --out "$DEMO_DIR/review.md"; then
  echo "Expected other open findings to remain" >&2; exit 1
else
  code=$?
  test "$code" -eq 1
fi
python -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).read_text())' "$DEMO_DIR/review.md"
```

The report shows the fresh dismissal and the other outstanding findings. `check` exits `0` when no configured findings exist, `1` when the check completes with findings, and `2` for invalid input or operational errors. `decide` exits `0` after appending a valid decision and `2` on invalid input. `report` exits `1` if current open, accepted, deferred, or stale findings remain; only fresh dismissed findings are excluded. Try `python -m spec_sentry --help` for the full command syntax.

## Annotation grammar and limits

Outside fenced code blocks, directives must occupy a whole line:

```text
@quantity preview.max_size = 10 MB
@define external collaborator: A person invited from outside the workspace.
@decision sharing-policy | pending | Who may invite guests?
@decision audit-retention | approved | Keep audit records for 30 days. | reviewer: Product owner
```

`[[term:external collaborator]]` marks an explicit term reference anywhere in prose. Quantity keys and term identities compare case-insensitively after whitespace folding. Quantity values use decimal comparison, but units compare exactly as written; `10 MB` and `10 GB` conflict, and the tool performs no conversion. Duplicate decision IDs with different states or text conflict. Known directives with invalid syntax become findings.

This checks declared structure. Ordinary prose is not exhaustively checked, headings do not imply scope, and the tool does not infer contradictions, convert units, approve a specification, or decide whether a reviewer is correct. A clean report means only that no configured structural findings were observed.

## Data and tests

The report and ledger formats are described in [SCHEMA.md](docs/SCHEMA.md). The CLI uses relative source references under `--root`, resolves symlinks, and rejects paths that escape the root.

```sh
python -m unittest discover -s tests -v
```

## Data integrity

Report outputs cannot overwrite the specification or triage ledger. `decide` is the explicit ledger mutation command, and it refuses to replace its source report.

See [verification coverage](docs/VERIFICATION.md) and [the design plan](docs/PLAN.md) for tested behavior and remaining limits.
