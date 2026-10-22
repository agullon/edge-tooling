---
name: release-health
description: Use when analyzing the health of an OCP release cycle — evaluates Features, Initiatives, Epics, and Tasks from Jira to assess progress, identify risks, surface refinement gaps, and recommend actions to keep the team on track toward branch cut
allowed-tools: Agent, AskUserQuestion, Write, Read, Glob, Bash, mcp__plugin_mcp-atlassian_mcp-atlassian__jira_get_sprints_from_board, mcp__plugin_mcp-atlassian_mcp-atlassian__jira_search
user-invocable: true
---

# Release Health Analysis

You are orchestrating a release health analysis for the OCPEDGE team. Data fetching runs inline using MCP tools and transform scripts. Analysis is delegated to a sub-agent.

> **Before proceeding**: Read `plugins/edge-scrum/references/Edge-Scrum-Laws.md` to find which law files apply to release health orchestration. For this skill, load: `laws/00-team-roster.md`, `laws/01-jira-projects.md`, `laws/05-jira-features.md`, `laws/06-jira-fields.md`, `laws/09-sprint-policies.md`, `laws/14-agent-conventions.md`. The configuration below is derived from the Laws — when in doubt, defer to the law files.

## Configuration

```yaml
# Scrum Board (skill-specific; not in Laws)
board_id: "11479"
board_name: "OpenShift Edge Scrum"
sprint_prefix: ["OCPEDGE Sprint", "OpenShift Edge Sprint"]

# Custom Field IDs (Red Hat Jira instance-specific)
fields:
  story_points:  customfield_10028   # Numeric; Stories/Tasks/Spikes/Bugs (decision 0003)
  parent:        parent              # Native issue → Epic link (Jira Cloud)
  epic_link:     customfield_10014   # Legacy fallback for the native Parent field
  parent_link:   customfield_10018   # Epic → Feature/Initiative relationship
  qa_contact:    customfield_10470   # User picker; QA owner
  flagged:       customfield_10021   # Array; non-empty = impediment
  docs_approver: customfield_10473   # User picker; Doc Contact
  sme:           customfield_10475   # User picker; Subject Matter Expert
```

## Execution Model

1. **Steps 0–1**: Load laws/roster, gather release parameters (main context)
2. **Phase 2**: Fetch sprints + features inline using MCP tools → transform scripts (main context)
3. **Phase 3**: Fetch epics + spikes inline using MCP tools → transform scripts (main context)
4. **Phase 4**: Delegate full analysis to sub-agent (LLM-driven risk assessment)
5. **Step 9**: Assemble and write the final report (main context)

**Rules:**

- Data fetching uses MCP tools directly in the main context
- MCP responses are large and get persisted to files automatically — note those file paths
- Transform scripts (`plugins/edge-scrum/bin/`) convert raw MCP data to structured JSON
- Use `check-page.py` to extract pagination info from persisted files
- The analysis sub-agent only needs `Read`, `Write`, and `jira_search` — it consumes the structured JSON
- Never embed raw Jira response data in the main context

## User Arguments

The user may provide arguments: `$ARGUMENTS`

- Version number (e.g., `4.19`, `5.0`) → release version
- Sprint range (e.g., `281-285`) → first through last sprint
- Branch cut (e.g., `bc:285` or `branch-cut 285`) → last sprint before feature freeze
- `--refinement` → refinement-only mode (see below)
- No arguments → ask for all inputs

### Refinement Mode (`--refinement`)

When the `--refinement` flag is present, the skill runs a narrower analysis focused on whether Features are fully refined to the story level:

1. **Scope**: Only Features/Initiatives in **Refinement** status are analyzed. Features already in Backlog, In Progress, or later states are excluded — they are past the refinement gate.
2. **Data collection**: Phases 2–3 run identically (sprints, features, epics, spikes are all fetched).
3. **Analysis**: Phase 4 spawns the analysis sub-agent with the `REFINEMENT_MODE` parameter set to `true`. The sub-agent runs all standard checks but adds a `REFINEMENT_BY_SME` output section that groups gaps by SME with natural language summaries.
4. **Report**: Step 9 uses a condensed refinement report instead of the full release-health template. It outputs the SME-grouped refinement view plus a summary. Sections irrelevant to refinement (Sprint Forecast, Schedule Risk) are excluded.

Set `REFINEMENT_MODE = true` when parsing arguments if `--refinement` is present; otherwise `REFINEMENT_MODE = false`.

---

## Workflow

### Step 0: Load Edge Scrum Laws and Roster (main context)

Read both files and hold in working memory:

1. Load these law files from `plugins/edge-scrum/references/laws/`:
   - `00-team-roster.md` — team capacity and `.roster.json` structure
   - `01-jira-projects.md` — **Jira projects and OCPBUGS components** — authoritative project keys and component names
   - `05-jira-features.md` — Feature/Initiative conventions and sizing
   - `06-jira-fields.md` — custom field IDs
   - `09-sprint-policies.md` — sprint capacity rules
   - `14-agent-conventions.md` — agent orchestration conventions

2. `plugins/edge-scrum/.roster.json` — extract:
   - **Team roster** — `username`, `display_name`, and `sp_target` per member
   - **Roster size** — count of members (used for capacity calculations)
   - If the file does not exist, stop and instruct the user to copy `.roster.json.example` to `.roster.json` and populate it.

The Laws are authoritative. Where this skill and the Laws conflict, the Laws win.

---

### Step 1: Gather Release Parameters (main context)

Parse arguments. Use `AskUserQuestion` for any missing values:

1. **Release version** — e.g., `4.19`, `5.0`
2. **Sprint range** — first sprint number through last
3. **Branch cut sprint** — which sprint is the last dev sprint

Compute and confirm:

- `FIRST` = first sprint number
- `LAST` = last sprint number (branch cut)
- `TOTAL_SPRINTS` = LAST − FIRST + 1
- `REFINEMENT_SPRINT_NUM` = FIRST (dedicated to spike creation, no delivery expected)
- `TOTAL_DEV_SPRINTS` = TOTAL_SPRINTS − 1
- `TODAY` = today's date (`YYYY-MM-DD`)

Create the work directory:

```bash
WORKDIR=/tmp/release-health-$(date +%Y%m%d) && mkdir -p $WORKDIR && echo $WORKDIR
```

Record `WORKDIR` — substitute it into all agent prompts.

---

### Phase 2: Sprint + Feature Collection (inline)

Fetch sprints and features in parallel using MCP tools, then transform with scripts.

#### 2a — Fetch Sprints

Call `jira_get_sprints_from_board` for board_id `"11479"` three times:

- `state="active"`
- `state="closed"` — paginate using `page_token` (see pagination protocol below); use `limit=50`
- `state="future"`

After all pages are fetched, note all persisted file paths and run:

```bash
python3 plugins/edge-scrum/bin/transform-sprints.py \
  --input <all_persisted_file_paths> \
  --output {WORKDIR}/sprints.json \
  --today {TODAY} \
  --first-sprint {FIRST} \
  --last-sprint {LAST} \
  --total-dev-sprints {TOTAL_DEV_SPRINTS}
```

#### 2b — Fetch Features

Call `jira_search` with:

- **JQL (standard mode):** `project = OCPSTRAT AND issuetype in (Feature, Initiative) AND labels in ("ocpedge-plan", "microshift") AND "Target Version" = "openshift-{VERSION}" AND (resolution is EMPTY OR resolution not in (Duplicate, Obsolete)) ORDER BY Rank ASC`
- **JQL (refinement mode):** `project = OCPSTRAT AND issuetype in (Feature, Initiative) AND labels in ("ocpedge-plan", "microshift") AND "Target Version" = "openshift-{VERSION}" AND status = "Refinement" AND (resolution is EMPTY OR resolution not in (Duplicate, Obsolete)) ORDER BY Rank ASC`
- **Fields:** `key, summary, status, issuetype, priority, assignee, fixVersions, labels, description, issuelinks, customfield_10795, customfield_10470, customfield_10473, customfield_10475`
- **limit:** `50`

Use the refinement-mode JQL when `REFINEMENT_MODE = true`.

Paginate using `page_token`. If zero results, use fallback JQL (set `fallback_used`):

```jql
project = OCPSTRAT AND issuetype in (Feature, Initiative) AND labels in ("ocpedge-plan", "microshift") AND "Target Version" = "openshift-{VERSION}" AND status not in (Done, Closed, "Release Pending") ORDER BY Rank ASC
```

After all pages fetched, run:

```bash
python3 plugins/edge-scrum/bin/transform-features.py \
  --input <all_persisted_file_paths> \
  --output {WORKDIR}/features.json
```

Append `--fallback-used` if fallback JQL was used.

#### 2c — Verify

Read and check:

- `{WORKDIR}/sprints.json` — if `"error"` key is present or `sprint_map` is empty, warn the user and stop
- `{WORKDIR}/features.json` — if `feature_keys` is empty:
  - **Refinement mode**: Report "All features have progressed past Refinement — nothing to check." and exit cleanly (skip Phases 3–4 and Step 9).
  - **Standard mode**: Warn the user about scope and stop

---

### Phase 3: Epic + Spike Collection (inline)

#### 3a — Fetch Epics

Read `{WORKDIR}/features.json`. Extract `feature_keys_csv`.

If `feature_keys` has more than 50 entries, split into batches of 50. For each batch, call `jira_search`:

- **JQL:** `project in (OCPEDGE, USHIFT) AND "Parent Link" in ({feature_keys_batch_csv}) ORDER BY Rank ASC`
- **Fields:** `key, summary, status, assignee, labels, description, parent, customfield_10028, customfield_10018, customfield_10470, customfield_10473, customfield_10475`
- **limit:** `50`

Paginate using `page_token`. After all pages fetched, run:

```bash
python3 plugins/edge-scrum/bin/transform-epics.py \
  --input <all_persisted_file_paths> \
  --output {WORKDIR}/epics.json
```

#### 3b — Fetch Spikes

Read `{WORKDIR}/sprints.json`. Extract `refinement_sprint_id`.

Call `jira_search`:

- **JQL:** `project in (OCPEDGE, USHIFT) AND issuetype = Spike AND sprint = {refinement_sprint_id}`
- **Fields:** `key, summary, status, assignee, resolution, issuelinks`
- **limit:** `50`

Paginate using `page_token`; note the persisted refinement-sprint spike file paths.

**Linked spikes (reachable only via a feature's issuelinks).** A feature may be blocked by a
spike that is *not* in the refinement sprint; `transform-features.py` records these as
`spike_candidates`, but the issuelink payload usually lacks the spike's assignee/status/resolution,
so the test-plan vs refinement classification can't be made from it alone. Collect every
`spike_candidates[].key` across `{WORKDIR}/features.json` that is **not** already among the
refinement-sprint spikes just fetched. If any remain, fetch them by key with `jira_search`
(batch in groups of 50):

- **JQL:** `key in ({linked_spike_keys_csv})`
- **Fields:** `key, summary, status, assignee, resolution, issuelinks`
- **limit:** `50`

Paginate using `page_token`; note the persisted linked-spike file paths. If there are none, skip
this fetch and omit `--linked-spikes` below. Then run:

```bash
python3 plugins/edge-scrum/bin/transform-spikes.py \
  --input <refinement_sprint_spike_file_paths> \
  --linked-spikes <linked_spike_file_paths> \
  --features-file {WORKDIR}/features.json \
  --epics-file {WORKDIR}/epics.json \
  --sprints-file {WORKDIR}/sprints.json \
  --output {WORKDIR}/spikes.json
```

#### 3c — Verify

Read `{WORKDIR}/epics.json` and verify: `epic_keys` is a non-empty array, `feature_to_epics` is an object, and `epics` is an array. If any check fails, warn the user with a descriptive error and stop.

#### 3d — Team Velocity (optional)

Capacity is planned against the team's measured velocity — the average completed SP over the last 3 closed sprints (edge-context decision 0015) — not the roster's `sp_target` sum. This is the same velocity step as release-planning. If it is impractical or returns nothing, **skip it**: the analyzer falls back to the roster sum (`Σ sp_target × remaining sprints`) and labels the capacity line as a fallback.

Write this run's velocity files to a fresh, uniquely named directory created with `mktemp -d`. Because the directory is new each run (a random suffix, no predictable path), there are no stale files for a glob to pick up and nothing to delete:

```bash
VELOCITY_DIR=$(mktemp -d "{WORKDIR}/velocity.XXXXXX") && echo "$VELOCITY_DIR"
```

Record `VELOCITY_DIR` and substitute it for `{VELOCITY_DIR}` below. It sits inside `{WORKDIR}`, so the end-of-run cleanup removes it with the rest of the run directory.

1. Build a full (unfiltered) closed-sprint map. Phase 2a's `sprints.json` was transformed **with** `--first-sprint`/`--last-sprint`, so its `sprint_map` holds only the release-window sprints — the recent closed sprints velocity needs sit *before* `FIRST` and are not in it. Re-run `transform-sprints.py` on the **same** `state="closed"` raw pages already persisted in Phase 2a, this time with **no** `--first-sprint`/`--last-sprint` (so `sprint_map` holds every closed sprint) and `--today {TODAY}`, writing `{WORKDIR}/closed_sprints.json`:

   ```bash
   python3 plugins/edge-scrum/bin/transform-sprints.py \
     --input <closed_sprint_raw_file_paths_from_phase_2a> \
     --output {WORKDIR}/closed_sprints.json \
     --today {TODAY}
   ```

   From that `sprint_map`, pick the three `closed` sprints with the highest `num` (the three most recently closed sprints — do **not** filter by `< FIRST`; an early sprint of the current release that has already closed is a valid velocity input). Record each one's `id`, `num`, and (if available) `start`/`end` (the sprint_map date keys). Collect the exact file path you write for each sprint in step 2 into a list `{VELOCITY_FILES}`.
2. For each of those sprint IDs, call `jira_search`:
   - **JQL:** `project in (OCPEDGE, USHIFT, OCPBUGS) AND sprint = {SPRINT_ID}`
   - **Fields:** `key, summary, status, issuetype, assignee, resolutiondate, customfield_10028, customfield_10470, customfield_10020`
   - **limit:** `50`, paginate with `page_token`.

   Write the sprint metadata to a file with the `Write` tool (never interpolate the Jira sprint name into a shell command — it is attacker-influenced text):

   `{VELOCITY_DIR}/velocity_s{NUM}.meta.json` =
   `{"sprint_id": {SPRINT_ID}, "sprint_name": <SPRINT_NAME as a JSON-escaped string>, "sprint_start": <"YYYY-MM-DD" or null>, "sprint_end": <"YYYY-MM-DD" or null>}`

   JSON-encode `SPRINT_NAME` (a name containing `"` or `\` breaks the file otherwise) and use the bare JSON literal `null` for a missing date, never the string `"null"` (which `compute-velocity.py` would treat as a real date). Read the metadata file back and confirm it parses as JSON before running the transform; if it does not, skip this sprint's velocity contribution.

   Then run (pass the metadata file, not `--sprint-name`):

   ```bash
   python3 plugins/edge-scrum/bin/transform-sprint-issues.py \
     --input <all_persisted_file_paths> \
     --output {VELOCITY_DIR}/velocity_s{NUM}.json \
     --sprint-meta {VELOCITY_DIR}/velocity_s{NUM}.meta.json \
     --today {TODAY}
   ```

3. Compute velocity from the (up to) three sprint files. Pass the **exact** files you wrote in `{VELOCITY_FILES}` (space-separated, each under `{VELOCITY_DIR}`), never a `velocity_s*.json` glob:

   ```bash
   python3 plugins/edge-scrum/bin/compute-velocity.py \
     --sprint-issues {VELOCITY_FILES} \
     --roster plugins/edge-scrum/.roster.json \
     --output {VELOCITY_DIR}/velocity.json
   ```

   Velocity counts completed SP of **team-owned** issues (assignee or QA Contact on the roster, per law 00); bugs count like other work (decision 0003). A done issue is credited only to the sprint it finished in — the sprint with the latest end date among the sprints it belonged to (falling back to the highest sprint id, then its resolution date, when end dates are missing; Jira does not return the list in reliable order) — so an issue carried across sprints is not double-counted.

#### 3e — Team availability (optional, PTO/holidays)

Law 09 plans capacity against velocity "adjusted for PTO and holidays". This is the same optional input as release-planning. Ask the user (via `AskUserQuestion`) whether any known PTO or company holidays fall in the remaining sprints. If they give you people-days away, convert to a per-sprint availability fraction for each remaining sprint: `availability_i = 1 − (people-days away in sprint i ÷ (roster size × working days in sprint i))`, clamped to `[0, 1]`. Record the resulting CSV as `{AVAILABILITY}` (one fraction per remaining sprint).

If the run is non-interactive, or the user skips or has nothing to report, leave `{AVAILABILITY}` **empty**. When it is empty the analysis uses the full `remaining_sprint_count` and the report must state the capacity is **not adjusted for PTO**.

---

### Pagination Protocol

This Jira instance uses `page_token` pagination, NOT `start_at`. Follow this protocol for all paginated MCP calls:

1. Make the first call without `page_token`
2. The response may be persisted to a file. Note the file path.
3. Run `check-page.py` to get pagination info:

   ```bash
   python3 plugins/edge-scrum/bin/check-page.py <persisted_file_path>
   ```

   Output: `{"issues_count": N, "has_more": bool, "next_page_token": "..."}`
4. If `has_more` is `true`: make the next call with `page_token` set to the `next_page_token` value. Repeat from step 2.
5. If `has_more` is `false`: pagination is complete.

For small responses that fit in context (not persisted), write them to `{WORKDIR}/raw_<type>_<page>.json` using `Write`, then run `check-page.py` on that file.

For `jira_get_sprints_from_board`: closed sprints may require multiple pages. Active and future typically fit in one page each.

---

### Phase 4: Full Analysis (sub-agent)

Read `plugins/edge-scrum/skills/release-health-analysis/SKILL.md`. Substitute `{WORKDIR}`, `{VELOCITY_DIR}` (from step 3d, or empty if that step was skipped — the analyzer then uses the roster fallback), `{VERSION}`, `{TODAY}`, `{REFINEMENT_SPRINT_NUM}`, `{REFINEMENT_MODE}`, `{AVAILABILITY}` (the CSV from step 3e, or empty if not given), then spawn as a sub-agent:

- **Agent 4** — prompt: analysis content with all placeholders substituted

This agent reads all four data files, detects misplaced spikes, fetches child issues, builds the hierarchy, assesses all risks, and writes `{WORKDIR}/analysis.md`.

---

### Step 9: Generate Report (main context)

#### Standard mode (`REFINEMENT_MODE = false`)

1. Read the report template from `plugins/edge-scrum/references/release-health-report-template.md`
2. Read `{WORKDIR}/analysis.md`
3. Parse the `===ANALYSIS_META===` block for header values
4. Substitute all `{placeholder}` values in the template:
   - Header fields from release parameters and ANALYSIS_META
   - `{executive_summary}`: Write 3-5 sentences using `top_risks`, `overall_health`, feature counts, and `sprint_recommendation` from ANALYSIS_META. Cover: overall verdict, count on track vs. at risk, top 2-3 risks, one recommended priority this sprint.
   - `{DASHBOARD}`, `{FEATURE_DETAIL}`, `{EPIC_DETAIL}`, `{RISK_REGISTER}`, `{REFINEMENT_BACKLOG}`, `{SPRINT_FORECAST}`, `{ACTIONS}`: paste the corresponding `===SECTION:*===` block content from analysis.md, stripping the sentinel lines
5. Add Jira links: replace all bare issue keys (OCPSTRAT-*, OCPEDGE-*, USHIFT-*, OCPBUGS-*) with `[KEY](https://redhat.atlassian.net/browse/KEY)` markdown links, skipping keys already inside link syntax
6. Write to `.reports/release_health_{VERSION}_{TODAY}.md`
7. Clean up: `test -n "{WORKDIR}" && [[ "{WORKDIR}" == /tmp/release-health-* ]] && rm -rf -- "{WORKDIR}"`

#### Refinement mode (`REFINEMENT_MODE = true`)

1. Read `{WORKDIR}/analysis.md`
2. Parse the `===ANALYSIS_META===` block for header values
3. Extract the `===SECTION:REFINEMENT_BY_SME===` block from analysis.md. If the section is not found, halt with an error: "Analysis phase did not produce the REFINEMENT_BY_SME section — check sub-agent output."
4. Extract the `===SECTION:REFINEMENT_BACKLOG===` block from analysis.md
5. Build the refinement report using the template from `plugins/edge-scrum/references/refinement-report-template.md`
6. Substitute placeholders in the template:
   - `{VERSION}`, `{TODAY}`, `{REFINEMENT_SPRINT_NUM}` — from release parameters
   - `{refinement_state}` — derive from `sprints.json`: `"Closed"` if `refinement_sprint_closed = true`, otherwise `"Open"`
   - `{total_features}` — from ANALYSIS_META `total_features`
   - `{refined_count}` — from ANALYSIS_META `refined_count`
   - `{needs_attention_count}` — from ANALYSIS_META `needs_attention_count`
   - `{REFINEMENT_BY_SME}` — paste the extracted section content, stripping sentinel lines
   - `{REFINEMENT_BACKLOG}` — paste the extracted section content, stripping sentinel lines
7. Add Jira links (same rule as standard mode)
8. Write to `.reports/refinement_{VERSION}_{TODAY}.md`
9. Clean up: `test -n "{WORKDIR}" && [[ "{WORKDIR}" == /tmp/release-health-* ]] && rm -rf -- "{WORKDIR}"`

---

## Edge Cases

- **No Features found**: Try fallback JQL (handled in Phase 2b); warn user to confirm scope; stop if still empty. In refinement mode, an empty result means all features have progressed past Refinement — handled in Phase 2c.
- **Feature with no Epics**: Flag as "Unplanned"; epic fetch returns empty list for that feature.
- **Epic with no Stories**: Flag as "Empty" in analysis.
- **Version format varies** (`4.19` vs `4.19.0`): Analysis agent tries both in fixVersion queries.
- **SME / Docs field errors**: Transform scripts handle gracefully with fallback values.
- **Sprint resolution failure**: transform-sprints.py sets `"error"` in JSON; main context stops before Phase 3.
- **Multiple spikes per Feature**: transform-spikes.py records all in `spike_keys[]`; analysis agent uses worst-case status.
- **OCPBUGS without Epics**: Grouped under "(Unlinked Bugs)" section by analysis agent.
- **Analysis during refinement sprint**: Analysis agent skips 7a entirely — no delivery progress expected.
- **Spike linked to child Epic**: Detected by analysis agent via `all_ref_sprint_spikes` cross-reference with `epics.json`.

---

## Important Notes

- **Read-only**: This skill does not modify any Jira data.
- **Transform scripts**: `plugins/edge-scrum/bin/` — reusable data transformation (no LLM needed)
- **Analysis sub-agent**: `plugins/edge-scrum/skills/release-health-analysis/SKILL.md` — LLM-driven risk assessment and report generation
- **Work directory**: `{WORKDIR}` persists across phases within a run. Rerunning on the same day overwrites prior files.
- **Laws files**: The analysis sub-agent reads specific files from `plugins/edge-scrum/references/laws/` per the index at `plugins/edge-scrum/references/Edge-Scrum-Laws.md` — never hardcode roster, rules, or sizing in skill definitions.
