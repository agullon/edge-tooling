# Edge Scrum Law: Scrum Ceremonies

> The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://datatracker.ietf.org/doc/html/rfc2119).
>
> **Canonical source:** edge-context [`procedures/scrum/scrum-meetings.md`](https://github.com/openshift-eng/edge-context/blob/main/procedures/scrum/scrum-meetings.md). If this file and edge-context disagree, edge-context is authoritative and this file must be updated.

## Sprint Planning

**Preparation:**

1. Copy previous sprint review slides; update goal progress, highlights, and scrum report link.
2. Calculate the planning target from the team's average completed story points over the last 3 sprints (edge-context decision 0015). The Jira Velocity chart is the human-facing view of this metric; the edge-scrum automation computes the same raw figure into `velocity.json` as a generated intermediate (team-owned, done-state, and finishing-sprint rules per laws 00/07 and `compute-velocity.py`). Apply known PTO and holiday availability separately when projecting capacity for the remaining sprints.
3. Compare this planning target against the proposed sprint scope.

**Agenda:**

1. Remind team to finalize Jira updates before sprint end.
2. Present previous sprint review slides.
3. End the current sprint; review sprint report metrics.
4. Review carryover stories and newly added items; decide what stays.
5. Pull high-priority, ready-to-work backlog items into the sprint.
6. Assign story points to unestimated items; assign owners.
7. Check total story points against the planning target and review anyone far above or below the ~8 SP per-person guideline; adjust scope if over- or under-committed.
8. Define clear, outcome-oriented sprint goals.
9. Start the sprint.

**After the meeting:** Save completed SP totals to the sprint and release tab in the Sprint Capacity Calculator. The Calculator is the team's historical record of planned-vs-completed SP, not a separate capacity source — the planning target above is the single source for capacity.

## Refinement (Mid-Sprint)

1. Evaluate current sprint progress using the board and sprint report; identify blockers.
2. Create the next sprint in Jira.
3. Review and adjust backlog priorities based on latest product direction.
4. Move high-priority, clearly defined items into the next sprint.
5. Assign SP and assignees to unestimated or unassigned items.
6. Assign action items for any stories requiring additional preparation.

## Retrospective

**Preparation:** Create a dedicated Miro board for the sprint using a fresh template.

**Agenda:**

1. Participants populate the board (went well, didn't, improvement ideas).
2. Each person shares their items.
3. Team votes on topics to discuss.
4. Discuss in vote-count order; timebox each topic.
5. Capture key takeaways and assign action items with owners in the meeting doc.
