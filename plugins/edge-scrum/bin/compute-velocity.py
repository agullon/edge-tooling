#!/usr/bin/env python3
"""Compute team velocity from the last few closed sprints.

Team velocity (edge-context decision 0015) is the average completed story points
of **team-owned** issues over the last 3 closed sprints. It is the preferred
basis for planning sprint and release capacity, replacing the fixed per-person
story-point limit.

Inputs are one or more ``sprint_issues.json`` files (produced by
``transform-sprint-issues.py``) plus the roster. "Team-owned" follows the law 00
roster rule: an issue counts if its **assignee** or **QA Contact** is a roster
member. "Completed" means the issue's status is a sprint done-state. Bug points
count like any other work (edge-context decision 0003), since they already carry
real story points.

A done issue is credited **only to the sprint it finished in**, not to every
sprint it ever touched. The finishing sprint is the issue's **most recent** sprint,
chosen as follows:

1. If the issue's sprints carry end dates (``sprint_details``), pick the one with
   the latest endDate/completeDate (ties broken by the higher sprint id). End date
   is the most reliable recency signal and survives sprints being renumbered or
   reopened out of id order.
2. Otherwise fall back to the highest sprint **id** in ``customfield_10020`` (Jira
   assigns ids chronologically but does not return the array in a reliable order,
   so we use the max id, not the last list entry).

An issue carried from sprint N and closed in N+1 therefore counts once, in N+1.
When no sprint history is available, we fall back to the issue's resolution date
against the sprint's start/end window; if neither is available the issue is skipped
and tallied in ``skipped_no_sprint_data``.

Output (``velocity.json``)::

    {
      "team_velocity": <float, avg done team SP per sprint>,
      "sprint_count": <int>,
      "skipped_no_sprint_data": <int, done issues with no sprint/resolve info>,
      "unmatched_done_sp": <int, done SP in these sprints whose owner is not on the roster>,
      "unmatched_owners": [<owner display name>, ...],
      "sprints": [{"sprint_id", "name", "done_team_sp", "team_done_issues",
                   "skipped_no_sprint_data", "unmatched_done_sp", "unmatched_owners"}, ...]
    }

``unmatched_done_sp``/``unmatched_owners`` surface done work finishing in these
sprints whose assignee/QA Contact did not match any roster member. It is a data-gap
signal (like roster drift): a genuine other-team owner is expected there, but a
roster member who was missed — e.g. because their Jira display name differs from the
roster — shows up as uncounted velocity and should be reconciled.
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from _jira_transforms import (
    load_json,
    parse_date,
    write_output,
    is_sprint_done,
    build_roster_index,
    roster_match,
)


def roster_usernames(roster):
    """Set of roster member usernames (empty set if roster missing members)."""
    return {m.get("username") for m in roster.get("members", []) if m.get("username")}


_PLACEHOLDER_NAMES = {"", "unassigned", "none", "field not configured"}


def is_team_owned(issue, roster_index):
    """law 00: issue belongs to the team if assignee OR QA Contact is a roster member.

    Matches on email/username **or** display name (:func:`roster_match`), because
    live Jira often returns ``email: null`` and only a display name. ``roster_index``
    is a :func:`build_roster_index` result (or a raw roster dict)."""
    if roster_match(issue.get("assignee"), issue.get("assignee_display"), roster_index):
        return True
    if roster_match(issue.get("qa_contact"), issue.get("qa_contact_display"), roster_index):
        return True
    return False


def _owner_label(issue):
    """Best human-readable owner name for an unmatched done issue, or None.

    Prefers the assignee display name, then the raw assignee id, then the QA Contact
    display name — skipping placeholder values like "Unassigned"/"None"."""
    for value in (issue.get("assignee_display"), issue.get("assignee"),
                  issue.get("qa_contact_display")):
        if value and str(value).strip().casefold() not in _PLACEHOLDER_NAMES:
            return str(value).strip()
    return None


def _sprint_matches(sprint_entry, sprint_id):
    """True if a sprint-list entry refers to the same sprint as sprint_id."""
    if sprint_entry == sprint_id:
        return True
    return str(sprint_entry) == str(sprint_id)


def _sprint_num(entry):
    """Numeric value of a sprint id for max-by comparison (unparseable sorts low)."""
    try:
        return int(entry)
    except (ValueError, TypeError):
        return -1


def _parse_end(value):
    """Parse a sprint end date to a date object, or None if absent/unparseable."""
    if not value:
        return None
    try:
        return parse_date(value)
    except (ValueError, TypeError, AttributeError):
        return None


def _finishing_sprint_id(issue):
    """The id of the sprint an issue finished in, or None if no sprint history.

    Prefers the sprint with the latest end date (``sprint_details``); falls back to
    the highest sprint id in ``sprints`` when no end dates are present.
    """
    dated = []
    for d in issue.get("sprint_details") or []:
        sid = d.get("id")
        end = _parse_end(d.get("end"))
        if sid is not None and end is not None:
            # Sort key: latest end date wins, ties broken by the higher id.
            dated.append((end, _sprint_num(sid), sid))
    if dated:
        dated.sort()
        return dated[-1][2]
    ids = [s for s in (issue.get("sprints") or []) if s is not None]
    if ids:
        return max(ids, key=_sprint_num)
    return None


def _resolved_in_window(resolved, sprint_start, sprint_end):
    """True if the resolution date falls within [sprint_start, sprint_end]."""
    if not resolved or not sprint_start or not sprint_end:
        return False
    try:
        r = parse_date(resolved)
        return parse_date(sprint_start) <= r <= parse_date(sprint_end)
    except (ValueError, TypeError, AttributeError):
        return False


def _finished_in_sprint(issue, sprint_id, sprint_start, sprint_end):
    """Decide whether a done issue should be credited to this sprint.

    Returns "yes" (count it), "no" (finished elsewhere), or "unknown" (no sprint
    history and no usable resolution date — caller tallies it as skipped).
    """
    finishing = _finishing_sprint_id(issue)
    if finishing is not None:
        # The finishing sprint is the most recent one: by latest end date when the
        # sprints carry dates, otherwise by highest sprint id (see _finishing_sprint_id).
        return "yes" if _sprint_matches(finishing, sprint_id) else "no"
    if issue.get("resolved") and sprint_start and sprint_end:
        return "yes" if _resolved_in_window(issue.get("resolved"), sprint_start, sprint_end) else "no"
    return "unknown"


def compute_sprint_velocity(issues, roster_index, sprint_id=None,
                            sprint_start=None, sprint_end=None):
    """Done team-owned SP, issue count, skipped count, and unmatched owners for one sprint.

    Credits a done issue only to the sprint it finished in (by latest sprint end
    date, then highest sprint id, then resolution date against the sprint window).
    "Done" follows law 07 per issue type (:func:`is_sprint_done`): OCPBUGS bugs at
    Verified/Closed, everything else only at Closed.

    Done team-owned issues with no sprint/resolution signal are returned in
    ``skipped``. Done issues finishing in this sprint whose owner is **not** on the
    roster are tallied in ``unmatched_sp``/``unmatched_owners`` so the caller can
    flag velocity that is not being credited to the team (e.g. a roster member whose
    Jira display name was missed). Returns ``(done_sp, done_issues, skipped,
    unmatched_sp, unmatched_owners)`` with ``unmatched_owners`` sorted.
    """
    done_sp = 0
    done_issues = 0
    skipped = 0
    unmatched_sp = 0
    unmatched_owners = set()
    for issue in issues:
        if not is_sprint_done(issue):
            continue
        team_owned = is_team_owned(issue, roster_index)
        verdict = _finished_in_sprint(issue, sprint_id, sprint_start, sprint_end)
        if team_owned:
            if verdict == "yes":
                done_sp += issue.get("sp", 0)
                done_issues += 1
            elif verdict == "unknown":
                skipped += 1
            # "no": finished in a different sprint — credited there, not here.
        elif verdict == "yes":
            # Done work finishing in this sprint but owned by a non-roster user:
            # expected for other teams, but a data-gap signal if a teammate was missed.
            unmatched_sp += issue.get("sp", 0)
            label = _owner_label(issue)
            if label:
                unmatched_owners.add(label)
    return done_sp, done_issues, skipped, unmatched_sp, sorted(unmatched_owners)


def compute_velocity(sprint_data, roster):
    """Aggregate per-sprint done team SP into an average velocity.

    ``sprint_data`` is a list of parsed sprint_issues dicts. The average is taken
    over the sprints provided (callers pass the most recent 3 closed sprints);
    fewer is allowed and still produces a usable figure.
    """
    roster_index = build_roster_index(roster)
    sprints = []
    total_skipped = 0
    total_unmatched_sp = 0
    all_unmatched_owners = set()
    for sd in sprint_data:
        done_sp, done_issues, skipped, unmatched_sp, unmatched_owners = compute_sprint_velocity(
            sd.get("issues", []),
            roster_index,
            sprint_id=sd.get("sprint_id"),
            sprint_start=sd.get("sprint_start"),
            sprint_end=sd.get("sprint_end"),
        )
        total_skipped += skipped
        total_unmatched_sp += unmatched_sp
        all_unmatched_owners.update(unmatched_owners)
        sprints.append({
            "sprint_id": sd.get("sprint_id"),
            "name": sd.get("sprint_name"),
            "done_team_sp": done_sp,
            "team_done_issues": done_issues,
            "skipped_no_sprint_data": skipped,
            "unmatched_done_sp": unmatched_sp,
            "unmatched_owners": unmatched_owners,
        })
    count = len(sprints)
    team_velocity = round(sum(s["done_team_sp"] for s in sprints) / count, 1) if count else None
    return {
        "team_velocity": team_velocity,
        "sprint_count": count,
        "skipped_no_sprint_data": total_skipped,
        "unmatched_done_sp": total_unmatched_sp,
        "unmatched_owners": sorted(all_unmatched_owners),
        "sprints": sprints,
    }


def main():
    parser = argparse.ArgumentParser(description="Compute team velocity from closed sprints")
    parser.add_argument("--sprint-issues", nargs="*", default=[],
                        help="Zero or more sprint_issues.json files (most recent closed "
                        "sprints). With none, velocity is null and callers use the "
                        "roster-sum fallback instead of crashing.")
    parser.add_argument("--roster", required=True, help="Path to .roster.json")
    parser.add_argument("--output", required=True, help="Output path for velocity.json")
    args = parser.parse_args()

    sprint_data = [load_json(p) for p in args.sprint_issues]
    roster = load_json(args.roster)

    output = compute_velocity(sprint_data, roster)
    write_output(output, args.output)


if __name__ == "__main__":
    main()
