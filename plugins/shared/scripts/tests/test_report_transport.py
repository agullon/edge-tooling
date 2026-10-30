"""Run with: python3 plugins/shared/scripts/tests/test_report_transport.py."""

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


class ReportTransportTests(unittest.TestCase):
    def test_censored_serialization_and_actual_consumers(self):
        metrics = {
            "cpu": {"timestamps": ["now", "later"], "user": [10, 20], "sys": [1, 2], "iowait": [0, 1]},
            "mem": {"timestamps": ["now", "later"], "used_gb": [1, 2], "cached_gb": [0, 1], "total_gb": [8, 8]},
            "io": {"timestamps": ["now", "later"], "bi": [1, 2], "bo": [2, 3], "await": [1, 2], "aveq": [0.9123456999999999, 2]},
            "disk": {"timestamps": ["now", "later"], "partitions": [
                {"device": "/dev/sda4", "mountdir": "/", "capacity_gb": 120.5,
                 "used_pct": [0.9123456999999999, 2], "used_gb": [float("inf"), 2.41]},
                {"device": "/dev/sdb1", "mountdir": "/var/lib/containers", "capacity_gb": 250,
                 "used_pct": [50, float("nan")], "used_gb": [125, "invalid"]},
            ]},
        }
        issue = {"number": 1, "title": "transport probe", "affected_jobs": [
            {"name": "probe", "url": "https://example.invalid/123"}]}
        with tempfile.TemporaryDirectory() as temporary:
            graph = Path(temporary) / "123"
            graph.mkdir()
            for filename, kind in REPORT._METRIC_FILES:
                (graph / filename).write_text(json.dumps(metrics[kind]))
            original_graphs = REPORT._GRAPHS_DIR
            REPORT._GRAPHS_DIR = temporary
            REPORT._graph_cache.clear()
            try:
                html = REPORT.generate_html(
                    "Probe", {"4.20": {"issues": [issue], "total_failed": 1}}, [], None, None,
                    datetime(2026, 10, 19, tzinfo=timezone.utc),
                )
            finally:
                REPORT._GRAPHS_DIR = original_graphs
                REPORT._graph_cache.clear()
            self.assertIn('"0.9123456999999999"', html)
            html = html.replace("123456", "XXXXXX")
            self.assertIn('"0.9XXXXXX999999999"', html)
            renderer = Path(temporary) / "renderer.js"
            renderer.write_text(REPORT.JS)
            report = Path(temporary) / "report.html"
            report.write_text(html)
            result = subprocess.run([
                "node", str(Path(__file__).with_name("test_report_filter.js")),
                str(renderer), "", "--regex-tests", str(report), "--transport-tests",
            ], capture_output=True, text=True, check=False, timeout=90)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS censored report transport", result.stdout)
        print(result.stdout.strip())

    def test_partition_schema_and_numeric_samples(self):
        timestamps = ["2026-10-19T01:02:03Z", "2026-10-19T01:02:04Z"]
        invalid = [True, False, "invalid", {}, [], float("nan"), float("inf"), -float("inf"), None]
        for samples in ([], [0, 12.5, -1], invalid):
            with self.subTest(samples=samples):
                partition = {"device": "/dev/sda4", "mountdir": "/", "capacity_gb": 120.5,
                             "used_pct": samples, "used_gb": samples}
                sanitized = REPORT._sanitize_metrics({"timestamps": timestamps, "partitions": [partition]})
                expected = [None] * len(invalid) if samples is invalid else samples
                self.assertEqual(sanitized, {"timestamps": timestamps, "partitions": [
                    {"device": "/dev/sda4", "mountdir": "/", "capacity_gb": 120.5,
                     "used_pct": expected, "used_gb": expected}]})
                for kind in ("cpu", "mem", "io"):
                    self.assertEqual(REPORT._sanitize_metrics({"timestamps": timestamps, kind: samples}),
                                     {"timestamps": timestamps, kind: expected})
        self.assertEqual(REPORT._sanitize_metrics({}), {})
        self.assertEqual(REPORT._sanitize_metrics({"partitions": []}), {"partitions": []})
        self.assertEqual(REPORT._sanitize_metrics({"user": [{"unexpected": 1}]}), {"user": [None]})

    def test_loaded_metrics_and_pr_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            graph = Path(temporary) / "123"
            graph.mkdir()
            (graph / "io.json").write_text(json.dumps({"aveq": [0.9123456999999999, None]}))
            (graph / "disk.json").write_text(json.dumps({
                "timestamps": ["2026-10-19T01:02:03Z", "2026-10-19T01:02:04Z"],
                "partitions": [{"device": "/dev/sda4", "mountdir": "/", "capacity_gb": 120.5,
                                "used_pct": [0.9123456999999999, 0], "used_gb": [None, 0]}],
            }))
            original_graphs = REPORT._GRAPHS_DIR
            REPORT._GRAPHS_DIR = temporary
            REPORT._graph_cache.clear()
            try:
                html = REPORT.generate_html(
                    "Probe", {}, [], {"prs": [{"number": 7, "issues": [{
                        "title": "probe", "affected_jobs": [{"url": "https://example.invalid/123"}]
                    }]}]}, None, datetime(2026, 10, 19, tzinfo=timezone.utc),
                )
            finally:
                REPORT._GRAPHS_DIR = original_graphs
                REPORT._graph_cache.clear()
        payload = html.split("window.REPORT_DATA = ", 1)[1].split(";</script>", 1)[0]
        parsed = json.loads(payload.replace("123456", "XXXXXX"))
        self.assertEqual(parsed["pr_data"]["prs"][0]["issues"][0]["affected_jobs"][0]["metrics"]["io"]["aveq"],
                         ["0.9XXXXXX999999999", None])
        disk = parsed["pr_data"]["prs"][0]["issues"][0]["affected_jobs"][0]["metrics"]["disk"]
        self.assertEqual(disk, {
            "timestamps": ["2026-10-19T01:02:03Z", "2026-10-19T01:02:04Z"],
            "partitions": [{"device": "/dev/sda4", "mountdir": "/", "capacity_gb": "120.5",
                            "used_pct": ["0.9XXXXXX999999999", "0"], "used_gb": [None, "0"]}],
        })


if __name__ == "__main__":
    unittest.main()
