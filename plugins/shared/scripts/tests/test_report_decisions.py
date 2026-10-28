"""Categorization decisions flow into the HTML report data model.

Covers the Python half of the bug-decision wiring: loading
bug-results-*.json, attaching decisions to matched candidates, and the
create-report.py entry point applying (and ignoring) decisions end to
end. The renderer half (button gating, badges) is covered by the Node
harness in test_report_filter.js.

Run with: python3 plugins/shared/scripts/tests/test_report_decisions.py
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

STAMP = datetime(2026, 10, 28, tzinfo=timezone.utc)


def payload(html):
    return json.loads(html.split("window.REPORT_DATA = ", 1)[1].split(";</script>", 1)[0])


class DecisionAttachmentTests(unittest.TestCase):
    def test_decision_attached_to_matching_candidate(self):
        candidates = [{"error_signature": "greenboot timeout",
                       "duplicates": [], "regressions": []}]
        decisions = {"greenboot timeout": {
            "action": "skip", "jira_key": "", "skip_category": "stale_regression",
            "reason": "Stale failure predating fix for OCPBUGS-4242"}}
        html = REPORT.generate_html(
            "Probe", {"4.20": {"issues": [{"number": 1, "title": "greenboot timeout"}]}},
            candidates, None, None, STAMP, bug_decisions=decisions)
        issue = payload(html)["releases_data"]["4.20"]["issues"][0]
        self.assertEqual(issue["bug_match"]["error_signature"], "greenboot timeout")
        self.assertEqual(issue["bug_match"]["decision"]["action"], "skip")
        self.assertEqual(issue["bug_match"]["decision"]["skip_category"],
                         "stale_regression")

    def test_unknown_signature_left_undecided(self):
        candidates = [{"error_signature": "greenboot timeout",
                       "duplicates": [], "regressions": []}]
        decisions = {"some other signature": {"action": "suggest", "jira_key": "",
                                              "skip_category": "", "reason": ""}}
        html = REPORT.generate_html(
            "Probe", {"4.20": {"issues": [{"number": 1, "title": "greenboot timeout"}]}},
            candidates, None, None, STAMP, bug_decisions=decisions)
        issue = payload(html)["releases_data"]["4.20"]["issues"][0]
        self.assertIn("bug_match", issue)
        self.assertNotIn("decision", issue["bug_match"])

    def test_pr_issues_get_decisions(self):
        candidates = [{"error_signature": "image pull timeout",
                       "duplicates": [], "regressions": []}]
        decisions = {"image pull timeout": {
            "action": "linked", "jira_key": "USHIFT-1234", "skip_category": "",
            "reason": "Linked to existing bug USHIFT-1234"}}
        pr_data = {"prs": [{"number": 7, "issues": [
            {"number": 1, "title": "image pull timeout"}]}]}
        html = REPORT.generate_html(
            "Probe", {"4.20": {"issues": []}}, candidates, pr_data, None, STAMP,
            bug_decisions=decisions)
        issue = payload(html)["pr_data"]["prs"][0]["issues"][0]
        self.assertEqual(issue["bug_match"]["decision"]["action"], "linked")
        self.assertEqual(issue["bug_match"]["decision"]["jira_key"], "USHIFT-1234")

    def test_no_decisions_keeps_plain_bug_matches(self):
        candidates = [{"error_signature": "greenboot timeout",
                       "duplicates": [{"key": "USHIFT-1"}], "regressions": []}]
        html = REPORT.generate_html(
            "Probe", {"4.20": {"issues": [{"number": 1, "title": "greenboot timeout"}]}},
            candidates, None, None, STAMP)
        issue = payload(html)["releases_data"]["4.20"]["issues"][0]
        self.assertEqual(issue["bug_match"]["duplicates"][0]["key"], "USHIFT-1")
        self.assertNotIn("decision", issue["bug_match"])


class LoadBugDecisionsTests(unittest.TestCase):
    def test_merges_files_first_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "bug-results-4.19.json").write_text(json.dumps({"mode": "search", "results": [
                {"error_signature": "sig a", "action": "suggest", "jira_key": "",
                 "skip_category": "", "reason": "first file"},
                {"error_signature": "sig b", "action": "skip", "jira_key": "",
                 "skip_category": "infrastructure", "reason": "infra"}]}))
            (tmp / "bug-results-4.20.json").write_text(json.dumps({"mode": "search", "results": [
                {"error_signature": "sig a", "action": "linked", "jira_key": "USHIFT-9",
                 "skip_category": "", "reason": "second file"},
                {"error_signature": "sig c", "action": "suggest", "jira_key": "",
                 "skip_category": "", "reason": "second file"}]}))
            decisions = REPORT.load_bug_decisions(
                sorted(tmp.glob("bug-results-*.json")))
        self.assertEqual(sorted(decisions), ["sig a", "sig b", "sig c"])
        self.assertEqual(decisions["sig a"]["reason"], "first file")
        self.assertEqual(decisions["sig c"]["reason"], "second file")

    def test_skips_invalid_files_and_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "bug-results-broken.json").write_text("{not json")
            (tmp / "bug-results-empty.json").write_text(json.dumps({"results": []}))
            (tmp / "bug-results-real.json").write_text(json.dumps({"results": [
                {"error_signature": "", "action": "skip"},
                {"action": "suggest"},
                {"error_signature": "sig", "action": "suggest", "jira_key": "",
                 "skip_category": "", "reason": "ok"}]}))
            decisions = REPORT.load_bug_decisions(
                sorted(tmp.glob("bug-results-*.json")))
        self.assertEqual(list(decisions), ["sig"])
        self.assertEqual(decisions["sig"]["reason"], "ok")


class CreateReportEndToEndTests(unittest.TestCase):
    def test_main_applies_and_ignores_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            (workdir / "jobs").mkdir()
            (workdir / "bugs").mkdir()
            (workdir / "jobs" / "release-4.20-summary.json").write_text(json.dumps({
                "total_failed": 3, "issues": [
                    {"number": 1, "title": "greenboot timeout", "severity": "HIGH",
                     "failure_type": "test", "root_cause": "node failed to boot"},
                    {"number": 2, "title": "image pull timeout", "severity": "MEDIUM",
                     "failure_type": "test", "root_cause": "registry unreachable"},
                    {"number": 3, "title": "node ran out of disk", "severity": "LOW",
                     "failure_type": "test", "root_cause": "disk full"},
                ]}))
            (workdir / "bugs" / "bug-matches-4.20.json").write_text(json.dumps({
                "source": "4.20", "candidates": [
                    {"error_signature": "greenboot timeout", "duplicates": [],
                     "regressions": [{"key": "OCPBUGS-4242"}]},
                    {"error_signature": "image pull timeout",
                     "duplicates": [{"key": "USHIFT-1234"}], "regressions": []},
                    {"error_signature": "node ran out of disk", "duplicates": [],
                     "regressions": []},
                ]}))
            (workdir / "bugs" / "bug-results-4.20.json").write_text(json.dumps({
                "mode": "search", "results": [
                    {"error_signature": "greenboot timeout", "action": "skip",
                     "jira_key": "", "skip_category": "stale_regression",
                     "reason": "Stale failure predating fix for OCPBUGS-4242"},
                    {"error_signature": "image pull timeout", "action": "linked",
                     "jira_key": "USHIFT-1234", "skip_category": "",
                     "reason": "Linked to existing bug USHIFT-1234"},
                    {"error_signature": "node ran out of disk", "action": "suggest",
                     "jira_key": "", "skip_category": "",
                     "reason": "No existing bugs found — suggest filing a new bug"},
                ]}))
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "create-report.py"),
                 "--component", "microshift", "--workdir", str(workdir),
                 "--ignore", "USHIFT-1234", "4.20"],
                capture_output=True, text=True, check=True)
            self.assertIn("Bug categorization: 1 result file(s)", result.stdout)
            html = (workdir / "report-microshift-ci-doctor.html").read_text()
            issues = payload(html)["releases_data"]["4.20"]["issues"]
            by_title = {issue["title"]: issue for issue in issues}
            self.assertEqual(
                by_title["greenboot timeout"]["bug_match"]["decision"]["action"],
                "skip")
            self.assertEqual(
                by_title["node ran out of disk"]["bug_match"]["decision"]["action"],
                "suggest")
            # USHIFT-1234 is closed (--ignore): its linked decision must be
            # dropped and the candidate must fall back to suggest affordances.
            self.assertNotIn("decision", by_title["image pull timeout"]["bug_match"])


if __name__ == "__main__":
    unittest.main()
