"""Tests for compute-velocity.py — team velocity from closed sprints."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from importlib import import_module

_mod = import_module("compute-velocity")
roster_usernames = _mod.roster_usernames
is_team_owned = _mod.is_team_owned
compute_sprint_velocity = _mod.compute_sprint_velocity
compute_velocity = _mod.compute_velocity
_finishing_sprint_id = _mod._finishing_sprint_id

_sprint_mod = import_module("transform-sprint-issues")
transform_issue = _sprint_mod.transform_issue


def _roster(*usernames):
    return {"members": [{"username": u, "display_name": u.split("@")[0].title()} for u in usernames]}


def _issue(key="OCPEDGE-1", status="Closed", sp=5, assignee=None, assignee_display=None,
           qa_contact=None, qa_contact_display=None, sprints=None, resolved=None,
           sprint_details=None):
    # Status defaults to "Closed": law 07 done-state for non-OCPBUGS issues (a bare
    # "Done" no longer counts as done for velocity — see is_sprint_done).
    return {"key": key, "status": status, "sp": sp,
            "assignee": assignee, "assignee_display": assignee_display,
            "qa_contact": qa_contact, "qa_contact_display": qa_contact_display,
            "sprints": sprints, "resolved": resolved,
            "sprint_details": sprint_details}


def _sprint(sprint_id=1, name="Sprint 1", issues=None, sprint_start=None, sprint_end=None):
    issues = issues or []
    # Default each issue's finishing sprint to this sprint unless the test set it
    # explicitly (lets carry-over tests override while keeping simple cases terse).
    for i in issues:
        if i.get("sprints") is None and i.get("resolved") is None:
            i["sprints"] = [sprint_id]
    return {"sprint_id": sprint_id, "sprint_name": name, "issues": issues,
            "sprint_start": sprint_start, "sprint_end": sprint_end}


class TestRosterUsernames(unittest.TestCase):
    def test_extracts_usernames(self):
        assert roster_usernames(_roster("a@x.com", "b@x.com")) == {"a@x.com", "b@x.com"}

    def test_empty_roster(self):
        assert roster_usernames({"members": []}) == set()

    def test_missing_members_key(self):
        assert roster_usernames({}) == set()


class TestIsTeamOwned(unittest.TestCase):
    def test_assignee_on_roster(self):
        roster = _roster("a@x.com")
        assert is_team_owned(_issue(assignee="a@x.com"), roster) is True

    def test_qa_contact_on_roster(self):
        # law 00: QA Contact on the roster also makes the issue team-owned.
        roster = _roster("a@x.com")
        assert is_team_owned(_issue(assignee="other@x.com", qa_contact="a@x.com"), roster) is True

    def test_neither_on_roster(self):
        roster = _roster("a@x.com")
        assert is_team_owned(_issue(assignee="other@x.com", qa_contact="nobody@x.com"), roster) is False

    def test_matches_by_display_name_when_email_null(self):
        # Live Jira returns email: null; the transform keeps the display name so the
        # issue still matches a roster member (must-fix: match by display name too).
        roster = {"members": [{"username": "alice@x.com", "display_name": "Alice Smith"}]}
        issue = _issue(assignee=None, assignee_display="Alice Smith")
        assert is_team_owned(issue, roster) is True

    def test_matches_by_qa_display_name_when_email_null(self):
        roster = {"members": [{"username": "alice@x.com", "display_name": "Alice Smith"}]}
        issue = _issue(assignee="outsider@x.com", qa_contact=None, qa_contact_display="Alice Smith")
        assert is_team_owned(issue, roster) is True


class TestComputeSprintVelocity(unittest.TestCase):
    def test_sums_done_team_sp(self):
        roster = _roster("a@x.com")
        issues = [
            _issue("S-1", status="Closed", sp=5, assignee="a@x.com", sprints=[1]),
            _issue("S-2", status="Closed", sp=3, assignee="a@x.com", sprints=[1]),
        ]
        sp, count, skipped, unmatched_sp, unmatched_owners = compute_sprint_velocity(
            issues, roster, sprint_id=1)
        assert sp == 8
        assert count == 2
        assert skipped == 0
        assert unmatched_sp == 0
        assert unmatched_owners == []

    def test_excludes_unfinished(self):
        roster = _roster("a@x.com")
        issues = [
            _issue("S-1", status="Closed", sp=5, assignee="a@x.com", sprints=[1]),
            _issue("S-2", status="In Progress", sp=8, assignee="a@x.com", sprints=[1]),
        ]
        sp, count, skipped, _, _ = compute_sprint_velocity(issues, roster, sprint_id=1)
        assert sp == 5
        assert count == 1

    def test_bare_done_status_is_not_done(self):
        # law 07: a non-OCPBUGS issue is done only at Closed, not at "Done".
        roster = _roster("a@x.com")
        issues = [_issue("S-1", status="Done", sp=5, assignee="a@x.com", sprints=[1])]
        sp, count, _, _, _ = compute_sprint_velocity(issues, roster, sprint_id=1)
        assert sp == 0 and count == 0

    def test_excludes_non_team(self):
        roster = _roster("a@x.com")
        issues = [
            _issue("S-1", status="Closed", sp=5, assignee="a@x.com", sprints=[1]),
            _issue("S-2", status="Closed", sp=8, assignee="outsider@x.com",
                   assignee_display="Out Sider", sprints=[1]),
        ]
        sp, count, skipped, unmatched_sp, unmatched_owners = compute_sprint_velocity(
            issues, roster, sprint_id=1)
        assert sp == 5
        assert count == 1
        # Done work by a non-roster owner finishing here is surfaced as unmatched.
        assert unmatched_sp == 8
        assert unmatched_owners == ["Out Sider"]

    def test_bugs_count(self):
        # OCPBUGS bugs are done at Verified (law 07) and carry real SP (decision 0003).
        roster = _roster("a@x.com")
        issues = [_issue("OCPBUGS-1", status="Verified", sp=3, assignee="a@x.com", sprints=[1])]
        sp, count, _, _, _ = compute_sprint_velocity(issues, roster, sprint_id=1)
        assert sp == 3

    def test_ocpedge_bug_verified_is_not_done(self):
        # Only OCPBUGS bugs get the Verified done-state; an OCPEDGE issue needs Closed.
        roster = _roster("a@x.com")
        issues = [_issue("OCPEDGE-9", status="Verified", sp=3, assignee="a@x.com", sprints=[1])]
        sp, count, _, _, _ = compute_sprint_velocity(issues, roster, sprint_id=1)
        assert sp == 0 and count == 0

    def test_carryover_counts_only_in_finishing_sprint(self):
        roster = _roster("a@x.com")
        carried = _issue("S-1", status="Closed", sp=5, assignee="a@x.com", sprints=[1, 2])
        sp1, count1, _, _, _ = compute_sprint_velocity([carried], roster, sprint_id=1)
        assert sp1 == 0 and count1 == 0
        sp2, count2, _, _, _ = compute_sprint_velocity([carried], roster, sprint_id=2)
        assert sp2 == 5 and count2 == 1

    def test_finishing_sprint_is_max_id_not_list_position(self):
        roster = _roster("a@x.com")
        carried = _issue("S-1", status="Closed", sp=5, assignee="a@x.com", sprints=[2, 1])
        sp1, count1, _, _, _ = compute_sprint_velocity([carried], roster, sprint_id=1)
        assert sp1 == 0 and count1 == 0
        sp2, count2, _, _, _ = compute_sprint_velocity([carried], roster, sprint_id=2)
        assert sp2 == 5 and count2 == 1

    def test_none_sprint_ids_are_ignored(self):
        roster = _roster("a@x.com")
        issue = _issue("S-1", status="Closed", sp=5, assignee="a@x.com", sprints=[None, 4])
        sp, count, _, _, _ = compute_sprint_velocity([issue], roster, sprint_id=4)
        assert sp == 5 and count == 1

    def test_single_sprint_issue_counts(self):
        roster = _roster("a@x.com")
        issue = _issue("S-1", status="Closed", sp=8, assignee="a@x.com", sprints=[3])
        sp, count, _, _, _ = compute_sprint_velocity([issue], roster, sprint_id=3)
        assert sp == 8 and count == 1

    def test_resolution_date_fallback(self):
        roster = _roster("a@x.com")
        inside = _issue("S-1", status="Closed", sp=5, assignee="a@x.com",
                        sprints=[], resolved="2026-06-10")
        outside = _issue("S-2", status="Closed", sp=7, assignee="a@x.com",
                         sprints=[], resolved="2026-07-10")
        sp, count, skipped, _, _ = compute_sprint_velocity(
            [inside, outside], roster, sprint_id=9,
            sprint_start="2026-06-01", sprint_end="2026-06-30")
        assert sp == 5 and count == 1 and skipped == 0

    def test_skipped_when_no_sprint_data(self):
        roster = _roster("a@x.com")
        issue = _issue("S-1", status="Closed", sp=5, assignee="a@x.com",
                       sprints=[], resolved=None)
        sp, count, skipped, _, _ = compute_sprint_velocity([issue], roster, sprint_id=9)
        assert sp == 0 and count == 0 and skipped == 1


class TestFinishingSprint(unittest.TestCase):
    def test_prefers_latest_end_date_over_max_id(self):
        issue = _issue("S-1", sprints=[7, 4], sprint_details=[
            {"id": 7, "end": "2026-05-30"},
            {"id": 4, "end": "2026-06-30"},
        ])
        assert _finishing_sprint_id(issue) == 4

    def test_latest_end_date_credits_right_sprint(self):
        roster = _roster("a@x.com")
        issue = _issue("S-1", status="Closed", sp=5, assignee="a@x.com",
                       sprints=[7, 4], sprint_details=[
                           {"id": 7, "end": "2026-05-30"},
                           {"id": 4, "end": "2026-06-30"},
                       ])
        sp7, c7, _, _, _ = compute_sprint_velocity([issue], roster, sprint_id=7)
        sp4, c4, _, _, _ = compute_sprint_velocity([issue], roster, sprint_id=4)
        assert sp7 == 0 and c7 == 0
        assert sp4 == 5 and c4 == 1

    def test_falls_back_to_max_id_when_dates_missing(self):
        issue = _issue("S-1", sprints=[5, 6], sprint_details=[
            {"id": 5, "end": None},
            {"id": 6, "end": None},
        ])
        assert _finishing_sprint_id(issue) == 6

    def test_partial_dates_prefer_the_dated_sprint(self):
        issue = _issue("S-1", sprints=[3, 9], sprint_details=[
            {"id": 3, "end": "2026-06-30"},
            {"id": 9, "end": None},
        ])
        assert _finishing_sprint_id(issue) == 3

    def test_no_detail_falls_back_to_sprints_ids(self):
        issue = _issue("S-1", sprints=[2, 1], sprint_details=None)
        assert _finishing_sprint_id(issue) == 2

    def test_tie_broken_by_higher_id(self):
        issue = _issue("S-1", sprint_details=[
            {"id": 3, "end": "2026-06-30"},
            {"id": 8, "end": "2026-06-30"},
        ])
        assert _finishing_sprint_id(issue) == 8

    def test_no_sprint_history_returns_none(self):
        assert _finishing_sprint_id(_issue("S-1", sprints=[], sprint_details=None)) is None


class TestComputeVelocity(unittest.TestCase):
    def test_average_over_three_sprints(self):
        roster = _roster("a@x.com")
        data = [
            _sprint(1, "S1", [_issue("S-1", sp=10, assignee="a@x.com")]),
            _sprint(2, "S2", [_issue("S-2", sp=20, assignee="a@x.com")]),
            _sprint(3, "S3", [_issue("S-3", sp=30, assignee="a@x.com")]),
        ]
        result = compute_velocity(data, roster)
        assert result["team_velocity"] == 20.0
        assert result["sprint_count"] == 3

    def test_fewer_than_three_sprints(self):
        roster = _roster("a@x.com")
        data = [
            _sprint(1, "S1", [_issue("S-1", sp=8, assignee="a@x.com")]),
            _sprint(2, "S2", [_issue("S-2", sp=12, assignee="a@x.com")]),
        ]
        result = compute_velocity(data, roster)
        assert result["team_velocity"] == 10.0
        assert result["sprint_count"] == 2

    def test_no_sprints_yields_none(self):
        result = compute_velocity([], _roster("a@x.com"))
        assert result["team_velocity"] is None
        assert result["sprint_count"] == 0

    def test_rounds_to_one_decimal(self):
        roster = _roster("a@x.com")
        data = [
            _sprint(1, "S1", [_issue("S-1", sp=10, assignee="a@x.com")]),
            _sprint(2, "S2", [_issue("S-2", sp=11, assignee="a@x.com")]),
            _sprint(3, "S3", [_issue("S-3", sp=12, assignee="a@x.com")]),
        ]
        result = compute_velocity(data, roster)
        assert result["team_velocity"] == 11.0

    def test_per_sprint_breakdown(self):
        roster = _roster("a@x.com")
        data = [_sprint(7, "Sprint 7", [_issue("S-1", sp=5, assignee="a@x.com")])]
        result = compute_velocity(data, roster)
        assert result["sprints"][0]["sprint_id"] == 7
        assert result["sprints"][0]["name"] == "Sprint 7"
        assert result["sprints"][0]["done_team_sp"] == 5
        assert result["sprints"][0]["team_done_issues"] == 1

    def test_carryover_not_double_counted(self):
        roster = _roster("a@x.com")
        data = [
            _sprint(1, "S1", [_issue("S-1", sp=10, assignee="a@x.com", sprints=[1, 2])]),
            _sprint(2, "S2", [_issue("S-1", sp=10, assignee="a@x.com", sprints=[1, 2])]),
        ]
        result = compute_velocity(data, roster)
        s1 = next(s for s in result["sprints"] if s["sprint_id"] == 1)
        s2 = next(s for s in result["sprints"] if s["sprint_id"] == 2)
        assert s1["done_team_sp"] == 0
        assert s2["done_team_sp"] == 10

    def test_skipped_aggregated(self):
        roster = _roster("a@x.com")
        nodata = _issue("S-1", sp=5, assignee="a@x.com", sprints=[], resolved=None)
        data = [_sprint(1, "S1", [nodata])]
        result = compute_velocity(data, roster)
        assert result["skipped_no_sprint_data"] == 1
        assert result["sprints"][0]["skipped_no_sprint_data"] == 1

    def test_unmatched_aggregated(self):
        # Done work by a non-roster owner is tallied top-level and per sprint.
        roster = _roster("a@x.com")
        outsider = _issue("S-2", status="Closed", sp=4, assignee="out@x.com",
                          assignee_display="Out Sider", sprints=[1])
        data = [_sprint(1, "S1", [_issue("S-1", sp=5, assignee="a@x.com"), outsider])]
        result = compute_velocity(data, roster)
        assert result["unmatched_done_sp"] == 4
        assert result["unmatched_owners"] == ["Out Sider"]
        assert result["sprints"][0]["unmatched_done_sp"] == 4
        assert result["sprints"][0]["unmatched_owners"] == ["Out Sider"]


def _raw(key="OCPEDGE-1", status="Closed", sp=5, assignee=None, qa=None,
         sprint_id=1, sprint_end="2026-06-30"):
    """A raw MCP-shaped issue (pre-transform), to exercise the real transform path."""
    raw = {
        "key": key,
        "status": {"name": status},
        "customfield_10028": sp,
        "customfield_10020": [{"id": sprint_id, "name": f"Sprint {sprint_id}", "endDate": sprint_end}],
    }
    if assignee is not None:
        raw["assignee"] = assignee
    if qa is not None:
        raw["customfield_10470"] = qa
    return raw


class TestRawMcpRosterMatch(unittest.TestCase):
    """End-to-end from RAW MCP issues through transform-sprint-issues into velocity."""

    TODAY = "2026-07-01"

    def _roster_real(self):
        return {"members": [{"username": "alice@x.com", "display_name": "Alice Smith", "sp_target": 8}]}

    def test_email_match(self):
        raw = _raw(assignee={"displayName": "Alice Smith", "email": "alice@x.com"})
        issue = transform_issue(raw, self.TODAY)
        sp, count, _, unmatched_sp, _ = compute_sprint_velocity(
            [issue], self._roster_real(), sprint_id=1)
        assert sp == 5 and count == 1 and unmatched_sp == 0

    def test_display_name_match_when_email_null(self):
        # The common live-Jira case: email is null, only the display name is present.
        raw = _raw(assignee={"displayName": "Alice Smith", "email": None})
        issue = transform_issue(raw, self.TODAY)
        assert issue["assignee"] is None
        assert issue["assignee_display"] == "Alice Smith"
        sp, count, _, unmatched_sp, _ = compute_sprint_velocity(
            [issue], self._roster_real(), sprint_id=1)
        assert sp == 5 and count == 1 and unmatched_sp == 0

    def test_qa_contact_display_name_match(self):
        raw = _raw(assignee={"displayName": "Out Sider", "email": None},
                   qa={"displayName": "Alice Smith", "email": None})
        issue = transform_issue(raw, self.TODAY)
        sp, count, _, _, _ = compute_sprint_velocity(
            [issue], self._roster_real(), sprint_id=1)
        assert sp == 5 and count == 1

    def test_mixed_sprint(self):
        teammate = _raw("OCPEDGE-1", assignee={"displayName": "Alice Smith", "email": None}, sp=5)
        outsider = _raw("OCPEDGE-2", assignee={"displayName": "Bob Other", "email": None}, sp=9)
        issues = [transform_issue(teammate, self.TODAY), transform_issue(outsider, self.TODAY)]
        sp, count, _, unmatched_sp, unmatched_owners = compute_sprint_velocity(
            issues, self._roster_real(), sprint_id=1)
        assert sp == 5 and count == 1
        assert unmatched_sp == 9
        assert unmatched_owners == ["Bob Other"]

    def test_non_roster_owner_not_counted(self):
        raw = _raw(assignee={"displayName": "Bob Other", "email": "bob@x.com"}, sp=7)
        issue = transform_issue(raw, self.TODAY)
        sp, count, _, unmatched_sp, unmatched_owners = compute_sprint_velocity(
            [issue], self._roster_real(), sprint_id=1)
        assert sp == 0 and count == 0
        assert unmatched_sp == 7
        assert unmatched_owners == ["Bob Other"]


if __name__ == "__main__":
    unittest.main()
