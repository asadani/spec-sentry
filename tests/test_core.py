import json
import unittest

from spec_sentry.core import (SentryError, apply_ledger, check_spec,
                              record_decision, render_markdown)


SPEC = """@quantity preview.max_size = 10 MB
@quantity preview.max_size = 10.0 MB
@quantity preview.max_size = 10 GB
[[term:Unlisted noun]]
@define workspace: A shared area.
[[term: WORKSPACE  ]]
@decision share | pending | Who may invite guests?
@decision approval | approved | Keep audit logs. | reviewer: Sam
```md
@quantity preview.max_size = 100 TB
@decision broken
```
@quantity broken = -1 MB
@define broken
@decision approval | approved | Keep audit logs.
@decision approval | rejected | Delete them.
"""


class CoreTests(unittest.TestCase):
    def test_annotations_code_fences_findings_and_exact_locations(self):
        report = check_spec(SPEC, "spec.md")
        kinds = [f["kind"] for f in report["findings"]]
        self.assertIn("conflicting_quantity", kinds)
        quantity = next(f for f in report["findings"] if f["kind"] == "conflicting_quantity")
        self.assertEqual([x["line_start"] for x in quantity["locations"]], [1, 2, 3])
        self.assertIn("undefined_term", kinds)
        self.assertIn("pending_decision", kinds)
        self.assertIn("conflicting_decision", kinds)
        self.assertIn("malformed_annotation", kinds)
        self.assertNotIn("fake annotation", [f["subject"] for f in report["findings"]])
        self.assertEqual(report["schema_version"], 1)

    def test_equal_decimal_and_normalized_terms(self):
        report = check_spec("@quantity x = 10 MB\n@quantity x = 10.0 MB\n@define Foo Bar: yes\n[[term:foo   bar]]\n")
        self.assertEqual(report["findings"], [])

    def test_ledger_latest_freshness_history_and_no_mutation(self):
        report = check_spec("@quantity x = 1 MB\n@quantity x = 2 MB\n", "a.md")
        finding = report["findings"][0]
        ledger = record_decision(report, None, finding["id"], "dismissed", "Reviewer", "Intentional during migration", "2026-10-22T01:00:00Z")
        before = json.dumps(ledger, sort_keys=True)
        joined = apply_ledger(report, ledger)
        self.assertEqual(joined["outstanding_count"], 0)
        self.assertTrue(joined["findings"][0]["triage"]["fresh"])
        revised = check_spec("@quantity x = 1 MB\n@quantity x = 3 MB\n", "a.md")
        stale = apply_ledger(revised, ledger)
        self.assertEqual(stale["outstanding_count"], 1)
        self.assertFalse(stale["findings"][0]["triage"]["fresh"])
        fixed = check_spec("No annotations remain.\n", "a.md")
        history = apply_ledger(fixed, ledger)
        self.assertEqual(len(history["historical_decisions"]), 1)
        self.assertEqual(json.dumps(ledger, sort_keys=True), before)
        self.assertIn("Historical decision", render_markdown(history))

    def test_invalid_decision_does_not_mutate_ledger(self):
        report = check_spec("@decision x | pending | Decide.\n")
        ledger = {"schema_version": 1, "decisions": []}
        before = json.dumps(ledger, sort_keys=True)
        with self.assertRaises(SentryError):
            record_decision(report, ledger, "no-such-id", "dismissed", "R", "note", "2026-10-22T01:00:00Z")
        self.assertEqual(json.dumps(ledger, sort_keys=True), before)
        with self.assertRaises(SentryError):
            record_decision(report, ledger, report["findings"][0]["id"], "dismissed", " ", "note", "2026-10-22T01:00:00Z")

    def test_invalid_schema_versions_and_ledger_types(self):
        valid = check_spec("@decision x | pending | Decide.\n")
        for version in (True, 1.0):
            with self.assertRaises(SentryError):
                apply_ledger(dict(valid, schema_version=version), {"schema_version": 1, "decisions": []})
        with self.assertRaises(SentryError):
            apply_ledger(valid, {"schema_version": 1, "decisions": [{"finding_id": [], "source_sha256": valid["source"]["sha256"], "status": "dismissed", "reviewer": "a", "note": "b", "decided_at": "2026-10-22T01:00:00Z"}]})


if __name__ == "__main__":
    unittest.main()
