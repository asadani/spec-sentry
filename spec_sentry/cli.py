from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .core import SentryError, apply_ledger, check_spec, record_decision, render_markdown


def _protect_inputs(output, sources):
    if output is None:
        return
    destination = Path(output).resolve()
    for source in sources:
        if source is not None and destination == Path(source).resolve():
            raise SentryError("output must not overwrite an input file; choose a separate report path")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SentryError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _read_json(path: str, optional: bool = False) -> Any:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        if optional:
            return None
        raise SentryError(f"file not found: {path}")
    except (OSError, UnicodeDecodeError) as exc:
        raise SentryError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(raw, object_pairs_hook=_pairs)
    except json.JSONDecodeError as exc:
        raise SentryError(f"invalid JSON in {path} at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def _atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
            json.dump(data, out, ensure_ascii=False, indent=2, sort_keys=True)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def _read_spec(path: str, root: str) -> tuple[str, str]:
    root_real = Path(root).resolve()
    target = (root_real / path).resolve(strict=True) if not Path(path).is_absolute() else Path(path).resolve(strict=True)
    try:
        rel = target.relative_to(root_real).as_posix()
    except ValueError as exc:
        raise SentryError(f"specification path escapes --root: {path}") from exc
    try:
        raw = target.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise SentryError(f"cannot read UTF-8 specification {rel}: {exc}") from exc
    return rel, text


def _write_text(path: str | None, text: str) -> None:
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spec-sentry", description="Check explicit structural annotations in a Markdown specification.")
    parser.add_argument("--version", action="version", version=f"spec-sentry {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("check", help="check annotations and emit a findings report")
    p.add_argument("spec")
    p.add_argument("--root", default=".")
    p.add_argument("--out")
    p = commands.add_parser("decide", help="append one reviewer decision to a ledger")
    p.add_argument("report")
    p.add_argument("--finding", required=True)
    p.add_argument("--status", choices=("accepted", "dismissed", "deferred"), required=True)
    p.add_argument("--reviewer", required=True)
    p.add_argument("--note", required=True)
    p.add_argument("--ledger", required=True)
    p.add_argument("--decided-at", help="UTC timestamp; defaults to current UTC time")
    p = commands.add_parser("report", help="render a fresh review from the spec and optional ledger")
    p.add_argument("spec")
    p.add_argument("--root", default=".")
    p.add_argument("--ledger")
    p.add_argument("--format", choices=("json", "markdown"), default="markdown")
    p.add_argument("--out")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            _protect_inputs(args.out, [Path(args.root) / args.spec])
            path, text = _read_spec(args.spec, args.root)
            report = check_spec(text, path)
            _write_text(args.out, json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            return 1 if report["findings"] else 0
        if args.command == "decide":
            _protect_inputs(args.ledger, [args.report])
            report = _read_json(args.report)
            ledger = _read_json(args.ledger, optional=True)
            timestamp = args.decided_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
            result = record_decision(report, ledger, args.finding, args.status, args.reviewer, args.note, timestamp)
            _atomic_json(Path(args.ledger), result)
            return 0
        if args.command == "report":
            _protect_inputs(args.out, [Path(args.root) / args.spec, args.ledger])
            path, text = _read_spec(args.spec, args.root)
            report = check_spec(text, path)
            if args.ledger:
                report = apply_ledger(report, _read_json(args.ledger))
            if args.format == "json":
                rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            else:
                rendered = render_markdown(report)
            _write_text(args.out, rendered)
            return 1 if report.get("outstanding_count", len(report["findings"])) else 0
    except (SentryError, OSError, ValueError) as exc:
        print(f"spec-sentry: error: {exc}", file=sys.stderr)
        return 2
    return 2

