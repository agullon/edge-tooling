"""Report search probes: counts are rendered groups/jobs, scoped to tab and day.

Run with: python3 plugins/shared/scripts/tests/test_report_filter.py
The Node harness runs the actual embedded renderer with a dependency-free DOM.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("report", SCRIPTS / "create-report.py")
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


class ReportFilterTests(unittest.TestCase):
    def test_literal_placeholder_and_existing_causal_chain_model(self):
        chain = [{"cause": "cause", "evidence": "evidence", "quote": "quote"}]
        issue = {"number": 1, "title": "add", "causal_chain": chain}
        html = REPORT.generate_html(
            "Probe", {"4.20": {"issues": [issue]}}, [], None, None,
            datetime(2026, 10, 19, tzinfo=timezone.utc),
        )
        self.assertIn('placeholder="Filter… (title, root cause, causal chain, job name)"', html)
        self.assertNotIn(r"\u2026", html)
        payload = html.split("window.REPORT_DATA = ", 1)[1].split(";</script>", 1)[0]
        data = json.loads(payload)
        self.assertEqual(data["releases_data"]["4.20"]["issues"][0]["causal_chain"], chain)

    def test_embedded_renderer_filters_and_counters(self):
        with tempfile.TemporaryDirectory() as temporary:
            renderer = Path(temporary) / "renderer.js"
            renderer.write_text(REPORT.JS)
            result = subprocess.run(
                ["node", str(Path(__file__).with_name("test_report_filter.js")), str(renderer)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS renderer filter regressions", result.stdout)
        print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
