"""Explicit Markdown annotation parser, checker, and triage ledger."""
from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Any


class SentryError(ValueError):
    """Expected invalid report or ledger data."""


def _visible_lines(text: str):
    """Yield prose lines while respecting the opening fence's character and length."""
    opened = None
    for number, line in enumerate(text.splitlines(), 1):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})(.*)$", line)
        if opened:
            if marker and marker.group(1)[0] == opened[0] and len(marker.group(1)) >= opened[1] and not marker.group(2).strip():
                opened = None
            continue
        if marker:
            opened = (marker.group(1)[0], len(marker.group(1)))
            continue
        yield number, line


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


def _identity(kind: str, subject: str) -> str:
    return hashlib.sha256((kind + "\0" + subject).encode("utf-8")).hexdigest()[:20]


def _loc(path: str, line: int, text: str) -> dict[str, Any]:
    return {"path": path, "line_start": line, "line_end": line, "text": text}


def _finding(kind: str, subject: str, message: str, locations: list[dict[str, Any]], evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {"id": _identity(kind, subject), "kind": kind, "message": message,
                              "subject": subject, "locations": locations}
    if evidence is not None:
        result["evidence"] = evidence
    return result


def parse_spec(text: str, path: str = "spec.md") -> dict[str, Any]:
    if not isinstance(text, str):
        raise SentryError("specification text must be a string")
    if not isinstance(path, str) or not path:
        raise SentryError("path must be a nonempty string")
    quantities: dict[str, list[dict[str, Any]]] = {}
    definitions: dict[str, list[dict[str, Any]]] = {}
    uses: dict[str, list[dict[str, Any]]] = {}
    decisions: dict[str, list[dict[str, Any]]] = {}
    malformed: list[dict[str, Any]] = []
    q_re = re.compile(r"^\s*@quantity\s+([A-Za-z0-9._-]+)\s*=\s*(\d+(?:\.\d+)?)\s+([A-Za-z%]+)\s*$")
    d_re = re.compile(r"^\s*@define\s+(.+?)\s*:\s*(\S(?:.*\S)?)\s*$")
    dec_re = re.compile(r"^\s*@decision\s+([A-Za-z0-9._-]+)\s*\|\s*(pending|approved|rejected)\s*\|\s*(.+?)(?:\s*\|\s*reviewer:\s*(.*))?\s*$", re.I)
    for line_no, line in _visible_lines(text):
        for used in re.finditer(r"\[\[term:([^\]]+)\]\]", line, re.I):
            term = used.group(1).strip()
            if term:
                uses.setdefault(_norm(term), []).append(_loc(path, line_no, used.group(0)))
        if re.match(r"^\s*@quantity\b", line, re.I):
            m = q_re.match(line)
            if m:
                key, number, unit = m.groups()
                quantities.setdefault(_norm(key), []).append({"value": number, "decimal": Decimal(number), "unit": unit,
                                                               "location": _loc(path, line_no, line.strip())})
            else:
                malformed.append({"line": line_no, "text": line.strip(), "expected": "@quantity key = nonnegative-number unit"})
        elif re.match(r"^\s*@define\b", line, re.I):
            m = d_re.match(line)
            if m:
                term, definition = m.groups()
                term, definition = term.strip(), definition.strip()
                if term and definition:
                    definitions.setdefault(_norm(term), []).append({"term": term, "definition": definition,
                                                                       "location": _loc(path, line_no, line.strip())})
                else:
                    malformed.append({"line": line_no, "text": line.strip(), "expected": "@define term: definition text"})
            else:
                malformed.append({"line": line_no, "text": line.strip(), "expected": "@define term: definition text"})
        elif re.match(r"^\s*@decision\b", line, re.I):
            m = dec_re.match(line)
            if m:
                ident, state, question, reviewer = m.groups()
                decisions.setdefault(ident, []).append({"state": state.casefold(), "text": question.strip(),
                                                          "reviewer": reviewer.strip() if reviewer is not None else "",
                                                          "location": _loc(path, line_no, line.strip())})
            else:
                malformed.append({"line": line_no, "text": line.strip(), "expected": "@decision id | pending|approved|rejected | text [| reviewer: name]"})
    return {"quantities": quantities, "definitions": definitions, "uses": uses, "decisions": decisions, "malformed": malformed}


def check_spec(text: str, path: str = "spec.md") -> dict[str, Any]:
    parsed = parse_spec(text, path)
    findings: list[dict[str, Any]] = []
    for key, values in parsed["quantities"].items():
        distinct = {(v["decimal"], v["unit"]) for v in values}
        if len(distinct) > 1:
            locations = [v["location"] for v in values]
            rendered = [f"{v['value']} {v['unit']}" for v in values]
            findings.append(_finding("conflicting_quantity", key, f"Declared quantity {key} has conflicting values: {', '.join(rendered)}.", locations,
                                     {"values": rendered, "key": key}))
    for term, definitions in parsed["definitions"].items():
        variants = {_norm(d["definition"]) for d in definitions}
        if len(variants) > 1:
            findings.append(_finding("conflicting_definition", term, f"Term {definitions[0]['term']!r} has different declared definitions.",
                                     [d["location"] for d in definitions], {"definitions": [d["definition"] for d in definitions]}))
    for term, locations in parsed["uses"].items():
        if term not in parsed["definitions"]:
            findings.append(_finding("undefined_term", term, f"Explicit term reference {term!r} has no declared definition.", locations, {"term": term}))
    for ident, occurrences in parsed["decisions"].items():
        signatures = {(d["state"], _norm(d["text"])) for d in occurrences}
        if len(signatures) > 1:
            findings.append(_finding("conflicting_decision", ident, f"Decision {ident!r} has differing annotations.",
                                     [d["location"] for d in occurrences], {"occurrences": [{"state": d["state"], "text": d["text"]} for d in occurrences]}))
        else:
            d = occurrences[0]
            if d["state"] == "pending":
                findings.append(_finding("pending_decision", ident, f"Decision {ident!r} is pending: {d['text']}", [d["location"]], {"state": d["state"], "text": d["text"]}))
            elif any(not occurrence["reviewer"] for occurrence in occurrences):
                findings.append(_finding("unattributed_decision", ident, f"Decision {ident!r} is {d['state']} without a reviewer.", [x["location"] for x in occurrences], {"state": d["state"]}))
    for item in parsed["malformed"]:
        subject = f"{item['line']}\0{item['text']}"
        findings.append(_finding("malformed_annotation", subject, f"Malformed annotation at line {item['line']}; expected {item['expected']}.",
                                 [_loc(path, item["line"], item["text"])], {"expected": item["expected"]}))
    findings.sort(key=lambda f: (f["locations"][0]["line_start"], f["kind"], f["id"]))
    return {"schema_version": 1, "source": {"path": path, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()},
            "coverage": {"grammar_version": 1, "limitations": ["Checks only the documented annotation grammar; ordinary prose is not exhaustively checked.",
                                                                  "Units are compared as written; no conversion or prose-derived scope is inferred."]},
            "findings": findings}


def _validate_report(report: Any) -> None:
    if not isinstance(report, dict) or type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        raise SentryError("report schema_version must be integer 1")
    source = report.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("path"), str) or not source["path"] or not isinstance(source.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
        raise SentryError("report source must contain path and lowercase SHA-256")
    findings = report.get("findings")
    if not isinstance(findings, list):
        raise SentryError("report findings must be an array")
    ids = set()
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get("id"), str) or not finding["id"]:
            raise SentryError("each report finding must have a nonempty id")
        if finding["id"] in ids:
            raise SentryError(f"duplicate report finding id: {finding['id']}")
        ids.add(finding["id"])


def _validate_ledger(ledger: Any) -> None:
    if not isinstance(ledger, dict) or type(ledger.get("schema_version")) is not int or ledger["schema_version"] != 1:
        raise SentryError("ledger schema_version must be integer 1")
    decisions = ledger.get("decisions")
    if not isinstance(decisions, list):
        raise SentryError("ledger decisions must be an array")
    for idx, d in enumerate(decisions):
        if not isinstance(d, dict):
            raise SentryError(f"ledger decision {idx} must be an object")
        if not isinstance(d.get("finding_id"), str) or not d["finding_id"]:
            raise SentryError(f"ledger decision {idx} finding_id must be nonempty")
        digest = d.get("source_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SentryError(f"ledger decision {idx} source_sha256 must be lowercase SHA-256")
        if d.get("status") not in ("accepted", "dismissed", "deferred"):
            raise SentryError(f"ledger decision {idx} has invalid status")
        for field in ("reviewer", "note"):
            if not isinstance(d.get(field), str) or not d[field].strip():
                raise SentryError(f"ledger decision {idx} {field} must be nonempty")
        stamp = d.get("decided_at")
        if not isinstance(stamp, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z", stamp):
            raise SentryError(f"ledger decision {idx} decided_at must be UTC ISO 8601")
        try:
            datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SentryError(f"ledger decision {idx} decided_at is not a valid date/time") from exc


def record_decision(report: dict[str, Any], ledger: dict[str, Any] | None, finding_id: str,
                    status: str, reviewer: str, note: str, decided_at: str) -> dict[str, Any]:
    _validate_report(report)
    current = {"schema_version": 1, "decisions": []} if ledger is None else json.loads(json.dumps(ledger))
    _validate_ledger(current)
    if not any(f["id"] == finding_id for f in report["findings"]):
        raise SentryError(f"unknown finding id: {finding_id}")
    if status not in ("accepted", "dismissed", "deferred"):
        raise SentryError("status must be accepted, dismissed, or deferred")
    if not isinstance(reviewer, str) or not reviewer.strip():
        raise SentryError("reviewer must be nonempty")
    if not isinstance(note, str) or not note.strip():
        raise SentryError("note must be nonempty")
    record = {"finding_id": finding_id, "source_sha256": report["source"]["sha256"], "status": status,
              "reviewer": reviewer.strip(), "note": note.strip(), "decided_at": decided_at}
    _validate_ledger({"schema_version": 1, "decisions": [record]})
    current["decisions"].append(record)
    return current


def apply_ledger(report: dict[str, Any], ledger: dict[str, Any]) -> dict[str, Any]:
    _validate_report(report)
    _validate_ledger(ledger)
    result = json.loads(json.dumps(report))
    current_hash = report["source"]["sha256"]
    latest: dict[str, dict[str, Any]] = {}
    for decision in ledger["decisions"]:
        latest[decision["finding_id"]] = decision
    active: list[dict[str, Any]] = []
    for finding in result["findings"]:
        decision = latest.get(finding["id"])
        if decision:
            decision_view = dict(decision)
            decision_view["fresh"] = decision["source_sha256"] == current_hash
            finding["triage"] = decision_view
        active.append(finding)
    current_ids = {f["id"] for f in result["findings"]}
    historical = []
    for finding_id, decision in latest.items():
        if finding_id not in current_ids:
            item = dict(decision)
            item["fresh"] = decision["source_sha256"] == current_hash
            historical.append(item)
    historical.sort(key=lambda d: d["finding_id"])
    result["findings"] = active
    result["historical_decisions"] = historical
    outstanding = [f for f in active if not (f.get("triage", {}).get("fresh") and f["triage"].get("status") == "dismissed")]
    result["outstanding_count"] = len(outstanding)
    return result


def render_markdown(report: dict[str, Any]) -> str:
    _validate_report(report)
    source = report["source"]
    lines = ["# Specification review", "", f"Source: `{source['path']}`", f"SHA-256: `{source['sha256']}`", "",
             "Coverage limits: " + " ".join(report.get("coverage", {}).get("limitations", [])), ""]
    for finding in report["findings"]:
        lines.extend((f"## {finding['kind']}: {finding['subject']}", "", finding["message"], ""))
        for loc in finding["locations"]:
            lines.append(f"- `{loc['path']}:{loc['line_start']}` — {loc['text']}")
        if finding.get("evidence"):
            lines.append("- Evidence: " + json.dumps(finding["evidence"], ensure_ascii=False, sort_keys=True))
        triage = finding.get("triage")
        if triage:
            freshness = "fresh" if triage.get("fresh") else "stale"
            lines.extend((f"- Triage: {triage['status']} ({freshness}) by {triage['reviewer']}: {triage['note']}",))
        lines.append("")
    for decision in report.get("historical_decisions", []):
        lines.extend((f"## Historical decision: {decision['finding_id']}", "", f"{decision['status']} ({'fresh' if decision['fresh'] else 'stale'}) by {decision['reviewer']}: {decision['note']}", ""))
    if not report["findings"]:
        lines.append("No configured structural findings were observed. This does not establish that the specification has no contradictions.")
    if "outstanding_count" in report:
        lines.extend((f"Outstanding current findings: {report['outstanding_count']}", ""))
    return "\n".join(lines).rstrip() + "\n"

