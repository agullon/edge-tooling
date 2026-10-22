"""Tests for transform-spikes helpers."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from importlib import import_module

_mod = import_module("transform-spikes")
epics_look_refined = _mod.epics_look_refined
EPIC_PLANNING_STATE = _mod.EPIC_PLANNING_STATE
build_spike_map = _mod.build_spike_map
is_test_plan_spike = _mod.is_test_plan_spike
is_unassigned_qa = _mod.is_unassigned_qa


def ref_spike(key, summary, status="To Do", assignee="", resolution=None, blocks=None):
    """Build a normalized refinement-sprint spike that blocks the given keys."""
    links = []
    for target in blocks or []:
        links.append({"type": {"outward": "blocks"}, "outward_issue": {"key": target}})
    return {
        "key": key,
        "summary": summary,
        "status": status,
        "assignee": assignee,
        "resolution": resolution,
        "issuelinks": links,
    }


def feature(key, qa_contact="Alice", status="Refinement", spike_candidates=None):
    return {
        "key": key,
        "status": status,
        "qa_contact": qa_contact,
        "spike_candidates": spike_candidates or [],
    }


def run(features, ref_spikes, ref_sprint_closed=False, linked_spikes=None):
    feature_keys = [f["key"] for f in features]
    return build_spike_map(features, feature_keys, {}, {}, ref_spikes, ref_sprint_closed,
                           linked_spikes=linked_spikes)


class TestEpicsLookRefined(unittest.TestCase):
    def test_empty_list_returns_false(self):
        assert epics_look_refined([]) is False

    def test_all_past_planning_returns_true(self):
        epics = [
            {"status": "In Progress"},
            {"status": "Closed"},
            {"status": "To Do"},
        ]
        assert epics_look_refined(epics) is True

    def test_missing_status_returns_false(self):
        epics = [{"status": "In Progress"}, {}]
        assert epics_look_refined(epics) is False

    def test_empty_status_returns_false(self):
        epics = [{"status": "In Progress"}, {"status": ""}]
        assert epics_look_refined(epics) is False

    def test_any_epic_in_planning_returns_false(self):
        epics = [
            {"status": "In Progress"},
            {"status": EPIC_PLANNING_STATE},
            {"status": "Closed"},
        ]
        assert epics_look_refined(epics) is False

    def test_feature_pre_refined_states_do_not_affect_result(self):
        """Features in New/Refinement status are irrelevant to epics_look_refined;
        only epic records matter."""
        epics = [{"status": "In Progress"}, {"status": "Closed"}]
        assert epics_look_refined(epics) is True

        epics_with_feature_like_status = [
            {"status": "New"},
            {"status": "Refinement"},
        ]
        assert epics_look_refined(epics_with_feature_like_status) is True


class TestBuildSpikeMap(unittest.TestCase):
    FK = "OCPSTRAT-1"

    def test_both_spikes(self):
        spikes = [
            ref_spike("OCPEDGE-10", "Refinement spike", blocks=[self.FK]),
            ref_spike("OCPEDGE-11", "Test plan spike", blocks=[self.FK]),
        ]
        m = run([feature(self.FK)], spikes)[self.FK]
        assert m["spike_key"] == "OCPEDGE-10"
        assert m["spike_missing"] is False
        assert m["test_plan_spike_key"] == "OCPEDGE-11"
        assert m["test_plan_spike_missing"] is False
        assert m["test_plan_check_skipped"] is False

    def test_only_refinement_spike(self):
        spikes = [ref_spike("OCPEDGE-10", "Refinement spike", blocks=[self.FK])]
        m = run([feature(self.FK)], spikes)[self.FK]
        assert m["spike_key"] == "OCPEDGE-10"
        assert m["spike_missing"] is False
        assert m["test_plan_spike_key"] is None
        assert m["test_plan_spike_missing"] is True

    def test_only_test_plan_spike_reports_refinement_missing(self):
        """A test plan spike can no longer satisfy the refinement spike."""
        spikes = [ref_spike("OCPEDGE-11", "Test plan spike", blocks=[self.FK])]
        m = run([feature(self.FK)], spikes)[self.FK]
        assert m["spike_key"] is None
        assert m["spike_missing"] is True
        assert m["spike_status"] == "Missing"
        assert m["test_plan_spike_key"] == "OCPEDGE-11"
        assert m["test_plan_spike_missing"] is False

    def test_test_plan_identified_by_assignee(self):
        """Assignee == QA Contact marks a test plan spike even without the phrase."""
        spikes = [
            ref_spike("OCPEDGE-12", "Investigate perf approach",
                      assignee="alice", blocks=[self.FK]),
        ]
        m = run([feature(self.FK, qa_contact="Alice")], spikes)[self.FK]
        assert m["test_plan_spike_key"] == "OCPEDGE-12"
        assert m["test_plan_spike_missing"] is False
        assert m["spike_missing"] is True

    def test_unassigned_qa_skips_check(self):
        """QA Contact unassigned_jira skips the test plan check; an assignee match
        can no longer apply, so a non-phrase spike stays a refinement spike."""
        spikes = [
            ref_spike("OCPEDGE-13", "Investigate perf approach",
                      assignee="Bob", blocks=[self.FK]),
        ]
        m = run([feature(self.FK, qa_contact="unassigned_jira")], spikes)[self.FK]
        assert m["test_plan_check_skipped"] is True
        assert m["test_plan_spike_key"] is None
        assert m["test_plan_spike_missing"] is True
        assert m["spike_key"] == "OCPEDGE-13"

    def test_test_plan_closed_wont_do_no_flag_resolution_shown(self):
        """A Closed test plan spike satisfies the check whatever its resolution,
        and the resolution is surfaced so deliberate skips are visible."""
        spikes = [
            ref_spike("OCPEDGE-10", "Refinement spike", status="Closed", blocks=[self.FK]),
            ref_spike("OCPEDGE-11", "Test plan spike", status="Closed",
                      resolution="Won't Do", blocks=[self.FK]),
        ]
        m = run([feature(self.FK)], spikes, ref_sprint_closed=True)[self.FK]
        assert m["test_plan_spike_status"] == "Closed"
        assert m["test_plan_spike_resolution"] == "Won't Do"
        assert m["test_plan_spike_missing"] is False
        assert m["test_plan_spike_overdue"] is False

    def test_test_plan_overdue_when_ref_sprint_closed(self):
        spikes = [
            ref_spike("OCPEDGE-10", "Refinement spike", status="Closed", blocks=[self.FK]),
            ref_spike("OCPEDGE-11", "Test plan spike", status="In Progress", blocks=[self.FK]),
        ]
        m = run([feature(self.FK)], spikes, ref_sprint_closed=True)[self.FK]
        assert m["test_plan_spike_overdue"] is True

    def test_candidate_summary_classifies_test_plan(self):
        """spike_candidates carrying summary/assignee are classified too."""
        feat = feature(
            self.FK,
            spike_candidates=[{"key": "OCPEDGE-20", "summary": "Test plan spike",
                               "assignee": "", "status": "To Do", "issuelinks": []}],
        )
        m = run([feat], [])[self.FK]
        assert m["test_plan_spike_key"] == "OCPEDGE-20"
        assert m["spike_missing"] is True

    def test_closed_test_plan_preferred_over_open_not_overdue(self):
        """When one test plan spike is Closed and another still open, the Closed one
        represents the check (Closed-first selection) so the feature is not overdue —
        regardless of which key comes first numerically."""
        spikes = [
            ref_spike("OCPEDGE-30", "Test plan spike", status="New", blocks=[self.FK]),
            ref_spike("OCPEDGE-31", "Test plan spike", status="Closed", blocks=[self.FK]),
        ]
        m = run([feature(self.FK)], spikes, ref_sprint_closed=True)[self.FK]
        assert m["test_plan_spike_key"] == "OCPEDGE-31"
        assert m["test_plan_spike_status"] == "Closed"
        assert m["test_plan_spike_overdue"] is False

    def test_primary_uses_numeric_key_order(self):
        """Same-status spikes are ordered numerically: OCPEDGE-9 before OCPEDGE-10
        (a plain string sort would wrongly pick OCPEDGE-10)."""
        spikes = [
            ref_spike("OCPEDGE-10", "Refinement spike", status="To Do", blocks=[self.FK]),
            ref_spike("OCPEDGE-9", "Refinement spike", status="To Do", blocks=[self.FK]),
        ]
        m = run([feature(self.FK)], spikes)[self.FK]
        assert m["spike_key"] == "OCPEDGE-9"

    def test_linked_spike_fills_resolution(self):
        """A spike reachable only via the feature's issuelinks (empty candidate
        payload) gets status/resolution from the --linked-spikes fetch."""
        feat = feature(
            self.FK,
            spike_candidates=[{"key": "OCPEDGE-40", "summary": "Test plan spike",
                               "assignee": "", "status": "", "issuelinks": []}],
        )
        linked = [ref_spike("OCPEDGE-40", "Test plan spike", status="Closed",
                            resolution="Won't Do")]
        m = run([feat], [], linked_spikes=linked)[self.FK]
        assert m["test_plan_spike_key"] == "OCPEDGE-40"
        assert m["test_plan_spike_status"] == "Closed"
        assert m["test_plan_spike_resolution"] == "Won't Do"

    def test_linked_spike_assignee_reclassifies(self):
        """The linked fetch supplies the assignee the candidate lacked, so a spike
        assigned to the QE Lead is reclassified as a test plan spike."""
        feat = feature(
            self.FK, qa_contact="Alice",
            spike_candidates=[{"key": "OCPEDGE-41", "summary": "Investigate perf",
                               "assignee": "", "status": "", "issuelinks": []}],
        )
        # Without the linked fetch there is no assignee, so it's a refinement spike.
        without = run([feat], [])[self.FK]
        assert without["test_plan_spike_missing"] is True
        assert without["spike_key"] == "OCPEDGE-41"
        # The linked fetch supplies assignee == QA Contact → test plan spike.
        linked = [ref_spike("OCPEDGE-41", "Investigate perf", status="In Progress",
                            assignee="Alice")]
        with_linked = run([feat], [], linked_spikes=linked)[self.FK]
        assert with_linked["test_plan_spike_key"] == "OCPEDGE-41"
        assert with_linked["spike_missing"] is True


class TestTestPlanClassifiers(unittest.TestCase):
    def test_summary_phrase_case_insensitive(self):
        assert is_test_plan_spike({"summary": "QE TEST PLAN draft"}, "Alice") is True

    def test_assignee_match_normalized(self):
        assert is_test_plan_spike({"summary": "x", "assignee": " alice "}, "Alice") is True

    def test_refinement_spike_default(self):
        assert is_test_plan_spike({"summary": "Refine X", "assignee": "Bob"}, "Alice") is False

    def test_is_unassigned_qa(self):
        for v in ("unassigned_jira", "None", "", None, "  UNASSIGNED_JIRA  "):
            assert is_unassigned_qa(v) is True
        assert is_unassigned_qa("Alice") is False


if __name__ == "__main__":
    unittest.main()
