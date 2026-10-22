---
name: release-planning
description: Use when assessing whether the team can deliver planned scope within remaining time — evaluates capacity, timeline, assignment, bug load, sizing, and progress risks per person and per feature to surface planning risks before they become execution problems
allowed-tools: Agent, AskUserQuestion, Write, Read, Glob, Bash, mcp__plugin_mcp-atlassian_mcp-atlassian__jira_get_sprints_from_board, mcp__plugin_mcp-atlassian_mcp-atlassian__jira_search
user-invocable: true
argument-hint: "<version> <sprint-range> bc:<branch-cut> [pd:<pencils-down>] [--component <component>]"
---

# Release Planning Risk Assessment

You are orchestrating a release planning risk assessment for the OCPEDGE team. Data fetching runs inline using MCP tools and transform scripts. Checks are deterministic (`run-checks.py`); only the narrative is delegated to a sub-agent.

The report is decision-oriented: verdict → decisions → cut line → people far above the soft guideline → dormant scope → process gaps → how the numbers were computed → appendix. Every figure is computed in `run-checks.py` and its formula is recorded in `checks.json` (`method` block) so the report can show how each conclusion was reached. The full method is in `plugins/edge-scrum/references/release-planning-method.md`.

**Scope handling (new):** features in `New` status with no evidence of work (no epics, no stories, or no story in progress / done / in a release sprint / updated in the last 30 days) are classified **dormant** and pulled out of the risk math — they are a scope decision for PM, not a risk. Epics that are already done (`Dev Complete`/`Testing`/`Release Pending`/`Closed`, per law 07) or that target another release are excluded from scope and listed in the report. Capacity counts every roster member; assignees missing from the roster are flagged as roster drift.

> **Before proceeding**: Read `plugins/edge-scrum/references/Edge-Scrum-Laws.md` to find which law files apply to release planning orchestration. For this skill, load: `laws/00-team-roster.md`, `laws/01-jira-projects.md`, `laws/03-jira-bugs.md`, `laws/04-jira-epics.md`, `laws/05-jira-features.md`, `laws/06-jira-fields.md`, `laws/09-sprint-policies.md`, `laws/14-agent-conventions.md`. The configuration below is derived from the Laws — when in doubt, defer to the law files.

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
  sme:           customfield_10475   # User picker; Subject Matter Expert

# Component mapping (short name → OCPBUGS components)
components:
  TNA: "Two Node with Arbiter"
  TNF: "Two Node Fencing"
  LVMS: "Logical Volume Manager Storage"
  topolvm: "Logical Volume Manager Storage"
  MicroShift:
    - "MicroShift"
    - "MicroShift / Networking"
    - "MicroShift / Storage"
  SNO: "Installer / Single Node OpenShift"
```

## Execution Model

1. **Steps 0–1**: Load laws/roster, gather release parameters (main context)
2. **Phase 2**: Fetch sprints + features inline using MCP tools → transform scripts (main context)
3. **Phase 3**: Fetch epics inline using MCP tools → transform scripts (main context)
4. **Phase 4**: Fetch stories + bugs inline using MCP tools → transform scripts (main context)
5. **Phase 5a**: Run `run-checks.py` — deterministic data-quality gate + 6 checks → `checks.json`
6. **Phase 5b**: Delegate narrative to sub-agent — reads `checks.json`, writes `recommendations.json`
7. **Step 6**: Run `assemble-report.py` — produces `.md` from structured data

**Rules:**

- Data fetching uses MCP tools directly in the main context. Requires the standard `mcp-atlassian` plugin MCP server; if its tools are unavailable, stop and tell the user to enable it
- MCP responses are large and get persisted to files automatically — note those file paths
- Transform scripts (`plugins/edge-scrum/bin/`) convert raw MCP data to structured JSON
- Use `check-page.py` to extract pagination info from persisted files
- The analysis sub-agent only needs `Read` and `Write` — it reads `checks.json` and writes `recommendations.json`
- Never embed raw Jira response data in the main context

## User Arguments

The user may provide arguments: `$ARGUMENTS`

- Version number (e.g., `5.0`) → release version
- Sprint range (e.g., `287-292`) → first through last sprint
- Branch cut (e.g., `bc:292` or `branch-cut 292`) → last sprint; the release branch is created after this sprint
- Pencils down (e.g., `pd:291` or `pencils-down 291`) → last sprint where feature code must be merged. If not provided, defaults to same as branch cut
- `--component <name>` → filter to a specific component (TNA, TNF, LVMS, topolvm, MicroShift, SNO)
- No arguments → ask for all required inputs

**Branch cut vs pencils down:** Pencils down is when all feature work must be code-complete. Branch cut is when the release branch is actually created. Feature timeline risk is measured against pencils down (the earlier deadline). Bug fixes can still land between pencils down and branch cut.

---

## Usage Examples

```shell
/release-planning 5.0 287-292 bc:292
/release-planning 5.0 287-292 bc:292 pd:291
/release-planning 5.0 287-292 bc:292 --component TNA
/release-planning
```

## Workflow

### Step 0: Load Edge Scrum Laws and Roster (main context)

Read both files and hold in working memory:

1. Load these law files from `plugins/edge-scrum/references/laws/`:
   - `00-team-roster.md` — team capacity and `.roster.json` structure
   - `01-jira-projects.md` — Jira projects and OCPBUGS components
   - `03-jira-bugs.md` — bug conventions
   - `04-jira-epics.md` — epic conventions and sizing
   - `05-jira-features.md` — feature/initiative conventions and sizing
   - `06-jira-fields.md` — custom field IDs
   - `09-sprint-policies.md` — sprint capacity rules
   - `14-agent-conventions.md` — agent orchestration conventions

2. `plugins/edge-scrum/.roster.json` — extract:
   - **Team roster** — `username`, `display_name`, and `sp_target` per member
   - **Roster size** — count of members
   - If the file does not exist, stop and instruct the user to copy `.roster.json.example` to `.roster.json` and populate it.

The Laws are authoritative. Where this skill and the Laws conflict, the Laws win.

---

### Step 1: Gather Release Parameters (main context)

Parse arguments. Use `AskUserQuestion` for any missing required values:

1. **Release version** — e.g., `5.0`
2. **Sprint range** — first sprint number through last
3. **Branch cut sprint** — which sprint is the last sprint before the release branch is created
4. **Pencils down sprint** — optional; which sprint is the last sprint where feature code must be merged. Defaults to branch cut if not provided
5. **Component filter** — optional, from `--component` argument

Compute and confirm:

- `FIRST` = first sprint number
- `LAST` = last sprint number (branch cut)
- `PENCILS_DOWN` = pencils down sprint number (defaults to `LAST` if not provided)
- `TOTAL_SPRINTS` = LAST − FIRST + 1
- `TOTAL_DEV_SPRINTS` = PENCILS_DOWN − FIRST (sprints available for feature work, excluding refinement sprint)
- `REMAINING_SPRINT_COUNT` = number of remaining sprints until pencils down (not branch cut). After reading `sprints.json`, count how many active + future sprints have sprint numbers ≤ `PENCILS_DOWN`. If pencils down equals branch cut, use `remaining_sprint_count` from `sprints.json` directly.
- `TODAY` = today's date (`YYYY-MM-DD`)
- `COMPONENT_FILTER` = mapped component name from the components table, or `none`

Note: Both `TOTAL_DEV_SPRINTS` and `REMAINING_SPRINT_COUNT` are computed against pencils down, not branch cut. Feature timeline risk is measured against this deadline. The sprints between pencils down and branch cut are available for bug fixes only.

Create the work directory:

```bash
WORKDIR=/tmp/release-planning-$(date +%Y%m%d) && mkdir -p $WORKDIR && echo $WORKDIR
```

Record `WORKDIR` — substitute it into all agent prompts.

---

### Phase 2: Sprint + Feature Collection (inline)

Like release-health Phase 2 (standard mode JQL only), except planning skips the
closed-sprint fetch — see 2a.

#### 2a — Fetch Sprints

Call `jira_get_sprints_from_board` for board_id `"11479"` twice:

- `state="active"`
- `state="future"`

Do **not** fetch `state="closed"` here. `run-checks.py` takes `--remaining-sprints` as a
number, and every sprint-derived figure in this phase (`remaining_sprint_count`, the
active/dormant release-window check) is computed from active + future sprints or from sprint
numbers on the stories themselves. The board returns closed sprints oldest-first across the
full history (hundreds of sprints, many pages), so pulling them all into this phase costs a
large amount of context. The velocity computation **does** need the most recent closed
sprints, so it fetches them on its own in Phase 4d (`closed_sprints.json`) rather than here.

After both calls, note all persisted file paths and run:

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

- **JQL:** `project = OCPSTRAT AND issuetype in (Feature, Initiative) AND labels in ("ocpedge-plan", "microshift") AND "Target Version" = "openshift-{VERSION}" AND (resolution is EMPTY OR resolution not in (Duplicate, Obsolete)) ORDER BY Rank ASC`
- **Fields:** `key, summary, status, issuetype, priority, assignee, fixVersions, labels, description, issuelinks, customfield_10795, customfield_10855, customfield_10470, customfield_10473, customfield_10475`
- **limit:** `50`

Keep the pages in fetch order: the JQL sorts by Rank and `transform-features.py` persists the position as `rank`, which the report's cut line relies on.

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
- `{WORKDIR}/features.json` — if `feature_keys` is empty, warn the user about scope and stop

---

### Phase 3: Epic Collection (inline)

Like release-health Phase 3, except planning does not fetch spikes — they feed only the
release-health refinement checks, not the planning report.

#### 3a — Fetch Epics

Read `{WORKDIR}/features.json`. Extract `feature_keys_csv`.

If `feature_keys` has more than 50 entries, split into batches of 50. For each batch, call `jira_search`:

- **JQL:** `project in (OCPEDGE, USHIFT) AND "Parent Link" in ({feature_keys_batch_csv}) ORDER BY Rank ASC`
- **Fields:** `key, summary, status, assignee, labels, description, parent, updated, fixVersions, customfield_10028, customfield_10795, customfield_10855, customfield_10018, customfield_10470, customfield_10473, customfield_10475`
- **limit:** `50`

`customfield_10795` is the epic's T-shirt size (law 04); `customfield_10855` (Target Version) and `fixVersions` let `run-checks.py` exclude epics that belong to another release.

Paginate using `page_token`. After all pages fetched, run:

```bash
python3 plugins/edge-scrum/bin/transform-epics.py \
  --input <all_persisted_file_paths> \
  --output {WORKDIR}/epics.json
```

#### 3b — Verify

Read `{WORKDIR}/epics.json` and verify: `epic_keys` is a non-empty array, `feature_to_epics` is an object, and `epics` is an array. If any check fails, warn the user with a descriptive error and stop.

---

### Phase 4: Story + Bug Collection (inline)

This is the new data collection phase. It fetches story-level data needed for capacity, assignment, and bug load checks.

#### 4a — Fetch Stories Under Epics

Read `{WORKDIR}/epics.json`. Extract `epic_keys`.

Split epic keys into batches of 20. For each batch, call `jira_search`:

- **JQL:** `project in (OCPEDGE, USHIFT, OCPBUGS) AND parent in ({epic_keys_batch_csv}) ORDER BY priority ASC`
- **Fields:** `key, summary, status, issuetype, priority, assignee, labels, updated, parent, customfield_10028, customfield_10021, customfield_10020, issuelinks`
- **limit:** `50`

`customfield_10020` is the Sprint field; together with `updated` it is the evidence used to tell an active `New` feature from a dormant one.

Paginate using `page_token`. After all pages fetched, note all persisted file paths and run:

```bash
python3 plugins/edge-scrum/bin/transform-stories.py \
  --input <all_persisted_file_paths> \
  --output {WORKDIR}/stories.json \
  --today {TODAY}
```

#### 4b — Fetch Unlinked Bugs

Call `jira_search` with:

- **JQL:** `project = OCPBUGS AND component in ("Installer / Single Node OpenShift", "Two Node with Arbiter", "Two Node Fencing", "Logical Volume Manager Storage", "MicroShift", "MicroShift / Networking", "MicroShift / Storage") AND fixVersion in ("{VERSION}", "{VERSION}.0") AND "Epic Link" is EMPTY ORDER BY priority ASC`
- **Fields:** `key, summary, status, priority, assignee, components, labels, updated`
- **limit:** `50`

Paginate using `page_token`. After all pages fetched, run:

```bash
python3 plugins/edge-scrum/bin/transform-bugs.py \
  --input <all_persisted_file_paths> \
  --output {WORKDIR}/bugs.json \
  --today {TODAY}
```

#### 4c — Verify

Read `{WORKDIR}/stories.json` and `{WORKDIR}/bugs.json`. Verify they parse correctly and contain expected top-level keys (`total_stories`, `stories`, `total_bugs`, `bugs`). An empty stories or bugs list is valid (not an error).

#### 4d — Team Velocity (optional)

Capacity is planned against the team's measured velocity — the average completed SP over the last 3 closed sprints (edge-context decision 0015). This is the **one** planning consumer of closed-sprint data; fetch only the three most recent closed sprints, and if that is impractical or returns nothing, **skip this step** — `run-checks.py` falls back to the roster sum (`Σ sp_target × sprints left`) and the report states that the fallback was used.

Write this run's velocity files to a fresh, uniquely named directory created with `mktemp -d`. Because the directory is new each run (a random suffix, no predictable path), there are no stale files for a glob to pick up and nothing to delete:

```bash
VELOCITY_DIR=$(mktemp -d "{WORKDIR}/velocity.XXXXXX") && echo "$VELOCITY_DIR"
```

Record `VELOCITY_DIR` and substitute it for `{VELOCITY_DIR}` below. It sits inside `{WORKDIR}`, so the end-of-run cleanup removes it with the rest of the run directory.

1. Call `jira_get_sprints_from_board` for board_id `"11479"` with `state="closed"`, paginating (see pagination protocol). Transform with `transform-sprints.py` (no `--first-sprint`/`--last-sprint`, so `sprint_map` holds every sprint with its `id`, `num`, and `state`), writing `{WORKDIR}/closed_sprints.json`.
2. From that `sprint_map`, pick the three `closed` sprints with the highest `num` (the three most recently closed sprints — all closed sprints precede the planning window, so no `< FIRST` filter is needed). Record their `id`, `num`, and (if available) `start`/`end` (the sprint_map date keys). Collect the exact file path you write for each sprint in step 3 into a list `{VELOCITY_FILES}`.
3. For each of those sprint IDs, call `jira_search`:
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

4. Compute velocity from the (up to) three sprint files. Pass the **exact** files you wrote in `{VELOCITY_FILES}` (space-separated, each under `{VELOCITY_DIR}`), never a `velocity_s*.json` glob:

   ```bash
   python3 plugins/edge-scrum/bin/compute-velocity.py \
     --sprint-issues {VELOCITY_FILES} \
     --roster plugins/edge-scrum/.roster.json \
     --output {VELOCITY_DIR}/velocity.json
   ```

   Velocity counts completed SP of **team-owned** issues (assignee or QA Contact on the roster, per law 00); bugs count like other work (decision 0003). A done issue is credited only to the sprint it finished in — the sprint with the latest end date among the sprints it belonged to (falling back to the highest sprint id, then its resolution date, when end dates are missing; Jira does not return the list in reliable order) — so an issue carried across sprints is not double-counted.

#### 4e — Team availability (optional, PTO/holidays)

Law 09 plans against velocity "adjusted for PTO and holidays". Ask the user (via `AskUserQuestion`) whether any known PTO or company holidays fall in the remaining sprints. If they give you people-days away, convert to a per-sprint availability fraction for each remaining sprint: `availability_i = 1 − (people-days away in sprint i ÷ (roster size × working days in sprint i))`, clamped to `[0, 1]`. Record the resulting CSV as `{AVAILABILITY}` (one fraction per remaining sprint) and pass it to `run-checks.py` via `--availability`. If the user skips or has nothing to report, omit `--availability`; capacity is then not adjusted for PTO and the report says so.

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

---

### Phase 5a: Run Checks (deterministic)

Run the planning risk checks script. This classifies features active/dormant, filters scope, performs the data-quality gate, all checks, the cut line and the hidden-scope estimate deterministically — no LLM needed:

```bash
python3 plugins/edge-scrum/bin/run-checks.py \
  --features {WORKDIR}/features.json \
  --epics {WORKDIR}/epics.json \
  --stories {WORKDIR}/stories.json \
  --bugs {WORKDIR}/bugs.json \
  --roster plugins/edge-scrum/.roster.json \
  --remaining-sprints {REMAINING_SPRINT_COUNT} \
  --velocity-file {VELOCITY_DIR}/velocity.json \
  --availability {AVAILABILITY} \
  --component-filter "{COMPONENT_FILTER}" \
  --version {VERSION} \
  --today {TODAY} \
  --first-sprint {FIRST} \
  --pencils-down {PENCILS_DOWN} \
  --focus-priorities Blocker,Critical,Major \
  --include-lower-when Refinement \
  --output {WORKDIR}/checks.json
```

Include `--velocity-file` only if `{VELOCITY_DIR}/velocity.json` exists (Phase 4d ran and produced it). If Phase 4d was skipped, omit the flag; capacity then falls back to `Σ sp_target × sprints left` and `method.capacity` says so. (`run-checks.py` also tolerates a missing `--velocity-file` path, logging a warning and using the roster fallback, but prefer to omit the flag when there is no file.) Include `--availability` only if Phase 4e produced a value; otherwise omit it and capacity is not adjusted for PTO.

Lower-priority features are excluded from all figures and listed in the appendix; adjust the two flags to widen or narrow focus.

Verify `{WORKDIR}/checks.json` was written and contains `meta` and `method` keys.

**Roster drift check.** Read `checks.json` → `process_gaps.roster_drift`. If it is non-empty, tell the user which assignees carry work but are not in `.roster.json`, with their SP, and ask (via `AskUserQuestion`) whether to add them to the roster and re-run, or continue with them counted as scope but not capacity. Do not silently continue: every capacity figure depends on this.

### Phase 5b: Recommendations (sub-agent)

Read `plugins/edge-scrum/skills/release-planning-analysis/SKILL.md`. Substitute `{WORKDIR}` and `{VERSION}`, then spawn as a sub-agent.

This agent reads `checks.json` (pre-computed numbers) and writes `{WORKDIR}/recommendations.json` with a headline, up to five decisions, and narrative. It does NOT compute any numbers — only interprets and advises.

Verify `{WORKDIR}/recommendations.json` was written and contains `headline` and `decisions`.

---

### Step 6: Assemble Report (main context)

Run the report assembly script. This renders Markdown from structured data — no markdown parsing needed:

```bash
python3 plugins/edge-scrum/bin/assemble-report.py \
  --checks {WORKDIR}/checks.json \
  --recommendations {WORKDIR}/recommendations.json \
  --template plugins/edge-scrum/references/release-planning-report-template.md \
  --version {VERSION} \
  --today {TODAY} \
  --first-sprint {FIRST} \
  --last-sprint {LAST} \
  --pencils-down {PENCILS_DOWN} \
  --remaining-sprints {REMAINING_SPRINT_COUNT} \
  --total-dev-sprints {TOTAL_DEV_SPRINTS} \
  --strict \
  --output .reports/release_planning_{VERSION}_{TODAY}
```

This produces `.reports/release_planning_{VERSION}_{TODAY}.md`. Rendering for other channels (chai-bot, browser, Word) is handled downstream from the Markdown.

`--strict` makes assembly fail if `recommendations.json` breaks the writing rules (pre-built links, gendered pronouns, unknown feature keys, more than five decisions). If it fails, re-spawn the analysis agent with the reported problems and assemble again.

Clean up: `test -n "{WORKDIR}" && [[ "{WORKDIR}" == /tmp/release-planning-* ]] && rm -rf -- "{WORKDIR}"`

---

## Edge Cases

- **No Features found**: Try fallback JQL (handled in Phase 2b); warn user to confirm scope; stop if still empty.
- **Feature in New with no evidence of work**: Classified dormant; listed under "Scope nobody has started" with the reason; excluded from all risk math.
- **Active feature with no Epics**: Flagged by data-quality gate as FAIL — "no epics created."
- **Active feature whose epics have no Stories**: Flagged by data-quality gate as FAIL — "epics have no stories."
- **Epic that is Dev Complete/Testing/Release Pending/Closed or targets another release**: Excluded from scope; listed in the appendix with its open SP.
- **Assignee not in `.roster.json`**: Work counts as scope, capacity is zero; reported as roster drift and the user is asked before continuing.
- **Component filter matches no features**: Warn user and exit cleanly — "No features found for component {COMPONENT_FILTER}."
- **stories.json empty**: Data-quality gate flags all features as FAIL — no numeric projections possible.
- **bugs.json empty**: Bug load check reports no issues — not an error.
- **Sprint data unavailable**: transform-sprints.py sets `"error"` in JSON; main context stops before Phase 3.
- **Version format varies** (`5.0` vs `5.0.0`): Bug JQL tries both `fixVersion in ("{VERSION}", "{VERSION}.0")`.
- **Unlinked bugs (no epic)**: Collected in Phase 4b, reported separately in Bug Load check.

---

## Important Notes

- **Read-only**: This skill does not modify any Jira data.
- **Transform scripts**: `plugins/edge-scrum/bin/` — reusable data transformation (no LLM needed)
- **Analysis sub-agent**: `plugins/edge-scrum/skills/release-planning-analysis/SKILL.md` — LLM-driven risk assessment
- **Work directory**: `{WORKDIR}` persists across phases within a run. Rerunning on the same day overwrites prior files.
- **Laws files**: Authoritative for all team conventions. Never hardcode roster, rules, or sizing in skill definitions.
- **Data-quality gate**: MUST run before capacity and timeline checks. Features without story-level breakdown are excluded from numeric projections.
- **Method transparency**: `checks.json` → `method` records formula, inputs and result for every headline figure and the report renders it verbatim. Thresholds are named constants in `run-checks.py` and documented in `references/release-planning-method.md`; change both together.
