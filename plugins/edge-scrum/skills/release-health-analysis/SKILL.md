---
name: release-health-analysis
description: Analyze release health data and produce assessment
allowed-tools: Read, Write, Bash, mcp__plugin_mcp-atlassian_mcp-atlassian__jira_search
user-invocable: false
---

# release-health: Analysis

## Purpose

Perform the full hierarchy analysis, risk assessment, and generate all report sections, writing the results to `analysis.md` in the work directory.

## When to Spawn

The parent release-health skill spawns this agent during Phase 4, after Phase 3 (Epic Fetcher + Spike Finder) completes. This is the only Phase 4 agent.

## Capabilities

- Jira MCP search queries (`jira_search`)
- File reading via `Read` tool (all four phase data files + Edge Scrum Laws + `.roster.json`)
- JSON file writing via `Write` tool

This agent does **not** modify any Jira data.

## Parameters

Substituted by the parent before spawning:

| Placeholder | Description |
|---|---|
| `{WORKDIR}` | Work directory path |
| `{VELOCITY_DIR}` | Velocity directory path (holds `velocity.json`; empty when velocity was not collected) |
| `{VERSION}` | OCP release version (e.g., `4.19`, `5.0`) |
| `{TODAY}` | Today's date in `YYYY-MM-DD` format |
| `{REFINEMENT_SPRINT_NUM}` | Sprint number of the refinement sprint |
| `{REFINEMENT_MODE}` | `true` or `false` — when true, produce additional `REFINEMENT_BY_SME` output section |
| `{AVAILABILITY}` | Per-remaining-sprint PTO/holiday availability CSV (e.g. `1,0.6,1`); empty when not collected — capacity then uses the full `remaining_sprint_count` and is not adjusted for PTO |

## Instructions

### 1. Read Context Files

1. `plugins/edge-scrum/.roster.json`
   Extract: `members` array — use `username` for ownership matching.
   Derive `roster_size` (count of members) and `total_sp_per_sprint` (sum of all `sp_target` values).
   `total_sp_per_sprint` is the **roster fallback** for capacity, used only when measured velocity is unavailable (decision 0015); it is not the team's capacity.
   If a member is missing `sp_target`, default that member to 8. If the file is absent, halt with an error.
1a. `{VELOCITY_DIR}/velocity.json` (optional; `{VELOCITY_DIR}` empty when the skill skipped velocity collection) — if present, read `team_velocity` (measured SP/sprint over the last 3 closed sprints). This is the preferred capacity basis; the roster sum is only a fallback.
2. Load these law files from `plugins/edge-scrum/references/laws/`:
   - `07-workflow-states.md` — done states per issue type
   - `02-jira-stories.md` — story pointing (bugs are pointed like other work, decision 0003)
   - `04-jira-epics.md` — epic sizing scales
   - `05-jira-features.md` — feature/initiative sizing scales
   - `01-jira-projects.md` — OCPBUGS components
   - `06-jira-fields.md` — custom field IDs
3. `{WORKDIR}/sprints.json`
4. `{WORKDIR}/features.json`
5. `{WORKDIR}/epics.json`
6. `{WORKDIR}/spikes.json`

---

### 2. Fetch Child Issues

Split `epic_keys_csv` from `epics.json` into batches of ~20. For each batch, paginate with `page_token`, `limit=50` until all results are fetched:

```jql
project in (OCPEDGE, USHIFT, OCPBUGS) AND "Epic Link" in ({batch_csv}) ORDER BY priority ASC
```

Also fetch unlinked OCPBUGS bugs (use components from Laws). Paginate with `page_token`, `limit=50` until all results are fetched:

```jql
project = OCPBUGS
  AND component in ("Installer / Single Node OpenShift", "Two Node with Arbiter", "Two Node Fencing", "Logical Volume Manager Storage")
  AND fixVersion in ("{VERSION}", "{VERSION}.0")
  AND "Epic Link" is EMPTY
ORDER BY priority ASC
```

Fields per issue:

```text
key, summary, status, issuetype, priority, assignee, sprint, labels, updated,
customfield_10028, customfield_10470, customfield_10021, parent, customfield_10014, issuelinks
```

Per issue, compute:

- `sp`: `customfield_10028` — `0` if unset; **bugs are pointed like other work (decision 0003)**, so use their actual value
- `epic_key`: the native `parent` key when the parent is an Epic, else the legacy Epic Link `customfield_10014` (or `"No Epic"`)
- `flagged`: `customfield_10021` is non-empty
- `blocked_by`: issuelinks where `type.inward = "is blocked by"` AND blocker status not in {Closed, Verified, Done}
- `stale`: status in {In Progress, Review} AND `updated` older than 5 business days from `{TODAY}`

---

### 3. Build Hierarchy and Rollups

Group: Feature → Epics → Issues.
Orphan groups: `(No Feature)`, `(No Epic)`, `(Unlinked Bugs)`.

**Done states** (from Laws):

- Stories/Tasks/Spikes: Closed
- OCPEDGE Bugs: Closed
- OCPBUGS Bugs: Verified, Closed
- Epics: Closed, Dev Complete, Testing, Release Pending

**Per-Epic rollup:**

| Field | Calculation |
|---|---|
| `total_issues` | count of all child issues |
| `done_issues` | issues in done state |
| `total_sp` | sum of SP (all types, including bugs) |
| `done_sp` | SP of done issues |
| `remaining_sp` | SP of non-done issues |
| `completion_pct` | `done_sp / total_sp × 100`; fallback: `done_issues / total_issues × 100` if total_sp = 0 |
| `unpointed_count` | issues with SP null or 0 (bugs included — decision 0003) |
| `blocked_count` | flagged OR blocked_by non-empty OR "Blocked" in labels |
| `unassigned_count` | no assignee |

**Per-Feature rollup:** aggregate epics; add `epic_count` and `done_epics`.

**Release totals:**

- `total_remaining_sp` = sum of `remaining_sp` over **in-scope** epics only — **exclude** epics already in a done state (Closed/Dev Complete/Testing/Release Pending, per law 07) and epics whose Target/Fix Version is set to a different release. This matches `run-checks.py`'s capacity scope: a done epic's leftover SP and another release's epics are not demand on this release's remaining capacity, so counting them would inflate `total_remaining_sp` and invent a capacity shortfall. List the excluded epics in the report rather than silently dropping them.
- `effective_sprint_count`: the availability-adjusted sprints left. If `{AVAILABILITY}` (the per-sprint PTO/holiday CSV collected by the release-health skill) is non-empty, this is Σ of those fractions (e.g. `1,0.6,1 → 2.6`) and `capacity_pto_adjusted = true`; if `{AVAILABILITY}` is empty it equals `remaining_sprint_count` and `capacity_pto_adjusted = false`. **Edge case — guard:** a full `remaining_sprint_count` over-credits capacity when a remaining sprint has known PTO/holidays, which can hide a real capacity shortfall; always use `effective_sprint_count` below, and when `capacity_pto_adjusted = false` the report must state the capacity is **not adjusted for PTO**.
- `max_sp_capacity` (computed from `effective_sprint_count`, matching `run-checks.py`):
  - If `velocity.json` was present: `team_velocity × effective_sprint_count`; set `capacity_basis = "velocity"`.
  - Otherwise: `effective_sprint_count × total_sp_per_sprint`; set `capacity_basis = "roster_fallback"` (state this in the report — it is a fallback, not measured capacity).

---

### 4. Refinement Reassessment

After building the hierarchy, reassess `epics_appear_refined` for features that the transform did not already mark as refined. For each feature where `spike_missing = true` AND `spike_on_epic = false` AND `epics_appear_refined = false` AND feature status is not "New" or "Refinement":

1. Get the feature's child epics from the hierarchy
2. Skip features with 0 epics — they cannot be refined via epics
3. For each epic, read its `description` (from `epics.json`) and examine the child stories/tasks created under it (from the hierarchy)
4. An epic looks refined if its description describes work to be done AND the existing child stories appear to cover that described work — the stories don't need to be complete, but they should exist and address the scope outlined in the description
5. If **all** of the feature's epics look refined by this assessment, override `epics_appear_refined = true` for that feature

Update `features_refined_via_epics` count accordingly.

---

### 5. Risk Assessment

Read `refinement_sprint_closed` from `sprints.json`.

**7a — Schedule Risk** — Skip entirely if `refinement_sprint_closed = false`.

If `refinement_sprint_closed = true`, per Feature:

| Condition | Status |
|---|---|
| status ∈ {Done, Closed, Release Pending} | ✅ Complete |
| 0% complete AND ≤ 2 dev sprints remaining | 🔴 Critical |
| 0% complete AND ≤ 4 dev sprints remaining | 🟡 At Risk |
| completion_pct ≥ expected_dev_pct | 🟢 On Track |
| completion_pct ≥ expected_dev_pct × 0.75 | 🟡 Slightly Behind |
| completion_pct < expected_dev_pct × 0.75 | 🔴 At Risk |
| no Epics AND ≥ 1 dev sprint remaining | 🔴 Unplanned |

**7b — Staffing:**

- Feature `sme = "None"` → 🔴 "No SME assigned" — Action: "Assign SME this sprint"
- Feature `qa_contact = "None"` AND status ≠ Closed → 🟡 "No QA contact"
- Feature `docs_approver = "None"` → 🟢 "No docs approver"
- Epic `assignee = "Unassigned"` → 🟡 "No epic DRI"
- Epic `qa_contact = "None"` AND status ≠ Closed → 🟡 "No epic QA contact"

**7c — Refinement — Refinement Spike Rules** (based on `refinement_sprint_closed`):

These `spike_*` signals describe the **refinement spike only** — a test plan spike no longer satisfies them (laws 12, 14). The test plan spike is assessed separately below.

Evaluate in this order — first match wins:

1. `spike_status = "Closed"` → ✅ "Closed" — direct spike completed, no risk
2. `spike_missing` AND (`spike_on_epic = true` OR `epics_appear_refined = true`) → ✅ "Via epics" — no spike risk
3. If `refinement_sprint_closed = false`:
   - `spike_missing` → 🔴 "No refinement spike — SME must create one in Sprint {REFINEMENT_SPRINT_NUM} that blocks this Feature"
   - spike exists AND NOT `spike_in_ref_sprint` → 🟡 "Spike not in refinement sprint — move to Sprint {REFINEMENT_SPRINT_NUM}"
   - spike exists AND `spike_in_ref_sprint` AND status ≠ Closed → 🟢 "Spike in progress (expected)"
4. If `refinement_sprint_closed = true`:
   - `spike_overdue = true` → 🔴 "Refinement spike not closed — refinement incomplete"
   - `spike_missing` → 🔴 "No refinement spike found; delivery epics may be under-refined"

**7c — Refinement — Test Plan Spike** (law 12 step 3; the QE Lead's spike, assessed independently of the refinement spike):

Skip all test plan checks when `test_plan_check_skipped = true` (the Feature's QA Contact is `unassigned_jira` or `None` — no QE Lead, so no test plan spike is expected). Otherwise:

- `test_plan_spike_missing = true` → 🟡 "No test plan spike — QE Lead ({qa_contact}) must create one that blocks this Feature"
- `test_plan_spike_overdue = true` (refinement sprint closed AND test plan spike not Closed) → 🟡 "Test plan spike not closed"

A **Closed** test plan spike satisfies the check regardless of its resolution — a deliberate `Won't Do` is a valid skip. Always surface `test_plan_spike_resolution` in the report next to a Closed status (e.g. `Closed (Won't Do)`) so intentional skips are visible.

**7c — Refinement — General:**

- Feature `has_ac = false` → 🟡 "Missing acceptance criteria"
- Feature `size = "Unsized"` → 🟡 "Feature not sized"
- Feature `epic_count = 0` → 🔴 "No epics — unplanned"
- Epic `has_ac = false` → 🟡 "Epic missing AC"
- Epic `size = "Unsized"` → 🟡 "Epic not sized"
- Epic `total_issues = 0` → 🟡 "Empty epic — no stories"
- Story/Task `sp null or 0` → 🟡 "Needs estimation"
- Story/Task `assignee = "Unassigned"` → 🟡 "Needs owner"

**7d — Blocked/Stalled:**

- `flagged = true` → 🔴 "Impediment flagged"
- `blocked_by` non-empty → 🔴 "Blocked by {keys}"
- `"Blocked"` in labels → 🔴 "Labeled Blocked"
- `"Parked"` in labels → 🟡 "Parked"
- `stale = true` → 🟡 "Stale — no update in 5+ business days"

**7e — Release-Level:**

- XL-sized epic AND `remaining_sprint_count ≤ 2` → 🔴 "XL-sized epic unlikely to complete"
- L-sized epic AND `remaining_sprint_count ≤ 1` → 🔴 "L-sized epic at risk"
- `total_remaining_sp > max_sp_capacity` → 🔴 "Capacity risk"
- (if `refinement_sprint_closed` AND `total_features > 0`) `(features_missing_spike - features_refined_via_epics) / total_features > 0.5` → 🔴 "Systematic refinement gap"
- (if `refinement_sprint_closed` AND `total_features > 0`) `(features_with_closed_spike + features_refined_via_epics) / total_features < 0.75` → 🟡 "Refinement coverage below 75%"

---

### 6. Write Output

Write to `{WORKDIR}/analysis.md` with this exact sentinel structure:

```text
===ANALYSIS_META===
{
  "total_features": <int>,
  "features_on_track": <int>,
  "features_at_risk": <int>,
  "features_complete": <int>,
  "high_risk_count": <int>,
  "medium_risk_count": <int>,
  "low_risk_count": <int>,
  "overall_health": "Critical|At Risk|On Track|Complete",
  "actual_completion_pct": <float>,
  "expected_dev_completion_pct": <float>,
  "features_with_spike": <int>,
  "features_with_closed_spike": <int>,
  "features_missing_spike": <int>,
  "features_spike_on_epic": <int>,
  "features_refined_via_epics": <int>,
  "remaining_sp": <int>,
  "max_sp_capacity": <int>,
  "capacity_basis": "velocity|roster_fallback",
  "capacity_pto_adjusted": <bool>,
  "capacity_risk": <bool>,
  "top_risks": ["<concise description>", ...],
  "sprint_recommendation": "<one sentence priority for this sprint>",
  "refined_count": <int>,
  "needs_attention_count": <int>
}
===END_META===

When `{REFINEMENT_MODE}` = `true`, compute and include `refined_count` (features with zero gaps at all levels) and `needs_attention_count` (`total_features - refined_count`). When `false`, set both to 0.

===SECTION:DASHBOARD===
| Key | Feature/Initiative | Type | Status | SME | QA | Size | Refn Spike | Epics Done | Progress | Risk |
|---|---|---|---|---|---|---|---|---|---|---|
(one row per feature, sorted by Jira rank — preserve the priority order returned by the JQL query)
Spike column: ✅ Closed | ✅ Via epics | 🔄 In Progress | ⚠️ Missing | ⏳ Open
===END_SECTION===

===SECTION:FEATURE_DETAIL===
(one subsection per feature, sorted by Jira rank — same order as the dashboard)

### OCPSTRAT-XXX: {Summary}

**Type**: {type} | **Status**: {status} | **Health**: {emoji}
**SME**: {sme} | **QA**: {qa_contact} | **Docs**: {docs_approver}
**Refinement Spike**: {spike_key — ✅ Closed | ✅ Via epics | 🔄 In Progress | ⚠️ Missing | ⏳ Open}
**Test Plan Spike**: {test_plan_spike_key — status, appending resolution when Closed (e.g. "Closed (Won't Do)") | ⚠️ Missing | n/a when test_plan_check_skipped}
**Progress**: {done_sp}/{total_sp} SP ({pct}%) — {done_epics}/{epic_count} epics complete
**Refinement**: {✅ Has AC | ⚠️ Needs AC} | **Sized**: {✅ | ⚠️ Unsized}

#### Epics
| Epic | DRI | QA | Size | Issues | Progress | Status | Health |

#### Risks & Gaps
- {severity}: {description} — Action: {action}

#### Actions
- [ ] {action} — Owner: {owner}

===END_SECTION===

===SECTION:EPIC_DETAIL===
(only epics with blocked, stale, flagged, or unpointed issues)

### OCPEDGE-XXX: {Epic Summary}

**DRI**: {assignee} | **QA**: {qa_contact} | **Progress**: {done}/{total} SP

| Issue | Type | DRI | SP | Status | Sprint | Flags |
|---|---|---|---|---|---|---|

Flag legend: 🚫 Blocked | ⏸️ Parked | ⚠️ Unpointed | 🔴 Flagged | 💤 Stale
===END_SECTION===

===SECTION:RISK_REGISTER===
### 🔴 High Priority
| # | Issue | Risk Type | Description | Owner | Action |
|---|---|---|---|---|---|

### 🟡 Medium Priority
| # | Issue | Risk Type | Description | Owner | Action |
|---|---|---|---|---|---|

### 🟢 Low / Informational
| # | Issue | Risk Type | Description | Owner | Action |
|---|---|---|---|---|---|
===END_SECTION===

===SECTION:REFINEMENT_BACKLOG===
### Features/Initiatives
- OCPSTRAT-XXX — Missing: {items}

### Epics
- OCPEDGE-XXX — Missing: {items}

### Stories/Tasks (Unpointed or Unassigned)
- OCPEDGE-XXX (Epic: OCPEDGE-YYY) — {issue}
===END_SECTION===

===SECTION:SPRINT_FORECAST===
| Sprint | State | Projected SP | Cumulative | Cumulative % | Notes |
|---|---|---|---|---|---|
Compute each sprint row's **Projected SP** as `team_velocity × availability_i`, where `availability_i` is that sprint's fraction from `{AVAILABILITY}` (the per-sprint PTO/holiday CSV), using `1.0` for any sprint whose availability is absent. Derive **Cumulative** and **Cumulative %** from these availability-adjusted rows so the forecast total matches `max_sp_capacity` (= `team_velocity × effective_sprint_count`) rather than `team_velocity × remaining_sprint_count`. If `velocity.json` is absent, fall back to `total_sp_per_sprint` (from `.roster.json`) as the per-sprint base and note it is a roster fallback, not measured velocity.
State the capacity line as `max_sp_capacity SP ({capacity_basis}) over effective_sprint_count sprints`; when `capacity_pto_adjusted = false`, append "— not adjusted for PTO".
Flag if projected completion at branch cut < 85% → add ⚠️ in Notes.
===END_SECTION===

===SECTION:ACTIONS===
### This Sprint — Immediate
1. {Action} — Owner: {person}

### Next Sprint
1. {Action} — Owner: {person}

### Grooming / Planning
1. {Action} — Target: Sprint {N} grooming
===END_SECTION===
```

#### Refinement-by-SME Section (only when `{REFINEMENT_MODE}` = `true`)

After writing all standard sections above, append this additional section. It reorganizes the refinement gaps from the existing analysis into an SME-centric view with natural language summaries.

```text
===SECTION:REFINEMENT_BY_SME===
## Refinement Status: OCP {VERSION}

**{refined_count} of {total_features} features are fully refined. {needs_attention_count} need attention.**

(For each SME that has at least one feature with gaps, produce a section. Omit SMEs whose features have zero gaps.)

### {SME display name} ({feature_count} features, {gaps_count} need attention)

**{OCPSTRAT-XXX} — {Feature Summary}**
{Natural language description of ALL gaps found at every level for this feature. Cover Feature-level gaps, then Epic-level, then Story-level. Be specific and actionable. Reference epic names and story counts.}

Example tone and format:
"No size set on the feature. Epic 'CLI Monitoring' (OCPEDGE-1234) has no stories underneath. Epic 'Staging Mechanism' (OCPEDGE-1235) looks good — 5 stories, all sized. 2 stories under 'Data Pipeline' (OCPEDGE-1236) are missing story points."

(Repeat for each feature under this SME that has gaps.)

### Unassigned SME (PM action needed)

**{OCPSTRAT-XXX} — {Feature Summary}**
No SME assigned — PM needs to assign one before refinement can proceed. {Continue listing any other gaps found at Epic/Story level below this feature — do not stop at the missing SME.}

===END_SECTION===
```

**Rules for the REFINEMENT_BY_SME section:**

1. **No early stopping**: Even if a Feature has no SME or no Epics, continue checking ALL levels and report everything found. A Feature with no SME may still have Epic and Story-level gaps worth reporting.
2. **Group by SME**: Use the SME's `display_name` from `features.json`. Features with no SME go under "Unassigned SME."
3. **Omit clean features**: If a Feature has zero gaps at any level, do not mention it in the SME's section.
4. **Natural language**: Do not use tables for the per-feature descriptions. Write conversational, actionable sentences that an SME can read and act on without opening Jira.
5. **Docs epics excluded**: In the REFINEMENT_BY_SME section only, skip epics whose summary starts with "Docs" and belong to the OSDOCS project — these are auto-generated and not part of refinement checks. Other sections (REFINEMENT_BACKLOG, standard report sections) are unaffected.
6. **All gap types apply**: Use the same checks from sections 5b (staffing), 5c (refinement), and 5d (blocked/stalled). The REFINEMENT_BY_SME section is a reorganized view of these existing findings, not a separate analysis.
7. **Test plan spike gaps**: Include the test plan spike findings from section 7c (missing or not-closed) in each feature's description, naming the **QE Lead** (the Feature's `qa_contact`) as the owner — e.g. "No test plan spike yet — QE Lead Dana needs to create one that blocks this Feature." Omit when `test_plan_check_skipped` (QA Contact is `unassigned_jira`).
