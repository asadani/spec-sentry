import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_cli_check_decide_report_and_errors(self):
        help_result = subprocess.run([sys.executable, "-m", "spec_sentry", "--help"], cwd=REPO, text=True, capture_output=True)
        version_result = subprocess.run([sys.executable, "-m", "spec_sentry", "--version"], cwd=REPO, text=True, capture_output=True)
        self.assertEqual(help_result.returncode, 0)
        self.assertEqual(version_result.stdout.strip(), "spec-sentry 0.1.0")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            spec = root / "sharing.md"
            spec.write_bytes((REPO / "fixtures" / "sharing-spec.md").read_bytes())
            findings = root / "findings.json"
            result = subprocess.run([sys.executable, "-m", "spec_sentry", "check", "sharing.md", "--root", str(root), "--out", str(findings)], cwd=REPO, text=True, capture_output=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            report = json.loads(findings.read_text())
            finding_id = next(f["id"] for f in report["findings"] if f["kind"] == "pending_decision")
            ledger = root / "decisions.json"
            result = subprocess.run([sys.executable, "-m", "spec_sentry", "decide", str(findings), "--finding", finding_id, "--status", "dismissed", "--reviewer", "Demo reviewer", "--note", "Keep this item for discussion.", "--decided-at", "2026-10-22T01:00:00Z", "--ledger", str(ledger)], cwd=REPO, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            review = root / "review.md"
            result = subprocess.run([sys.executable, "-m", "spec_sentry", "report", "sharing.md", "--root", str(root), "--ledger", str(ledger), "--format", "markdown", "--out", str(review)], cwd=REPO, text=True, capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("dismissed (fresh)", review.read_text())
            bad = root / "bad.json"
            bad.write_text("{", encoding="utf-8")
            result = subprocess.run([sys.executable, "-m", "spec_sentry", "decide", str(bad), "--finding", "x", "--status", "dismissed", "--reviewer", "a", "--note", "b", "--ledger", str(ledger)], cwd=REPO, text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
