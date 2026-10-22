"""Tests for transform-sprint-issues — sprint history and resolution fields."""

import sys
import os
import json
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from importlib import import_module

_mod = import_module("transform-sprint-issues")
transform_issue = _mod.transform_issue
_none_if_null_string = _mod._none_if_null_string

extract_epic_key = import_module("_jira_transforms").extract_epic_key

TODAY = "2026-07-09"


def _raw(key="OCPEDGE-1", status="Done", issue_type="Story",
         sprints=None, resolutiondate=None):
    raw = {
        "key": key,
        "summary": "s",
        "status": {"name": status},
        "issuetype": {"name": issue_type},
        "created": TODAY,
        "updated": TODAY,
    }
    if sprints is not None:
        raw["customfield_10020"] = sprints
    if resolutiondate is not None:
        raw["resolutiondate"] = resolutiondate
    return raw


class TestSprintHistory(unittest.TestCase):
    def test_ordered_sprint_ids_from_dicts(self):
        issue = transform_issue(
            _raw(sprints=[{"id": 11, "name": "S11"}, {"id": 12, "name": "S12"}]), TODAY)
        assert issue["sprints"] == [11, 12]

    def test_preserves_all_sprint_ids(self):
        # The transform just carries the ids through (order is not relied on);
        # compute-velocity picks the finishing sprint by max id.
        issue = transform_issue(_raw(sprints=[{"id": 6, "name": "B"}, {"id": 5, "name": "A"}]), TODAY)
        assert set(issue["sprints"]) == {5, 6}

    def test_drops_none_sprint_ids(self):
        issue = transform_issue(_raw(sprints=["unparseable", {"id": 7, "name": "C"}]), TODAY)
        assert issue["sprints"] == [7]

    def test_no_sprint_field_yields_empty_list(self):
        issue = transform_issue(_raw(sprints=None), TODAY)
        assert issue["sprints"] == []


class TestSprintDetails(unittest.TestCase):
    def test_carries_end_dates_non_chronological(self):
        # Sprints out of id order, each with an end date; sprint_details carries the
        # id + normalized end so compute-velocity can pick the latest-ending one.
        issue = transform_issue(_raw(sprints=[
            {"id": 7, "name": "S7", "endDate": "2026-05-30T00:00:00.000Z"},
            {"id": 4, "name": "S4", "endDate": "2026-06-30T00:00:00.000Z"},
        ]), TODAY)
        assert issue["sprint_details"] == [
            {"id": 7, "end": "2026-05-30"},
            {"id": 4, "end": "2026-06-30"},
        ]

    def test_falls_back_to_complete_date(self):
        # endDate absent but completeDate present: use completeDate for end.
        issue = transform_issue(_raw(sprints=[
            {"id": 5, "name": "S5", "completeDate": "2026-06-15T12:00:00.000Z"},
        ]), TODAY)
        assert issue["sprint_details"] == [{"id": 5, "end": "2026-06-15"}]

    def test_missing_dates_yield_none(self):
        # No end/complete date: end is None (compute-velocity falls back to max id).
        issue = transform_issue(_raw(sprints=[
            {"id": 5, "name": "S5"}, {"id": 6, "name": "S6"},
        ]), TODAY)
        assert issue["sprint_details"] == [{"id": 5, "end": None}, {"id": 6, "end": None}]


class TestResolved(unittest.TestCase):
    def test_resolution_date_normalized(self):
        issue = transform_issue(_raw(resolutiondate="2026-06-10T14:03:00.000+0000"), TODAY)
        assert issue["resolved"] == "2026-06-10"

    def test_unresolved_is_none(self):
        issue = transform_issue(_raw(resolutiondate=None), TODAY)
        assert issue["resolved"] is None


class TestSprintMeta(unittest.TestCase):
    def test_main_reads_sprint_meta(self):
        # --sprint-meta supplies sprint_id/name/start/end without shell interpolation.
        d = tempfile.mkdtemp()
        inp = os.path.join(d, "raw.json")
        meta = os.path.join(d, "meta.json")
        out = os.path.join(d, "out.json")
        with open(inp, "w") as fh:
            json.dump({"issues": [_raw(key="OCPEDGE-9")]}, fh)
        with open(meta, "w") as fh:
            json.dump({"sprint_id": 42, "sprint_name": "Sprint; rm -rf /",
                       "sprint_start": "2026-06-01", "sprint_end": "2026-06-30"}, fh)
        argv = ["prog", "--input", inp, "--output", out, "--sprint-meta", meta, "--today", TODAY]
        old = sys.argv
        sys.argv = argv
        try:
            _mod.main()
        finally:
            sys.argv = old
        with open(out) as fh:
            result = json.load(fh)
        assert result["sprint_id"] == 42
        assert result["sprint_name"] == "Sprint; rm -rf /"  # carried as data, never executed
        assert result["sprint_start"] == "2026-06-01"
        assert result["sprint_end"] == "2026-06-30"

    def test_null_string_dates_coerced_to_none(self):
        # A template that emits the string "null" (not bare JSON null) must not
        # be read as a real date — it is coerced to None.
        d = tempfile.mkdtemp()
        inp = os.path.join(d, "raw.json")
        meta = os.path.join(d, "meta.json")
        out = os.path.join(d, "out.json")
        with open(inp, "w") as fh:
            json.dump({"issues": [_raw(key="OCPEDGE-9")]}, fh)
        with open(meta, "w") as fh:
            json.dump({"sprint_id": 42, "sprint_name": "S",
                       "sprint_start": "null", "sprint_end": ""}, fh)
        argv = ["prog", "--input", inp, "--output", out, "--sprint-meta", meta, "--today", TODAY]
        old = sys.argv
        sys.argv = argv
        try:
            _mod.main()
        finally:
            sys.argv = old
        with open(out) as fh:
            result = json.load(fh)
        assert result["sprint_start"] is None
        assert result["sprint_end"] is None


class TestNoneIfNullString(unittest.TestCase):
    def test_coerces_null_variants(self):
        for v in ("null", "NULL", "none", "", "  ", "None"):
            assert _none_if_null_string(v) is None

    def test_preserves_real_values(self):
        assert _none_if_null_string("2026-06-01") == "2026-06-01"
        assert _none_if_null_string(None) is None


class TestExtractEpicKey(unittest.TestCase):
    """Parent-first epic resolution with a legacy Epic Link fallback."""

    def test_parent_only(self):
        # Native parent is an Epic, no Epic Link → use the parent key.
        issue = {"parent": {"key": "OCPEDGE-100", "issuetype": {"name": "Epic"}}}
        assert extract_epic_key(issue) == "OCPEDGE-100"

    def test_epic_link_only(self):
        # No native parent, legacy Epic Link set → fall back to customfield_10014.
        issue = {"customfield_10014": "OCPEDGE-200"}
        assert extract_epic_key(issue) == "OCPEDGE-200"

    def test_both_set_prefers_parent(self):
        # Both present → the native Epic parent wins over the legacy field.
        issue = {
            "parent": {"key": "OCPEDGE-100", "issuetype": {"name": "Epic"}},
            "customfield_10014": "OCPEDGE-200",
        }
        assert extract_epic_key(issue) == "OCPEDGE-100"

    def test_non_epic_parent_falls_back(self):
        # A non-Epic parent (e.g. a sub-task's Story) must not shadow the Epic Link.
        issue = {
            "parent": {"key": "OCPEDGE-50", "issuetype": {"name": "Story"}},
            "customfield_10014": "OCPEDGE-200",
        }
        assert extract_epic_key(issue) == "OCPEDGE-200"

    def test_non_epic_parent_without_epic_link_is_no_epic(self):
        issue = {"parent": {"key": "OCPEDGE-50", "issuetype": {"name": "Story"}}}
        assert extract_epic_key(issue) == "No Epic"


if __name__ == "__main__":
    unittest.main()
