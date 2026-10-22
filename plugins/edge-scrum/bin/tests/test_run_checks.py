"""Tests for run-checks.py — deterministic planning risk checks."""

import sys
import os
import io
import unittest
from contextlib import redirect_stderr

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from importlib import import_module

_mod = import_module("run-checks")
build_hierarchy = _mod.build_hierarchy
run_data_quality_gate = _mod.run_data_quality_gate
run_capacity_check = _mod.run_capacity_check
run_timeline_check = _mod.run_timeline_check
velocity_scaling_factor = _mod.velocity_scaling_factor
run_assignment_check = _mod.run_assignment_check
run_bug_load_check = _mod.run_bug_load_check
run_sizing_check = _mod.run_sizing_check
run_composite_check = _mod.run_composite_check
team_capacity = _mod.team_capacity
estimate_hidden_scope = _mod.estimate_hidden_scope
load_velocity = _mod.load_velocity
parse_availability = _mod.parse_availability
is_story_done = _mod.is_story_done


def _story(key="OCPEDGE-1", assignee="alice@example.com", sp=5, epic_key="EPIC-1",
           status="To Do", issue_type="Story", display="Alice", priority="Major"):
    return {
        "key": key, "summary": f"Story {key}", "type": issue_type, "status": status,
        "assignee": assignee, "assignee_display": display, "sp": sp, "epic_key": epic_key,
        "flagged": False, "blocked_by": [], "stale": False, "labels": [], "priority": priority,
    }


def _feature(key="OCPSTRAT-1", summary="Feature 1", size="M", epics=None, all_stories=None):
    return {
        "key": key, "summary": summary, "status": "In Progress", "size": size,
        "sme": "None", "type": "Feature",
        "epics": epics or [], "all_stories": all_stories or [],
    }


def _roster(*members):
    return {"members": [{"username": m[0], "display_name": m[1], "sp_target": m[2]} for m in members]}


class TestIsDone(unittest.TestCase):
    def test_ocpedge_closed_is_done(self):
        assert is_story_done({"key": "OCPEDGE-1", "status": "Closed"}) is True

    def test_ocpedge_done_is_not_done(self):
        assert is_story_done({"key": "OCPEDGE-1", "status": "Done"}) is False

    def test_ocpbugs_verified_is_done(self):
        assert is_story_done({"key": "OCPBUGS-1", "status": "Verified"}) is True

    def test_ocpbugs_done_is_not_done(self):
        assert is_story_done({"key": "OCPBUGS-1", "status": "Done"}) is False


class TestDataQualityGate(unittest.TestCase):
    def test_pass_with_pointed_stories(self):
        f = _feature(epics=[{"key": "E-1", "stories": [_story(sp=5)]}],
                     all_stories=[_story(sp=5)])
        result = run_data_quality_gate([f])
        assert result[0]["status"] == "PASS"

    def test_fail_no_epics(self):
        f = _feature(epics=[], all_stories=[])
        result = run_data_quality_gate([f])
        assert result[0]["status"] == "FAIL"

    def test_fail_no_stories(self):
        f = _feature(epics=[{"key": "E-1", "stories": []}], all_stories=[])
        result = run_data_quality_gate([f])
        assert result[0]["status"] == "FAIL"

    def test_warn_low_pointed(self):
        stories = [_story(f"S-{i}", sp=0) for i in range(8)] + [_story("S-9", sp=5)]
        f = _feature(epics=[{"key": "E-1", "stories": stories}], all_stories=stories)
        result = run_data_quality_gate([f])
        assert result[0]["status"] == "WARN"

    def test_bugs_count_as_issues_for_gate(self):
        # Bugs count as issues like other work (edge-context decision 0003): a feature
        # whose epics hold a pointed bug no longer FAILs for "no stories". A bug-only
        # epic is still not feature-refined, so the overlay downgrades it to WARN
        # (independent of the bug's points counting toward scope).
        stories = [_story("B-1", issue_type="Bug", sp=3)]
        f = _feature(epics=[{"key": "E-1", "stories": stories}], all_stories=stories)
        result = run_data_quality_gate([f])
        assert result[0]["status"] == "WARN"

    def test_bug_with_story_passes_gate(self):
        # With a real story in the epic, the overlay is satisfied and the pointed bug
        # counts toward the pointed ratio (edge-context decision 0003).
        stories = [_story("S-1", sp=5), _story("B-1", issue_type="Bug", sp=3)]
        f = _feature(epics=[{"key": "E-1", "stories": stories}], all_stories=stories)
        result = run_data_quality_gate([f])
        assert result[0]["status"] == "PASS"

    def test_closed_unpointed_excluded_from_pointed_pct(self):
        stories = [
            _story("S-1", sp=5, status="To Do"),
            _story("S-2", sp=0, status="Closed"),
        ]
        f = _feature(epics=[{"key": "E-1", "stories": stories}], all_stories=stories)
        result = run_data_quality_gate([f])
        assert result[0]["status"] == "PASS"
        assert result[0]["pointed_pct"] == 100


class TestCapacityCheck(unittest.TestCase):
    def test_far_above_guideline_flagged(self):
        # guideline = 8 × 2 = 16; flagged only when far above (> 1.5 × = 24).
        stories = [_story("S-1", "alice@example.com", sp=25)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_capacity_check([f], gate, roster, 2)
        assert result[0]["status"] == "ABOVE_GUIDELINE"
        assert result[0]["overrun"] == 9

    def test_slightly_over_guideline_not_flagged(self):
        # 18 SP is over the 16 guideline but not far above it (< 24): a normal
        # overrun is left OK, not treated as a capacity risk (must-fix item 3).
        stories = [_story("S-1", "alice@example.com", sp=18)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_capacity_check([f], gate, roster, 2)
        assert result[0]["status"] == "OK"

    def test_under_capacity(self):
        stories = [_story("S-1", "alice@example.com", sp=5)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_capacity_check([f], gate, roster, 2)
        assert result[0]["status"] == "OK"

    def test_excludes_fail_features(self):
        stories = [_story("S-1", "alice@example.com", sp=100)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "FAIL"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_capacity_check([f], gate, roster, 2)
        # Roster members always appear so capacity covers the whole team; the
        # FAIL feature's stories must not count.
        assert len(result) == 1
        assert result[0]["person"] == "alice@example.com"
        assert result[0]["assigned_sp"] == 0
        assert result[0]["remaining_capacity"] == 16

    def test_includes_bugs_in_sp(self):
        # Bugs load a person like other pointed work (edge-context decision 0003).
        stories = [
            _story("S-1", "alice@example.com", sp=5),
            _story("B-1", "alice@example.com", sp=3, issue_type="Bug"),
        ]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_capacity_check([f], gate, roster, 2)
        assert result[0]["assigned_sp"] == 8

    def test_non_roster_flagged(self):
        stories = [_story("S-1", "bot@x.com", sp=5)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster()
        result = run_capacity_check([f], gate, roster, 2)
        assert result[0]["in_roster"] is False


class TestTimelineCheck(unittest.TestCase):
    def test_on_track(self):
        stories = [_story("S-1", "alice@example.com", sp=8)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_timeline_check([f], gate, roster, 3)
        assert result[0]["risk"] == "OK"

    def test_behind_schedule(self):
        stories = [_story("S-1", "alice@example.com", sp=30)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_timeline_check([f], gate, roster, 1)
        assert result[0]["risk"] == "HIGH"
        assert result[0]["gap"] > 0

    def test_proportional_velocity(self):
        s1 = _story("S-1", "alice@example.com", sp=10, epic_key="E-1")
        s2 = _story("S-2", "alice@example.com", sp=10, epic_key="E-2")
        f1 = _feature("F-1", all_stories=[s1])
        f2 = _feature("F-2", all_stories=[s2])
        gate = [{"feature_key": "F-1", "status": "PASS"}, {"feature_key": "F-2", "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_timeline_check([f1, f2], gate, roster, 3)
        assert result[0]["velocity_per_sprint"] == 4.0
        assert result[1]["velocity_per_sprint"] == 4.0

    def test_no_contributors(self):
        stories = [_story("S-1", assignee=None, sp=10)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        result = run_timeline_check([f], gate, _roster(), 3)
        assert result[0]["risk"] == "NO_CONTRIBUTORS"

    def test_zero_remaining_sprints(self):
        stories = [_story("S-1", "alice@example.com", sp=10)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_timeline_check([f], gate, roster, 0)
        assert result[0]["risk"] == "HIGH"

    def test_effective_sprints_flips_risk_to_high(self):
        # A feature needing ~2 sprints is OK against 3 raw sprints, but HIGH once
        # availability cuts the effective sprints to 1.3 — matching the capacity cut-line.
        stories = [_story("S-1", "alice@example.com", sp=16)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        ok = run_timeline_check([f], gate, roster, 3)
        # 16 SP ÷ 8/sprint = 2 sprints needed; 3 raw sprints left → OK.
        assert ok[0]["risk"] == "OK"
        high = run_timeline_check([f], gate, roster, 3, effective_sprints=1.3)
        # Same 2 sprints needed, but only 1.3 effective sprints available → HIGH.
        assert high[0]["risk"] == "HIGH"
        assert high[0]["sprints_left"] == 1.3

    def test_effective_sprints_defaults_to_remaining(self):
        # Omitting effective_sprints reports the raw remaining sprints unchanged.
        stories = [_story("S-1", "alice@example.com", sp=8)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        result = run_timeline_check([f], gate, roster, 3)
        assert result[0]["sprints_left"] == 3

    def test_velocity_factor_scales_throughput(self):
        # One sole contributor on a feature: velocity == sp_target × velocity_factor.
        stories = [_story("S-1", "alice@example.com", sp=8)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        roster = _roster(("alice@example.com", "Alice", 8))
        full = run_timeline_check([f], gate, roster, 3)
        half = run_timeline_check([f], gate, roster, 3, velocity_factor=0.5)
        # Full pace: 8 SP ÷ (8 × 1.0) = 1 sprint. Half pace halves velocity, doubles sprints.
        assert full[0]["velocity_per_sprint"] == 8.0
        assert full[0]["sprints_needed"] == 1.0
        assert half[0]["velocity_per_sprint"] == 4.0
        assert half[0]["sprints_needed"] == 2.0

    def test_roster_member_without_sp_target_defaults_to_guideline(self):
        # A roster member missing the sp_target field must fall back to the single
        # DEFAULT_SP_TARGET guideline (decision 0015), not zero. Otherwise dropping
        # sp_target from every member — to lean on the single soft guideline —
        # would zero each member's throughput and flag every feature NO_CONTRIBUTORS.
        roster = {"members": [{"username": "alice@example.com", "display_name": "Alice"}]}
        stories = [_story("S-1", "alice@example.com", sp=8)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        result = run_timeline_check([f], gate, roster, 1)
        assert result[0]["risk"] != "NO_CONTRIBUTORS"
        assert result[0]["velocity_per_sprint"] == 8.0
        assert result[0]["risk"] == "OK"

    def test_non_roster_contributor_still_zero_velocity(self):
        # The fix must not credit non-roster people: with a roster present, an
        # assignee who is not a member still contributes zero (→ NO_CONTRIBUTORS).
        roster = {"members": [{"username": "alice@example.com", "display_name": "Alice"}]}
        stories = [_story("S-1", "stranger@example.com", sp=8)]
        f = _feature(all_stories=stories)
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        result = run_timeline_check([f], gate, roster, 1)
        assert result[0]["risk"] == "NO_CONTRIBUTORS"


class TestVelocityScalingFactor(unittest.TestCase):
    def test_none_velocity_is_identity(self):
        roster = _roster(("alice@example.com", "Alice", 8), ("bob@x.com", "Bob", 8))
        assert velocity_scaling_factor(None, roster) == 1.0

    def test_scales_to_measured_velocity(self):
        # Σ sp_target = 16; velocity 8 → factor 0.5.
        roster = _roster(("alice@example.com", "Alice", 8), ("bob@x.com", "Bob", 8))
        assert velocity_scaling_factor(8, roster) == 0.5

    def test_empty_roster_is_identity(self):
        assert velocity_scaling_factor(20, _roster()) == 1.0


class TestAssignmentCheck(unittest.TestCase):
    def test_spof_detected(self):
        stories = [_story("S-1", "alice@example.com"), _story("S-2", "alice@example.com")]
        f = _feature(all_stories=stories)
        result = run_assignment_check([f])
        assert len(result["spof"]) == 1

    def test_no_spof_with_multiple_contributors(self):
        stories = [_story("S-1", "alice@example.com"), _story("S-2", "bob@x.com")]
        f = _feature(all_stories=stories)
        result = run_assignment_check([f])
        assert len(result["spof"]) == 0

    def test_unassigned_detected(self):
        stories = [_story("S-1", assignee=None, sp=5)]
        f = _feature(all_stories=stories)
        result = run_assignment_check([f])
        assert len(result["unassigned"]) == 1
        assert result["unassigned"][0]["count"] == 1

    def test_bugs_counted_for_spof(self):
        # Bugs count as contributions like other work (edge-context decision 0003):
        # a bug owned by a second person means the feature is no longer single-owner.
        stories = [
            _story("S-1", "alice@example.com", sp=5),
            _story("B-1", "bot@x.com", sp=3, issue_type="Bug"),
        ]
        f = _feature(all_stories=stories)
        result = run_assignment_check([f])
        assert len(result["spof"]) == 0

    def test_bugs_counted_for_unassigned(self):
        # Unassigned bugs are unassigned work like any other (edge-context decision 0003).
        stories = [_story("B-1", assignee=None, sp=3, issue_type="Bug")]
        f = _feature(all_stories=stories)
        result = run_assignment_check([f])
        assert len(result["unassigned"]) == 1


class TestCompositeCheck(unittest.TestCase):
    def _run(self, features, gate_status="PASS", timeline_risk="OK", capacity_over=False,
             has_spof=False, has_unassigned=False, has_sizing=False, count_sizing=False):
        gate = [{"feature_key": f["key"], "status": gate_status} for f in features]
        capacity = [{"person": "alice@example.com", "status": "ABOVE_GUIDELINE"}] if capacity_over else []
        timeline = [{"feature_key": f["key"], "risk": timeline_risk} for f in features]
        spof = [{"feature_key": feat["key"], "sole_contributor": "alice"} for feat in features] if has_spof else []
        unassigned_list = [{"feature_key": feat["key"], "count": 1, "sp": 5} for feat in features] if has_unassigned else []
        assignment = {"spof": spof, "unassigned": unassigned_list}
        sizing = [{"feature_key": feat["key"], "assessment": "Undersized"} for feat in features] if has_sizing else []
        return run_composite_check(features, gate, capacity, timeline, assignment, sizing,
                                   count_sizing=count_sizing)

    def test_low_no_signals(self):
        f = _feature(all_stories=[_story()])
        result = self._run([f])
        assert result[0]["composite_risk"] == "LOW"

    def test_medium_two_signals(self):
        # Two counted signals = MEDIUM (capacity is not among the counted signals).
        f = _feature(all_stories=[_story()])
        result = self._run([f], timeline_risk="HIGH", has_spof=True)
        assert result[0]["composite_risk"] == "MEDIUM"

    def test_high_three_signals(self):
        # timeline + assignment + data-quality FAIL = 3 counted signals = HIGH.
        f = _feature(all_stories=[_story()])
        result = self._run([f], gate_status="FAIL", timeline_risk="HIGH", has_spof=True)
        assert result[0]["composite_risk"] == "HIGH"

    def test_capacity_not_counted_but_shown(self):
        # A contributor above the guideline is shown on the row but adds no signal:
        # one spof signal alone stays LOW even with capacity flagged (must-fix item 3).
        f = _feature(all_stories=[_story()])
        result = self._run([f], has_spof=True, capacity_over=True)
        assert result[0]["capacity"] == "ABOVE_GUIDELINE"
        assert result[0]["signal_count"] == 1
        assert result[0]["composite_risk"] == "LOW"

    def test_sizing_shown_but_not_counted_by_default(self):
        f = _feature(all_stories=[_story()])
        result = self._run([f], has_spof=True, has_sizing=True)
        assert result[0]["sizing"] == "Undersized"
        assert result[0]["signal_count"] == 1
        assert result[0]["composite_risk"] == "LOW"

    def test_sizing_counted_when_opted_in(self):
        f = _feature(all_stories=[_story()])
        result = self._run([f], has_spof=True, has_sizing=True, count_sizing=True)
        assert result[0]["signal_count"] == 2

    def test_spof_and_unassigned_merged_as_one_signal(self):
        f = _feature(all_stories=[_story()])
        result = self._run([f], has_spof=True, has_unassigned=True)
        assert result[0]["signal_count"] == 1
        assert result[0]["composite_risk"] == "LOW"

    def test_data_quality_fail_counts_as_signal(self):
        f = _feature(all_stories=[_story()])
        result = self._run([f], gate_status="FAIL", has_spof=True)
        assert result[0]["signal_count"] == 2
        assert result[0]["composite_risk"] == "MEDIUM"

    def test_bug_assignee_capacity_shown_not_counted(self):
        # edge-context decision 0003: bugs are team work, so a bug assignee who is
        # above the guideline shows on the feature's capacity cell — but per must-fix
        # item 3 that is informational and adds no composite signal. A legacy "OVER"
        # status is still read (readers accept both OVER and ABOVE_GUIDELINE).
        bug = _story("B-1", assignee="alice@example.com", sp=3, issue_type="Bug")
        f = _feature(all_stories=[bug])
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        capacity = [{"person": "alice@example.com", "status": "OVER"}]
        timeline = [{"feature_key": f["key"], "risk": "OK"}]
        assignment = {"spof": [], "unassigned": []}
        result = run_composite_check([f], gate, capacity, timeline, assignment, [])
        assert result[0]["capacity"] == "ABOVE_GUIDELINE"
        assert result[0]["signal_count"] == 0
        assert result[0]["composite_risk"] == "LOW"

    def test_sorted_high_first(self):
        # F-2 carries three counted signals (data-quality + timeline + assignment);
        # capacity and sizing are shown but not counted, so they don't alter the sort.
        f1 = _feature("F-1", all_stories=[_story("S-1")])
        f2 = _feature("F-2", all_stories=[_story("S-2")])
        gate = [{"feature_key": "F-1", "status": "PASS"}, {"feature_key": "F-2", "status": "FAIL"}]
        timeline = [{"feature_key": "F-1", "risk": "OK"}, {"feature_key": "F-2", "risk": "HIGH"}]
        assignment = {"spof": [{"feature_key": "F-2", "sole_contributor": "a"}],
                      "unassigned": [{"feature_key": "F-2", "count": 1, "sp": 0}]}
        capacity = [{"person": "alice@example.com", "status": "OVER"}]
        sizing = [{"feature_key": "F-2", "assessment": "Undersized"}]
        result = run_composite_check([f1, f2], gate, capacity, timeline, assignment, sizing)
        assert result[0]["feature_key"] == "F-2"
        assert result[0]["composite_risk"] == "HIGH"


class TestBuildHierarchy(unittest.TestCase):
    def test_basic_hierarchy(self):
        features_data = {"features": [{"key": "F-1", "summary": "Feature 1", "status": "In Progress",
                                        "size": "M", "sme": "None", "type": "Feature"}]}
        epics_data = {"epics": [{"key": "E-1", "labels": []}], "feature_to_epics": {"F-1": ["E-1"]}}
        stories_data = {"stories": [_story("S-1", epic_key="E-1")]}
        bugs_data = {"bugs": []}
        result, _bugs = build_hierarchy(features_data, epics_data, stories_data, bugs_data, "none")
        assert len(result) == 1
        assert len(result[0]["epics"]) == 1
        assert len(result[0]["all_stories"]) == 1

    def test_component_filter_by_label(self):
        features_data = {"features": [
            {"key": "F-1", "summary": "F1", "status": "IP", "size": "M", "sme": "N", "type": "Feature"},
            {"key": "F-2", "summary": "F2", "status": "IP", "size": "M", "sme": "N", "type": "Feature"},
        ]}
        epics_data = {"epics": [
            {"key": "E-1", "labels": ["tna"]},
            {"key": "E-2", "labels": ["lvms"]},
        ], "feature_to_epics": {"F-1": ["E-1"], "F-2": ["E-2"]}}
        stories_data = {"stories": [_story("S-1", epic_key="E-1"), _story("S-2", epic_key="E-2")]}
        bugs_data = {"bugs": []}
        result, _ = build_hierarchy(features_data, epics_data, stories_data, bugs_data, "tna")
        assert len(result) == 1
        assert result[0]["key"] == "F-1"

    def test_no_filter(self):
        features_data = {"features": [{"key": "F-1", "summary": "F1", "status": "IP", "size": "M", "sme": "N", "type": "Feature"}]}
        epics_data = {"epics": [], "feature_to_epics": {}}
        stories_data = {"stories": []}
        bugs_data = {"bugs": []}
        result, _ = build_hierarchy(features_data, epics_data, stories_data, bugs_data, "none")
        assert len(result) == 1

    def _make_data(self, story_key="OCPEDGE-1", epic_labels=None, story_component=""):
        s = _story(story_key, epic_key="E-1")
        s["component"] = story_component
        features_data = {"features": [{"key": "F-1", "summary": "F1", "status": "IP", "size": "M", "sme": "N", "type": "Feature"}]}
        epics_data = {"epics": [{"key": "E-1", "labels": epic_labels or []}], "feature_to_epics": {"F-1": ["E-1"]}}
        stories_data = {"stories": [s]}
        bugs_data = {"bugs": []}
        return features_data, epics_data, stories_data, bugs_data

    def test_microshift_filter_matches_microshift_component(self):
        fd, ed, sd, bd = self._make_data(story_component="MicroShift")
        result, _ = build_hierarchy(fd, ed, sd, bd, "microshift")
        assert len(result) == 1

    def test_microshift_filter_matches_subcomponent(self):
        fd, ed, sd, bd = self._make_data(story_component="MicroShift / Networking")
        result, _ = build_hierarchy(fd, ed, sd, bd, "microshift")
        assert len(result) == 1

    def test_microshift_filter_matches_future_subcomponent(self):
        fd, ed, sd, bd = self._make_data(story_component="MicroShift / etcd")
        result, _ = build_hierarchy(fd, ed, sd, bd, "microshift")
        assert len(result) == 1

    def test_microshift_filter_matches_ushift_key(self):
        fd, ed, sd, bd = self._make_data(story_key="USHIFT-100")
        result, _ = build_hierarchy(fd, ed, sd, bd, "microshift")
        assert len(result) == 1

    def test_sno_filter_does_not_match_ushift(self):
        fd, ed, sd, bd = self._make_data(story_key="USHIFT-100")
        result, _ = build_hierarchy(fd, ed, sd, bd, "sno")
        assert len(result) == 0

    def test_sno_filter_matches_sno_component(self):
        fd, ed, sd, bd = self._make_data(story_component="Installer / Single Node OpenShift")
        result, _ = build_hierarchy(fd, ed, sd, bd, "sno")
        assert len(result) == 1

    def test_tna_filter_does_not_match_microshift(self):
        fd, ed, sd, bd = self._make_data(story_component="MicroShift")
        result, _ = build_hierarchy(fd, ed, sd, bd, "tna")
        assert len(result) == 0

    def test_tna_filter_matches_label(self):
        fd, ed, sd, bd = self._make_data(epic_labels=["tna"])
        result, _ = build_hierarchy(fd, ed, sd, bd, "tna")
        assert len(result) == 1


class TestBugLoadFilter(unittest.TestCase):
    def _bug(self, key="OCPBUGS-1", component="MicroShift"):
        return {"key": key, "summary": f"Bug {key}", "type": "Bug", "status": "NEW",
                "priority": "Blocker", "assignee": None, "component": component}

    def test_microshift_filter_matches_all_subcomponents(self):
        bugs = [self._bug("B-1", "MicroShift"), self._bug("B-2", "MicroShift / Networking"),
                self._bug("B-3", "Two Node Fencing")]
        result = run_bug_load_check(bugs, [], "microshift")
        assert len(result["unassigned_blocker_critical"]) == 2

    def test_microshift_filter_matches_future_subcomponent(self):
        bugs = [self._bug("B-1", "MicroShift / etcd")]
        result = run_bug_load_check(bugs, [], "microshift")
        assert len(result["unassigned_blocker_critical"]) == 1

    def test_sno_filter_excludes_microshift(self):
        bugs = [self._bug("B-1", "MicroShift"), self._bug("B-2", "Installer / Single Node OpenShift")]
        result = run_bug_load_check(bugs, [], "sno")
        assert len(result["unassigned_blocker_critical"]) == 1
        assert result["unassigned_blocker_critical"][0]["key"] == "B-2"

    def test_tna_filter(self):
        bugs = [self._bug("B-1", "Two Node with Arbiter"), self._bug("B-2", "MicroShift")]
        result = run_bug_load_check(bugs, [], "tna")
        assert len(result["unassigned_blocker_critical"]) == 1
        assert result["unassigned_blocker_critical"][0]["key"] == "B-1"


class TestBugLoadCheck(unittest.TestCase):
    def _bug(self, key="OCPBUGS-1", priority="Blocker", assignee=None, component="Two Node Fencing"):
        return {"key": key, "summary": f"Bug {key}", "type": "Bug", "status": "NEW",
                "priority": priority, "assignee": assignee, "component": component}

    def test_unassigned_blocker_detected(self):
        result = run_bug_load_check([self._bug()], [], "none")
        assert len(result["unassigned_blocker_critical"]) == 1

    def test_assigned_blocker_not_flagged(self):
        result = run_bug_load_check([self._bug(assignee="alice@example.com")], [], "none")
        assert len(result["unassigned_blocker_critical"]) == 0

    def test_major_not_flagged(self):
        result = run_bug_load_check([self._bug(priority="Major")], [], "none")
        assert len(result["unassigned_blocker_critical"]) == 0

    def test_component_filter(self):
        bugs = [self._bug("B-1", component="Two Node Fencing"), self._bug("B-2", component="Two Node with Arbiter")]
        result = run_bug_load_check(bugs, [], "tnf")
        assert len(result["unassigned_blocker_critical"]) == 1

    def test_epic_bugs_included(self):
        epic_story_bug = _story("OCPBUGS-99", assignee=None, sp=0, issue_type="Bug", priority="Critical")
        epic_story_bug["component"] = "Two Node Fencing"
        result = run_bug_load_check([], [epic_story_bug], "none")
        assert len(result["unassigned_blocker_critical"]) == 1


class TestSizingCheck(unittest.TestCase):
    def test_unsized_flagged(self):
        f = _feature(size="Unsized", all_stories=[_story(sp=5)])
        result = run_sizing_check([f], [{"feature_key": f["key"], "sprints_needed": 1, "risk": "OK"}])
        assert result[0]["assessment"] == "Unsized"

    def test_correctly_sized_not_flagged(self):
        f = _feature(size="M", all_stories=[_story(sp=5)], epics=[{"key": "E-1"}])
        result = run_sizing_check([f], [{"feature_key": f["key"], "sprints_needed": 2, "risk": "OK"}])
        assert len(result) == 0

    def test_undersized_by_sprints(self):
        f = _feature(size="XS", all_stories=[_story(sp=30)], epics=[{"key": "E-1"}])
        result = run_sizing_check([f], [{"feature_key": f["key"], "sprints_needed": 5, "risk": "HIGH"}])
        assert result[0]["assessment"] == "Undersized"


class TestCompositeCheckBugSignal(unittest.TestCase):
    def test_bug_signal_fires_for_epic_linked_bugs(self):
        bug_story = _story("OCPBUGS-1", assignee=None, sp=0, issue_type="Bug", priority="Blocker")
        f = _feature(all_stories=[_story("S-1"), bug_story])
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        result = run_composite_check(
            [f], gate, [], [{"feature_key": f["key"], "risk": "OK"}],
            {"spof": [], "unassigned": []}, []
        )
        assert result[0]["bugs"] == "HIGH"
        assert result[0]["signal_count"] == 1

    def test_no_bug_signal_when_bugs_assigned(self):
        bug_story = _story("OCPBUGS-1", assignee="alice@example.com", sp=0, issue_type="Bug", priority="Blocker")
        f = _feature(all_stories=[_story("S-1"), bug_story])
        gate = [{"feature_key": f["key"], "status": "PASS"}]
        result = run_composite_check(
            [f], gate, [], [{"feature_key": f["key"], "risk": "OK"}],
            {"spof": [], "unassigned": []}, []
        )
        assert result[0]["bugs"] == "OK"


class TestTeamCapacity(unittest.TestCase):
    def test_velocity_basis_preferred(self):
        # Capacity is planned against measured velocity (edge-context decision 0015).
        roster = _roster(("alice@example.com", "Alice", 8), ("bob@example.com", "Bob", 8))
        cap, basis = team_capacity(20.0, roster, 3)
        assert basis == "velocity"
        assert cap == 60

    def test_velocity_rounds_to_nearest_sp(self):
        roster = _roster(("alice@example.com", "Alice", 8))
        cap, basis = team_capacity(12.5, roster, 2)
        assert basis == "velocity"
        assert cap == 25

    def test_roster_fallback_when_no_velocity(self):
        # No velocity available → Σ sp_target × sprints left, flagged as fallback.
        roster = _roster(("alice@example.com", "Alice", 8), ("bob@example.com", "Bob", 5))
        cap, basis = team_capacity(None, roster, 2)
        assert basis == "roster_fallback"
        assert cap == 26

    def test_roster_fallback_uses_default_target(self):
        roster = {"members": [{"username": "alice@example.com", "display_name": "Alice"}]}
        cap, basis = team_capacity(None, roster, 1)
        assert basis == "roster_fallback"
        assert cap == _mod.DEFAULT_SP_TARGET

    def test_availability_reduces_velocity_capacity(self):
        # law 09: velocity adjusted for PTO. Two sprints at 80% and 50% → 1.3 effective.
        roster = _roster(("alice@example.com", "Alice", 8))
        cap, basis = team_capacity(20.0, roster, 2, availability=[0.8, 0.5])
        assert basis == "velocity"
        assert cap == 26  # round(20 * 1.3)

    def test_full_availability_matches_unadjusted(self):
        roster = _roster(("alice@example.com", "Alice", 8))
        assert team_capacity(20.0, roster, 3, availability=[1.0, 1.0, 1.0])[0] == 60
        assert team_capacity(20.0, roster, 3)[0] == 60

    def test_availability_applies_to_roster_fallback(self):
        roster = _roster(("alice@example.com", "Alice", 8), ("bob@example.com", "Bob", 5))
        cap, basis = team_capacity(None, roster, 2, availability=[1.0, 0.5])
        assert basis == "roster_fallback"
        assert cap == 20  # round(13 * 1.5)


class TestParseAvailability(unittest.TestCase):
    def test_none_yields_full_availability(self):
        assert parse_availability(None, 3) == [1.0, 1.0, 1.0]

    def test_clamps_to_unit_interval(self):
        assert parse_availability("1.5,-0.2", 2) == [1.0, 0.0]

    def test_pads_short_list_with_full(self):
        assert parse_availability("0.5", 3) == [0.5, 1.0, 1.0]

    def test_truncates_long_list(self):
        assert parse_availability("0.5,0.6,0.7", 2) == [0.5, 0.6]

    def test_invalid_token_not_echoed_to_log(self):
        # --availability is caller-controlled; a bad token must be skipped
        # without echoing its raw value (it could carry sensitive data).
        secret = "user@example.com:hunter2"
        buf = io.StringIO()
        with redirect_stderr(buf):
            result = parse_availability(f"0.5,{secret}", 2)
        log = buf.getvalue()
        assert result == [0.5, 1.0]  # bad token treated as 1.0 in place
        assert secret not in log
        assert "position 2" in log

    def test_empty_token_kept_in_place_as_full(self):
        # An empty value must become 1.0 *in place*, not be dropped — dropping would
        # shift later sprints' availability onto the wrong sprint (should-fix item 7).
        buf = io.StringIO()
        with redirect_stderr(buf):
            result = parse_availability("0.5,,0.2", 3)
        assert result == [0.5, 1.0, 0.2]
        assert "position 2" in buf.getvalue()

    def test_non_numeric_token_kept_in_place_as_full(self):
        buf = io.StringIO()
        with redirect_stderr(buf):
            result = parse_availability("0.5,oops,0.2", 3)
        assert result == [0.5, 1.0, 0.2]


class TestHiddenScope(unittest.TestCase):
    def _active(self, stories):
        f = _feature(all_stories=stories)
        return [f], {f["key"]}

    def test_bugs_excluded_from_estimate(self):
        # Unpointed open bugs must not inflate the hidden-scope estimate.
        stories = [
            _story("S-1", sp=0, status="To Do"),
            _story("B-1", sp=0, status="To Do", issue_type="Bug"),
            _story("B-2", sp=0, status="To Do", issue_type="Bug"),
        ]
        features, active_keys = self._active(stories)
        hidden = estimate_hidden_scope(features, active_keys)
        assert hidden["unpointed_open"] == 1  # only the story
        assert hidden["unpointed_bugs"] == 2
        assert set(hidden["unpointed_bug_keys"]) == {"B-1", "B-2"}

    def test_no_bugs_leaves_estimate_unchanged(self):
        stories = [_story("S-1", sp=0, status="To Do"), _story("S-2", sp=0, status="To Do")]
        features, active_keys = self._active(stories)
        hidden = estimate_hidden_scope(features, active_keys)
        assert hidden["unpointed_open"] == 2
        assert hidden["unpointed_bugs"] == 0
        assert hidden["unpointed_bug_keys"] == []


class TestLoadVelocity(unittest.TestCase):
    def test_missing_path_returns_fallback(self):
        vel, sprints = load_velocity("/nonexistent/velocity.json")
        assert vel is None
        assert sprints == []

    def test_none_path_returns_fallback(self):
        assert load_velocity(None) == (None, [])

    def test_loads_existing_file(self):
        import json
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"team_velocity": 18.0, "sprints": [{"sprint_id": 1}]}, fh)
            path = fh.name
        try:
            vel, sprints = load_velocity(path)
            assert vel == 18.0
            assert sprints == [{"sprint_id": 1}]
        finally:
            os.unlink(path)

    def test_string_velocity_coerced_to_float(self):
        # velocity.json normally carries a number, but a stringified value must be
        # coerced rather than crash the planning run (should-fix item 7).
        import json
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"team_velocity": "12.5", "sprints": []}, fh)
            path = fh.name
        try:
            vel, _ = load_velocity(path)
            assert vel == 12.5
        finally:
            os.unlink(path)

    def test_non_numeric_velocity_ignored_with_warning(self):
        import json
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"team_velocity": "n/a", "sprints": [{"sprint_id": 3}]}, fh)
            path = fh.name
        try:
            buf = io.StringIO()
            with redirect_stderr(buf):
                vel, sprints = load_velocity(path)
            assert vel is None
            assert sprints == [{"sprint_id": 3}]
            assert "not numeric" in buf.getvalue()
        finally:
            os.unlink(path)

    def test_zero_velocity_coerced_to_fallback(self):
        # A measured 0 (nothing matched the roster, e.g. live null-email assignees)
        # is no usable signal: coerce to None so capacity uses the roster fallback,
        # not a degenerate 0-SP capacity that flags everything at risk.
        import json
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"team_velocity": 0.0, "sprints": [{"sprint_id": 5}]}, fh)
            path = fh.name
        try:
            vel, sprints = load_velocity(path)
            assert vel is None  # falls back to roster
            assert sprints == [{"sprint_id": 5}]
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
