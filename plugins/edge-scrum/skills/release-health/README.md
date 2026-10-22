# release-health

Release cycle health analysis for the OpenShift Edge team. Traverses the full Jira hierarchy — Features and Initiatives down to Stories and Tasks — and produces a structured status report with risk assessment, refinement gaps, sprint forecasting, and prioritized actions.

## Usage

```text
/release-health [version] [sprint-range] [bc:branch-cut-sprint] [--refinement]
```

**Examples:**

```text
/release-health
```

Interactive — asks for version, sprint range, and branch cut sprint.

```text
/release-health 4.19 281-285 bc:285
```

Analyzes OCP 4.19, Sprints 281–285, branch cut at Sprint 285.

```text
/release-health 4.20
```

Asks for sprint range interactively after auto-detecting the version.

```text
/release-health 5.0 --refinement
```

Refinement-only mode — checks whether Features in Refinement status are fully broken down to the story level with all fields populated.

## What It Analyzes

**Hierarchy traversal**: Features/Initiatives (OCPSTRAT) → Epics (OCPEDGE, USHIFT) → Stories/Tasks/Bugs (OCPEDGE, USHIFT, OCPBUGS)

**Per issue, identifies**:

- Assignee, QA Contact, Docs Approver, SME
- Story points / T-shirt sizing
- Acceptance criteria presence
- Sprint assignment

**Risk signals**:

- Schedule risk (completion % vs. expected % given sprints elapsed)
- Staffing gaps (no DRI, no QA contact)
- Refinement gaps (no AC, no sizing, no stories under an Epic)
- Spike gaps — a missing or unclosed **refinement spike**, and separately a missing or unclosed **test plan spike** owned by the QE Lead (law 12; skipped when the Feature's QA Contact is `unassigned_jira`)
- Blocked work (flagged, blocked-by links, Blocked/Parked labels, stale issues)
- Capacity risk (total remaining SP vs. team velocity × remaining sprints)

## Output

### Standard mode

Saves a report to `.reports/release_health_{version}_{YYYY-MM-DD}.md` and prints to terminal.

Report sections:

1. **Executive Summary** — overall health verdict and top risks
2. **Release Dashboard** — one-line status per Feature/Initiative
3. **Feature/Initiative Detail** — per-feature breakdown with Epics and actions
4. **Epic Detail** — issue-level view for active/at-risk Epics
5. **Risk Register** — all risks sorted by severity
6. **Refinement Backlog** — what needs grooming and at what level
7. **Sprint Forecast** — velocity-based projection through branch cut
8. **Recommended Actions** — prioritized, owner-assigned action list

### Refinement mode (`--refinement`)

Saves a condensed report to `.reports/refinement_{version}_{YYYY-MM-DD}.md`.

Checks whether Features in Refinement status are fully broken down (Feature → Epics → Stories) with all required fields populated. Output is grouped by SME with natural language summaries:

> Alice, OCPSTRAT-2607 Bandwidth Reduction has 2 issues: no size set on the feature, and Epic 'CLI Monitoring' has no stories underneath. The 'Staging Mechanism' epic is fine — 5 stories, all sized.

Features with zero gaps are omitted. Features without an SME are grouped under "Unassigned SME" with a PM action callout. All levels are checked regardless of gaps found above — a feature missing an SME still gets its Epics and Stories checked. Test plan spike gaps are listed under the SME group with the QE Lead named as owner.

## Configuration

Defaults are set for OpenShift Edge in the skill frontmatter.

- `board_id` — Jira board ID
- `feature_label` — label applied to Features/Initiatives in scope
- `projects` — primary, strategy, and bugs project keys
- `ocpbugs_components` — components owned by the team in OCPBUGS
- `fields.docs_approver` / `fields.sme` — custom field IDs (verify with your Jira admin)
