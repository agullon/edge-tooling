"""Tests for transform-stories."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from importlib import import_module

_mod = import_module("transform-stories")
transform_story = _mod.transform_story
compute_aggregates = _mod.compute_aggregates

TODAY = "2026-07-09"


def _make_raw(key="OCPEDGE-1", summary="test", status="To Do", assignee_email=None,
              sp=None, epic_key=None, issue_type="Story", priority="Major",
              labels=None, updated=None, flagged=None, issuelinks=None):
    raw = {
        "key": key,
        "summary": summary,
        "status": {"name": status},
        "issuetype": {"name": issue_type},
        "priority": {"name": priority},
        "labels": labels or [],
        "updated": updated or TODAY,
        "created": TODAY,
    }
    if assignee_email:
        raw["assignee"] = {"email": assignee_email, "display_name": assignee_email.split("@")[0].title()}
    if sp is not None:
        raw["customfield_10028"] = sp
    if epic_key:
        raw["parent"] = {"key": epic_key}
    if flagged:
        raw["customfield_10021"] = [{"value": "Impediment"}]
    if issuelinks:
        raw["issuelinks"] = issuelinks
    return raw


class TestTransformStory(unittest.TestCase):
    def test_basic_story(self):
        raw = _make_raw(key="OCPEDGE-100", summary="Do thing", status="In Progress",
                        assignee_email="alice@redhat.com", sp=5, epic_key="OCPEDGE-10")
        result = transform_story(raw, TODAY)
        assert result["key"] == "OCPEDGE-100"
        assert result["type"] == "Story"
        assert result["assignee"] == "alice@redhat.com"
        assert result["assignee_display"] == "Alice"
        assert result["sp"] == 5
        assert result["epic_key"] == "OCPEDGE-10"

    def test_bug_sp_extracted(self):
        # Bugs are pointed like other work (edge-context decision 0003).
        raw = _make_raw(issue_type="Bug", sp=8)
        result = transform_story(raw, TODAY)
        assert result["sp"] == 8
        assert result["type"] == "Bug"

    def test_bug_unpointed_defaults_to_zero(self):
        raw = _make_raw(issue_type="Bug")
        result = transform_story(raw, TODAY)
        assert result["sp"] == 0
        assert result["type"] == "Bug"

    def test_unassigned_story(self):
        raw = _make_raw()
        result = transform_story(raw, TODAY)
        assert result["assignee"] is None
        assert result["assignee_display"] == "Unassigned"

    def test_no_sp_defaults_to_zero(self):
        raw = _make_raw()
        result = transform_story(raw, TODAY)
        assert result["sp"] == 0

    def test_no_parent_key_defaults(self):
        raw = _make_raw()
        result = transform_story(raw, TODAY)
        assert result["epic_key"] == "No Feature"

    def test_flagged_issue(self):
        raw = _make_raw(flagged=True)
        result = transform_story(raw, TODAY)
        assert result["flagged"] is True

    def test_not_flagged_by_default(self):
        raw = _make_raw()
        result = transform_story(raw, TODAY)
        assert result["flagged"] is False

    def test_stale_in_progress(self):
        raw = _make_raw(status="In Progress", updated="2026-06-20")
        result = transform_story(raw, TODAY)
        assert result["stale"] is True

    def test_not_stale_if_recently_updated(self):
        raw = _make_raw(status="In Progress", updated=TODAY)
        result = transform_story(raw, TODAY)
        assert result["stale"] is False

    def test_not_stale_if_not_in_progress(self):
        raw = _make_raw(status="To Do", updated="2026-06-01")
        result = transform_story(raw, TODAY)
        assert result["stale"] is False

    def test_priority_extracted(self):
        raw = _make_raw(priority="Blocker")
        result = transform_story(raw, TODAY)
        assert result["priority"] == "Blocker"

    def test_labels_preserved(self):
        raw = _make_raw(labels=["edge", "tnf"])
        result = transform_story(raw, TODAY)
        assert result["labels"] == ["edge", "tnf"]


class TestComputeAggregates(unittest.TestCase):
    def _story(self, key="OCPEDGE-1", assignee=None, sp=0, epic="OCPEDGE-10",
               status="To Do", issue_type="Story"):
        return {
            "key": key, "assignee": assignee, "sp": sp, "epic_key": epic,
            "status": status, "type": issue_type,
        }

    def test_empty_list(self):
        agg = compute_aggregates([])
        assert agg["stories_by_epic"] == {}
        assert agg["sp_by_assignee"] == {}
        assert agg["unassigned_stories"] == []
        assert agg["unpointed_stories"] == []

    def test_stories_grouped_by_epic(self):
        stories = [
            self._story("A-1", epic="E-1"),
            self._story("A-2", epic="E-1"),
            self._story("A-3", epic="E-2"),
        ]
        agg = compute_aggregates(stories)
        assert agg["stories_by_epic"]["E-1"] == ["A-1", "A-2"]
        assert agg["stories_by_epic"]["E-2"] == ["A-3"]

    def test_sp_by_assignee_excludes_done(self):
        stories = [
            self._story("A-1", assignee="alice@redhat.com", sp=5, status="To Do"),
            self._story("A-2", assignee="alice@redhat.com", sp=3, status="Closed"),
        ]
        agg = compute_aggregates(stories)
        assert agg["sp_by_assignee"]["alice@redhat.com"] == 5

    def test_ocpbugs_verified_is_done(self):
        stories = [
            self._story("OCPBUGS-1", assignee="alice@redhat.com", sp=0, status="Verified", issue_type="Bug"),
        ]
        agg = compute_aggregates(stories)
        assert "OCPBUGS-1" not in agg.get("unassigned_stories", [])

    def test_sp_by_assignee_includes_bugs(self):
        # Bugs load a person like other pointed work (edge-context decision 0003).
        stories = [
            self._story("A-1", assignee="alice@redhat.com", sp=5),
            self._story("A-2", assignee="alice@redhat.com", sp=3, issue_type="Bug"),
        ]
        agg = compute_aggregates(stories)
        assert agg["sp_by_assignee"]["alice@redhat.com"] == 8

    def test_sp_by_assignee_excludes_zero_sp(self):
        stories = [
            self._story("A-1", assignee="alice@redhat.com", sp=0),
        ]
        agg = compute_aggregates(stories)
        assert "alice@redhat.com" not in agg["sp_by_assignee"]

    def test_unassigned_stories_only_non_done(self):
        stories = [
            self._story("A-1", assignee=None, status="To Do"),
            self._story("A-2", assignee=None, status="Closed"),
        ]
        agg = compute_aggregates(stories)
        assert agg["unassigned_stories"] == ["A-1"]

    def test_unpointed_stories_include_bugs_exclude_done(self):
        # Unpointed bugs count like unpointed stories (edge-context decision 0003);
        # done issues are still excluded.
        stories = [
            self._story("A-1", sp=0, status="To Do"),
            self._story("A-2", sp=0, status="Closed"),
            self._story("A-3", sp=0, issue_type="Bug", status="To Do"),
            self._story("A-4", sp=5, status="To Do"),
        ]
        agg = compute_aggregates(stories)
        assert agg["unpointed_stories"] == ["A-1", "A-3"]

    def test_remaining_sp_by_epic(self):
        stories = [
            self._story("A-1", sp=5, epic="E-1", status="To Do"),
            self._story("A-2", sp=3, epic="E-1", status="Closed"),
            self._story("A-3", sp=8, epic="E-1", status="In Progress"),
        ]
        agg = compute_aggregates(stories)
        assert agg["sp_by_epic"]["E-1"] == 16
        assert agg["done_sp_by_epic"]["E-1"] == 3
        assert agg["remaining_sp_by_epic"]["E-1"] == 13

    def test_stories_by_assignee(self):
        stories = [
            self._story("A-1", assignee="alice@redhat.com"),
            self._story("A-2", assignee="bob@redhat.com"),
            self._story("A-3", assignee="alice@redhat.com"),
        ]
        agg = compute_aggregates(stories)
        assert agg["stories_by_assignee"]["alice@redhat.com"] == ["A-1", "A-3"]
        assert agg["stories_by_assignee"]["bob@redhat.com"] == ["A-2"]

    def test_multiple_assignees_capacity(self):
        stories = [
            self._story("A-1", assignee="alice@redhat.com", sp=5),
            self._story("A-2", assignee="bob@redhat.com", sp=8),
            self._story("A-3", assignee="alice@redhat.com", sp=3),
        ]
        agg = compute_aggregates(stories)
        assert agg["sp_by_assignee"]["alice@redhat.com"] == 8
        assert agg["sp_by_assignee"]["bob@redhat.com"] == 8


if __name__ == "__main__":
    unittest.main()
