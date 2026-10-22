#!/usr/bin/env python3
"""Match spikes to features and produce spikes.json."""

import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _jira_transforms import (
    extract_display_name,
    get_nested,
    load_json,
    load_issues,
    write_output,
)


EPIC_PLANNING_STATE = "Planning"
FEATURE_PRE_REFINED_STATES = {"New", "Refinement"}


def epics_look_refined(epic_records):
    """Check if a set of epics collectively appear refined.

    True when every epic has moved past the Planning state, which per
    workflow-states law means "Refinement done; ready for sprint planning."
    """
    if not epic_records:
        return False
    return all(e.get("status") and e.get("status") != EPIC_PLANNING_STATE for e in epic_records)


def _normalize_name(name):
    """Casefolded, stripped display name for owner comparison."""
    return (name or "").strip().casefold()


def is_unassigned_qa(qa_contact):
    """True when a Feature's QA Contact (QE Lead) is effectively unset.

    Per law 12 a Feature with no QE need sets QA Contact to ``unassigned_jira``
    (MUST NOT leave blank); the feature transform also stores ``"None"`` when the
    field is empty. In either case no QE Lead owns a test plan spike, so the test
    plan spike check is skipped (law 14)."""
    return _normalize_name(qa_contact) in {"", "none", "unassigned_jira"}


def is_test_plan_spike(spike, qa_contact):
    """Classify a spike that blocks a Feature as a test plan spike (law 14).

    A spike is a test plan spike when its summary contains "test plan"
    (case-insensitive) or its assignee matches the Feature's QA Contact / QE Lead
    (display names, normalized). Otherwise it is a refinement spike. The assignee
    rule is only applied when the Feature has a real QA Contact — when the check
    is skipped (``unassigned_jira``/``None``) only the summary rule can match."""
    summary = spike.get("summary") or ""
    if "test plan" in summary.lower():
        return True
    if not is_unassigned_qa(qa_contact):
        assignee = spike.get("assignee") or ""
        if assignee and _normalize_name(assignee) == _normalize_name(qa_contact):
            return True
    return False


_SPIKE_KEY_RE = re.compile(r"^([A-Za-z]+)-(\d+)$")


def _spike_sort_key(key):
    """Sort spikes by project then **numeric** id, so OCPEDGE-9 precedes OCPEDGE-10
    (plain string sort would order them lexicographically and pick OCPEDGE-10 first)."""
    m = _SPIKE_KEY_RE.match(key or "")
    if m:
        return (m.group(1), int(m.group(2)))
    return (key or "", 0)


def _status_rank(status):
    """Selection preference for a spike's status: Closed first, then In Progress,
    then anything else — so a satisfied (Closed) spike represents the feature."""
    s = (status or "").strip()
    if s == "Closed":
        return 0
    if s == "In Progress":
        return 1
    return 2


def _select_primary(keys, detail_fn):
    """Pick the representative spike from ``keys``.

    Prefer a Closed spike, then In Progress, then others (:func:`_status_rank`);
    break ties by numeric key order (:func:`_spike_sort_key`). This means that when
    any spike of a kind is Closed, the primary is Closed and the check is satisfied —
    rather than picking the first key and calling the feature overdue because that
    particular one is still open."""
    if not keys:
        return None
    return min(keys, key=lambda k: (_status_rank(detail_fn(k).get("status")), _spike_sort_key(k)))


def _merge_nonempty(base, overlay):
    """Overlay ``overlay`` onto ``base`` without letting an empty value clobber a
    non-empty one. A missing key is still added (even if empty) so the shape is
    complete; a present non-empty value is never overwritten with blank."""
    out = dict(base)
    for k, v in (overlay or {}).items():
        if v in (None, "", [], {}):
            out.setdefault(k, v)
        else:
            out[k] = v
    return out


def _spike_detail(key, cand_by_key, linked_by_key, ref_by_key):
    """Merge a spike's candidate, linked-fetch and refinement-sprint records.

    A spike may surface three ways: as a ``spike_candidate`` on the feature's
    issuelinks (summary/assignee often missing in that payload), as a separately
    fetched ``--linked-spikes`` record (fills in assignee/status/resolution for
    spikes reachable only via issuelinks), and as a refinement-sprint spike (most
    authoritative). Later sources win, but :func:`_merge_nonempty` ensures an empty
    field never overwrites a value an earlier source already supplied."""
    detail = dict(cand_by_key.get(key, {}))
    detail = _merge_nonempty(detail, linked_by_key.get(key, {}))
    detail = _merge_nonempty(detail, ref_by_key.get(key, {}))
    return detail


def build_spike_map(features, feature_keys, feature_to_epics, epics_by_key,
                    ref_spikes, ref_sprint_closed, linked_spikes=None):
    """Classify the spikes blocking each feature into a refinement spike and a
    test plan spike, and compute the per-feature spike signals.

    The implicit-refinement signals (``spike_*``) describe the **refinement spike
    only** — a test plan spike can no longer satisfy them (laws 12, 14). Test plan
    spikes get their own ``test_plan_spike_*`` fields.

    ``linked_spikes`` are spikes fetched separately because they are reachable only
    through a feature's issuelinks (not in the refinement sprint); they enrich the
    classification with assignee/status/resolution that the issuelink payload lacked.
    They do not establish refinement-sprint membership (``spike_in_ref_sprint``)."""
    feature_keys = set(feature_keys)
    ref_by_key = {s["key"]: s for s in ref_spikes}
    linked_by_key = {s["key"]: s for s in (linked_spikes or [])}

    # Build spike -> feature mapping from ref sprint spikes (outward "blocks" links)
    spike_to_features = {}
    for spike in ref_spikes:
        for link in spike.get("issuelinks", []):
            link_type = link.get("type", {})
            if link_type.get("outward") == "blocks":
                outward = link.get("outward_issue") or link.get("outwardIssue")
                if outward and outward.get("key") in feature_keys:
                    spike_to_features.setdefault(spike["key"], []).append(outward["key"])

    spike_map = {}
    for feat in features:
        fk = feat["key"]
        qa_contact = feat.get("qa_contact", "None")
        test_plan_check_skipped = is_unassigned_qa(qa_contact)

        cand_by_key = {sc["key"]: sc for sc in feat.get("spike_candidates", [])}

        # All spikes that block this feature: ref sprint spikes + linked candidates
        matched = set()
        for spike in ref_spikes:
            if fk in spike_to_features.get(spike["key"], []):
                matched.add(spike["key"])
        for sc in feat.get("spike_candidates", []):
            matched.add(sc["key"])

        detail_fn = lambda k: _spike_detail(k, cand_by_key, linked_by_key, ref_by_key)

        # Split into refinement vs test plan spikes (numeric key order)
        refinement_keys = []
        test_plan_keys = []
        for key in sorted(matched, key=_spike_sort_key):
            if is_test_plan_spike(detail_fn(key), qa_contact):
                test_plan_keys.append(key)
            else:
                refinement_keys.append(key)

        # --- Refinement spike (implicit-refinement signals apply here only) ---
        # Pick the representative spike by status preference (Closed satisfies the
        # check), not just the lowest key — see _select_primary.
        primary = _select_primary(refinement_keys, detail_fn)
        if primary:
            spike_status = detail_fn(primary).get("status") or "Unknown"
        else:
            spike_status = "Missing"
        spike_in_ref = primary is not None and primary in ref_by_key

        # Detect refinement spikes linked to child epics instead of the feature
        child_epic_keys = set(feature_to_epics.get(fk, []))
        on_epic_keys = []
        if primary is None and child_epic_keys:
            for spike in ref_spikes:
                for link in spike.get("issuelinks", []):
                    if link.get("type", {}).get("outward") == "blocks":
                        outward = link.get("outward_issue") or link.get("outwardIssue")
                        if outward and outward.get("key") in child_epic_keys:
                            on_epic_keys.append(outward["key"])

        # Check if child epics collectively appear refined. If the feature itself
        # is still in New/Refinement, its workflow state is authoritative.
        child_epics = [epics_by_key[ek] for ek in child_epic_keys if ek in epics_by_key]
        feat_status = feat.get("status", "")
        if feat_status in FEATURE_PRE_REFINED_STATES:
            appear_refined = False
        else:
            appear_refined = epics_look_refined(child_epics)

        # --- Test plan spike (law 12 step 3) ---
        # Prefer a Closed test plan spike so one Closed spike satisfies the check.
        tp_primary = _select_primary(test_plan_keys, detail_fn)
        if tp_primary:
            tp_detail = detail_fn(tp_primary)
            tp_status = tp_detail.get("status") or "Unknown"
            tp_resolution = tp_detail.get("resolution") or None
        else:
            tp_status = "Missing"
            tp_resolution = None

        spike_map[fk] = {
            "spike_key": primary,
            "spike_keys": refinement_keys,
            "spike_status": spike_status,
            "spike_in_ref_sprint": spike_in_ref,
            "spike_overdue": (
                ref_sprint_closed and primary is not None and spike_status != "Closed"
            ),
            "spike_missing": primary is None,
            "spike_on_epic": bool(on_epic_keys),
            "spike_on_epic_keys": sorted(set(on_epic_keys)),
            "feature_pre_refined": feat_status in FEATURE_PRE_REFINED_STATES,
            "epics_appear_refined": appear_refined,
            "test_plan_spike_key": tp_primary,
            "test_plan_spike_keys": test_plan_keys,
            "test_plan_spike_status": tp_status,
            "test_plan_spike_resolution": tp_resolution,
            # A Closed test plan spike satisfies the check regardless of resolution.
            "test_plan_spike_missing": tp_primary is None,
            "test_plan_spike_overdue": (
                ref_sprint_closed and tp_primary is not None and tp_status != "Closed"
            ),
            "test_plan_check_skipped": test_plan_check_skipped,
        }

    return spike_map


def summarize(spike_map, total):
    """Roll up per-feature spike signals into summary counts."""
    def count(pred):
        return sum(1 for v in spike_map.values() if pred(v))

    return {
        "features_with_spike": count(lambda v: not v["spike_missing"]),
        "features_with_closed_spike": count(lambda v: v["spike_status"] == "Closed"),
        "features_missing_spike": count(lambda v: v["spike_missing"]),
        "features_spike_on_epic": count(lambda v: v["spike_on_epic"]),
        "features_refined_via_epics": count(
            lambda v: v["spike_missing"]
            and not v["feature_pre_refined"]
            and (v["spike_on_epic"] or v["epics_appear_refined"])
        ),
        "features_with_test_plan_spike": count(lambda v: not v["test_plan_spike_missing"]),
        "features_missing_test_plan_spike": count(
            lambda v: v["test_plan_spike_missing"] and not v["test_plan_check_skipped"]
        ),
        "features_test_plan_check_skipped": count(lambda v: v["test_plan_check_skipped"]),
        "total_features": total,
    }


def normalize_ref_spike(raw):
    """Normalize a raw refinement-sprint spike MCP record.

    Carries summary, status, assignee (display name) and resolution so the
    test plan / refinement classification and report have what they need."""
    res = raw.get("resolution")
    if isinstance(res, dict):
        resolution = res.get("name")
    elif isinstance(res, str):
        resolution = res or None
    else:
        resolution = None
    return {
        "key": raw.get("key", ""),
        "summary": raw.get("summary", ""),
        "status": get_nested(raw, "status", "name") or "",
        "assignee": extract_display_name(raw.get("assignee"), ""),
        "resolution": resolution,
        "issuelinks": raw.get("issuelinks", []),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Match spikes to features and produce spikes.json"
    )
    parser.add_argument(
        "--input", nargs="+", required=True,
        help="Raw MCP response file(s) for refinement sprint spikes",
    )
    parser.add_argument("--features-file", required=True, help="Path to features.json")
    parser.add_argument("--epics-file", required=True, help="Path to epics.json")
    parser.add_argument("--sprints-file", required=True, help="Path to sprints.json")
    parser.add_argument(
        "--linked-spikes", nargs="*", default=[],
        help="Optional raw MCP response file(s) for spikes reachable only via a "
        "feature's issuelinks (fetched to fill in assignee/status/resolution).",
    )
    parser.add_argument("--output", required=True, help="Output path")
    args = parser.parse_args()

    sprints_data = load_json(args.sprints_file)
    features_data = load_json(args.features_file)
    epics_data = load_json(args.epics_file)

    ref_sprint_closed = sprints_data.get("refinement_sprint_closed", False)
    features = features_data.get("features", [])
    feature_keys = set(features_data.get("feature_keys", []))

    feature_to_epics = epics_data.get("feature_to_epics", {})
    epics_by_key = {e["key"]: e for e in epics_data.get("epics", [])}

    # Load and normalize ref sprint spikes
    ref_spikes = [normalize_ref_spike(raw) for raw in load_issues(args.input)]
    # Spikes reachable only via feature issuelinks, fetched to fill in assignee/
    # status/resolution (same record shape as ref spikes, but not in the ref sprint).
    linked_spikes = [normalize_ref_spike(raw) for raw in load_issues(args.linked_spikes)] \
        if args.linked_spikes else []

    spike_map = build_spike_map(
        features, feature_keys, feature_to_epics, epics_by_key,
        ref_spikes, ref_sprint_closed, linked_spikes=linked_spikes,
    )

    output = {
        "spike_map": spike_map,
        "all_ref_sprint_spikes": ref_spikes,
        "linked_spikes": linked_spikes,
        "summary": summarize(spike_map, len(features)),
    }

    write_output(output, args.output)


if __name__ == "__main__":
    main()
