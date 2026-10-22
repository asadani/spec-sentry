import unittest
from spec_sentry.core import SentryError, check_spec, record_decision

class ReviewEdges(unittest.TestCase):
    def test_long_fence_contains_short_fence_example(self):
        text='````markdown\n```\n@quantity max.size = 10 MB\n````\n@quantity max.size = 20 MB\n'
        self.assertEqual(check_spec(text)['findings'],[])

    def test_impossible_decision_date_rejected(self):
        report=check_spec('@decision sharing | pending | Resolve access.\n')
        with self.assertRaises(SentryError):
            record_decision(report,None,report['findings'][0]['id'],'accepted','Reviewer','Review access','2026-99-99T25:00:00Z')

    def test_check_cannot_replace_its_specification(self):
        import contextlib, io, tempfile
        from pathlib import Path
        from spec_sentry.cli import main
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'spec.md'
            source.write_text('@quantity max.size = 10 MB\n')
            before=source.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                code=main(['check','spec.md','--root',str(root),'--out',str(source)])
            self.assertEqual(code,2)
            self.assertEqual(source.read_bytes(),before)
