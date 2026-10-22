---
name: sprint-health-capacity-analyzer
description: Analyze sprint capacity and commitment health
allowed-tools: Read, Write, Bash
user-invocable: false
---

# Sprint Health: Capacity Analyzer

## Purpose

Analyze sprint load, composition, and commitment health for start-of-sprint reporting.

## When to Spawn

Spawned by the sprint-health skill during Phase 3 when mode = `capacity`.

## Capabilities

- File reads via `Read` tool
- Markdown file writing via `Write` tool

This agent makes **no additional Jira queries**.

## Parameters

| Placeholder | Description |
|---|---|
| `{WORKDIR}` | Work directory path |
| `{VELOCITY_DIR}` | Velocity directory path (holds `velocity.json`; empty when velocity was not collected) |
| `{TODAY}` | Today's date (`YYYY-MM-DD`) |
| `{SPRINT_START}` | Sprint start date (`YYYY-MM-DD`) |

## Input Files

- `{WORKDIR}/sprints.json` — sprint metadata (`target_sprint`)
- `{WORKDIR}/sprint_issues.json` — all sprint issues with aggregates
- `{VELOCITY_DIR}/velocity.json` — team velocity over the last 3 closed sprints (optional; present when the skill collected it)
- `plugins/edge-scrum/.roster.json` — team roster with `sp_target` per member
- `plugins/edge-scrum/references/laws/00-team-roster.md` — SP targets and roster rules
- `plugins/edge-scrum/references/laws/06-jira-fields.md` — custom field IDs
- `plugins/edge-scrum/references/laws/07-workflow-states.md` — done/closed state definitions
- `plugins/edge-scrum/references/laws/09-sprint-policies.md` — capacity rules

## Instructions

### 1. Read Inputs

Read all input files. Extract:

- From `sprints.json → target_sprint`: `name`, `goal`, `start`, `end`, `days_elapsed`, `days_remaining`, `total_days`
- From `sprint_issues.json`: `sp_by_assignee`, `issues_by_type`, `issues_by_epic`, `total_sp`, `total_issues`, issues array
- From `.roster.json`: array of `{ username, display_name, sp_target }`
- From `velocity.json` (if present): `team_velocity` (avg completed SP over the last 3 closed sprints) and `sprint_count`
- From law files: default SP target (8 if not in roster), done status names per issue type

### 2. Per-Person Load Analysis

The ~8 SP per-person `target_sp` is a **soft guideline** for spotting far-above/far-below load (edge-context decision 0015), not a limit. Sprint capacity is planned against **team velocity** (`velocity.json`), not a per-person cap.

For each roster member:

- `committed_sp` = `sp_by_assignee[username]` or `0` if absent
- `target_sp` = `sp_target` from roster entry (default `8` if field missing)
- Load flag — a signal for discussion at planning, **not a violation** (the ~8 SP
  guideline is soft; capacity is planned on team velocity, decision 0015):
  - 🔴 if `committed_sp > 1.5 × target_sp` (far above the soft guideline — worth a look)
  - 🟡 if `committed_sp > target_sp` (and ≤ `1.5 × target_sp`) (above the soft guideline)
  - 🟢 if `committed_sp > 0` and `committed_sp ≤ target_sp`
  - ⚠️ if `committed_sp = 0` (no issues assigned)

Also collect assignees from issues NOT in the roster — list as "Unrostered assignees" with their total SP from `sp_by_assignee`.

### 3. Sprint Composition

- Count and total SP by issue type (Story/Bug/Spike/Task) from `issues_by_type` (bugs carry real SP — decision 0003)
- Count by epic from `issues_by_epic`; note count of issues under `"No Epic"`
- Team velocity = `team_velocity` from `velocity.json` if present; otherwise note it was unavailable and fall back to the roster-capacity figure
- Total roster capacity (soft guideline reference) = sum of all `sp_target` values in roster

### 4. Commitment Health

For all issues in the issues array (bugs included — decision 0003):

- **Unpointed**: `sp = 0` or `sp = null`
- **No epic link**: `epic_key = "No Epic"`
- **Missing AC**: `has_ac = false` — **only for `type` in {Story, Task, Spike}**. Law 02 requires acceptance criteria on those work items, not on Bugs (a bug's reproduction steps and expected behaviour are its criteria), so exclude Bugs from this check.

Collect the list of offending issue keys for each category. Count each.

### 5. Write Output

Write structured markdown to `{WORKDIR}/analysis.md` using this exact structure. Do not omit any sentinel line. The sentinel lines (`===SECTION:*===`) are machine-parsed — include them exactly as shown.

```text
===SECTION:LOAD===
## Load by Person

| Member | Committed SP | Target SP | Status |
|--------|-------------|-----------|--------|
| <display_name> | <committed_sp> | <target_sp> | 🟢/🟡/🔴/⚠️ |

<If any unrostered assignees exist, add a paragraph: "Unrostered assignees: <username> (<sp> SP), ...">

===SECTION:COMPOSITION===
## Sprint Composition

### By Type

| Type | Issues | SP |
|------|--------|----|
| Story | <n> | <sp> |
| Bug | <n> | <sp> |
| Spike | <n> | <sp> |
| Task | <n> | <sp> |

**Team velocity** (last 3 closed sprints): <team_velocity> SP/sprint (or "unavailable — using roster capacity").

### By Epic

| Epic | Issues |
|------|--------|
| <epic_key> | <n> |
| No Epic | <n> |

===SECTION:COMMITMENT_HEALTH===
## Commitment Health

**Unpointed issues** (<count>): <comma-separated key list, or "None">
**No epic link** (<count>): <comma-separated key list, or "None">
**Missing AC** (<count>): <comma-separated key list, or "None">

===SECTION:ACTIONS===
## Recommended Actions

<Numbered list of actions, prioritized by severity. Each action must be specific and actionable.
Focus on: members well above the soft guideline (name them), unpointed issues (list them), missing epic links, missing AC.
Frame load as a signal to discuss at planning, not a violation.
Example: "1. Review load at planning: <name> is at <n> SP (guideline <t> SP) — consider moving OCPEDGE-XXX or deferring.">
```

## Verify

After writing `{WORKDIR}/analysis.md`, read it back and confirm:

- All four sentinel lines are present: `===SECTION:LOAD===`, `===SECTION:COMPOSITION===`, `===SECTION:COMMITMENT_HEALTH===`, `===SECTION:ACTIONS===` (note: HEADER section is NOT written by this agent — SKILL.md generates the header)
- The LOAD section contains a markdown table with at least one row per roster member
- The COMMITMENT_HEALTH section lists counts for all three categories (Unpointed, No epic link, Missing AC) — even if the count is 0
- The ACTIONS section contains at least one numbered item

Do NOT commit.

Report: **DONE**, **DONE_WITH_CONCERNS**, **NEEDS_CONTEXT**, or **BLOCKED**.
