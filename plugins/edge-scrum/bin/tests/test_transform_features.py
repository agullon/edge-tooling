"""Tests for transform-features."""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from importlib import import_module

_mod = import_module("transform-features")
transform_feature = _mod.transform_feature


class TestPriority(unittest.TestCase):
    def test_priority_is_persisted(self):
        raw = {"key": "OCPSTRAT-1", "summary": "F", "status": {"name": "New"},
               "priority": {"name": "Blocker"}}
        assert transform_feature(raw)["priority"] == "Blocker"

    def test_priority_defaults_to_undefined_when_absent(self):
        raw = {"key": "OCPSTRAT-2", "summary": "F", "status": {"name": "New"}}
        assert transform_feature(raw)["priority"] == "Undefined"

    def test_priority_defaults_to_undefined_when_null(self):
        raw = {"key": "OCPSTRAT-3", "summary": "F", "status": {"name": "New"}, "priority": None}
        assert transform_feature(raw)["priority"] == "Undefined"


class TestSpikeCandidateResolution(unittest.TestCase):
    def _feature_with_spike(self, spike):
        return {
            "key": "OCPSTRAT-1", "summary": "F", "status": {"name": "New"},
            "issuelinks": [{
                "type": {"inward": "is blocked by"},
                "inward_issue": dict(spike, issuetype={"name": "Spike"}),
            }],
        }

    def test_resolution_captured_from_spike(self):
        raw = self._feature_with_spike(
            {"key": "OCPEDGE-9", "summary": "Test plan spike",
             "status": {"name": "Closed"}, "resolution": {"name": "Won't Do"}})
        spike = transform_feature(raw)["spike_candidates"][0]
        assert spike["key"] == "OCPEDGE-9"
        assert spike["resolution"] == "Won't Do"

    def test_resolution_empty_when_absent(self):
        raw = self._feature_with_spike(
            {"key": "OCPEDGE-9", "summary": "Spike", "status": {"name": "New"}})
        assert transform_feature(raw)["spike_candidates"][0]["resolution"] == ""


if __name__ == "__main__":
    unittest.main()
